"""Background task for downloading data."""

import math
import os
import shutil
import tempfile
import zlib

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsCsException,
    QgsTask,
    QgsTileMatrixSet,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from ogcapiclient.core.constants import (
    MAX_ZOOM_TILES_RASTER,
    MAX_ZOOM_TILES_VECTOR,
    TMS_WEB_MERCATOR_QUAD,
)
from ogcapiclient.core.enums import CollectionType, LogLevel
from ogcapiclient.core.exceptions import (
    InvalidLayerError,
    MbTilesError,
    OgcApiClientError,
    WriteDataError,
)
from ogcapiclient.core.interfaces import Feedback, Loader, Logger
from ogcapiclient.core.mbtiles import MbTilesWriter
from ogcapiclient.core.models import DownloadedLayer, OfflineDownload, PreparedLayer
from ogcapiclient.core.ogc_api_client import OgcApiClient
from ogcapiclient.core.utils import create_uri_parts, format_tile_url, parse_tilesets
from ogcapiclient.qgis_backend.feedback import QgisFeedback
from ogcapiclient.qgis_backend.loader import QgisLoader
from ogcapiclient.qgis_backend.logger import QgisLogger
from ogcapiclient.qgis_backend.utils import create_layer_uri


class DownloadTask(QgsTask):
    """Task to download collection for offline use."""

    def __init__(
        self,
        landing_page: str,
        collections: list[OfflineDownload],
        auth_cfg: str = "",
        loader: Loader | None = None,
        logger: Logger | None = None,
        feedback: Feedback | None = None,
    ) -> None:
        """Initializes the layer downloading task.

        :param landing_page: The landing page URL.
        :type landing_page: str
        :param collections: A list of OfflineDownload objects.
        :type collections: list[OfflineDownload]
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        :param loader: Injected HTTP loader.
        :type loader: Loader
        :param logger: Injected logger.
        :type logger: Logger
        :param feedback: Injected feedback object.
        :type feedback: Feedback
        """

        super().__init__(
            "Download layers",
            QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt,
        )
        self.landing_page = landing_page
        self.collections = collections
        self.auth_cfg = auth_cfg
        self.feedback = feedback or QgisFeedback(self)
        self.logger = logger or QgisLogger()
        self.loader = loader or QgisLoader(self.logger, self.feedback)
        self.data = None
        self.exception = None

    def run(self) -> bool:
        """Executes the layer downloading.

        :returns: Whether the layer downloading was succesfull.
        :rtype: bool
        """
        self.client = OgcApiClient(
            self.loader, self.logger, self.feedback, self.auth_cfg
        )

        downloaded_layers = []

        try:
            for i in self.collections:
                if self.feedback.is_canceled():
                    break

                layer = None
                if i.collection_type == CollectionType.FEATURES:
                    layer = self.download_features(i)
                elif i.collection_type in (
                    CollectionType.TILES_RASTER,
                    CollectionType.TILES_VECTOR,
                ):
                    layer = self.download_tiles(i)
                else:
                    continue

                if layer:
                    downloaded_layers.append(layer)

                # TODO: report progress?

            self.data = downloaded_layers
            return True
        except Exception as e:
            self.logger.log(
                self.tr("Failed download data: {error}").format(error=str(e)),
                LogLevel.CRITICAL,
            )
            self.exception = e
            return False

    def cancel(self) -> None:
        """Triggered when the user cancels the task."""
        if self.feedback:
            self.feedback.cancel()
        super().cancel()

    def download_features(self, item: OfflineDownload) -> DownloadedLayer:
        """Downloads Features collection.

        :param item: Object describing collection to download.
        :type item: OfflineDownload
        :returns: Structured object describing oflline layer.
        :rtype: DownloadedLayer
        :raises InvalidLayerError: When vector layer can not be constructed
        for collection.
        :raises WriteDataError: When vector layer can not be saved to disk.
        """
        self.logger.log(
            self.tr("Downloading Features from collection '{name}'.").format(
                name=item.collection.id
            )
        )
        uri_parts = create_uri_parts(
            item.collection.id,
            self.landing_page,
            item.collection_type,
            crs=item.crs,
            auth_cfg=self.auth_cfg,
        )
        uri = create_layer_uri(
            PreparedLayer(item.collection.title, item.collection_type, uri_parts),
            item.bbox,
        )

        self.logger.log(self.tr("Instantiating vector layer."))
        layer = QgsVectorLayer(uri, item.collection.id, "oapif")
        if not layer.isValid():
            self.logger.log(
                self.tr("An invalid layer created from URI '{uri}'.").format(uri=uri),
                LogLevel.CRITICAL,
            )
            raise InvalidLayerError(f"An invalid layer created from URI '{uri}'.")

        os.makedirs(os.path.split(item.file_path)[0], exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg")
        temp_file_path = temp_file.name
        temp_file.close()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.drivername = "GPKG"
        options.layerName = item.collection.id
        options.fileEncoding = "UTF-8"

        # TODO: pass feedback for cancellation and progress reporting?
        self.logger.log(self.tr("Saving to GeoPackage."))
        error_code, error_message, output_path, layer_name = (
            QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, temp_file_path, QgsCoordinateTransformContext(), options
            )
        )
        if error_code != QgsVectorFileWriter.WriterError.NoError:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            self.logger.log(
                self.tr("Failed to save data: {message}.").format(
                    message=error_message
                ),
                LogLevel.CRITICAL,
            )
            raise WriteDataError(f"Failed to save data: {error_message}.")

        shutil.move(temp_file_path, item.file_path)
        return DownloadedLayer(
            item.collection.title, item.collection_type, item.file_path
        )

    def download_tiles(self, item: OfflineDownload) -> DownloadedLayer:
        """Downloads Tiles collection.

        :param item: Object describing collection to download.
        :type item: OfflineDownload
        :returns: Structured object describing oflline layer.
        :rtype: DownloadedLayer
        :raises MbTilesError: When MBTiles file can not be created.
        """
        self.logger.log(
            self.tr("Downloading Tiles from collection '{name}'.").format(
                name=item.collection.id
            )
        )
        tiles_url = item.collection.capabilities.get(item.collection_type)
        raw_tilesets = self.client.get_tilesets(tiles_url)

        if item.collection_type == CollectionType.TILES_VECTOR:
            mime_types = [
                "application/vnd.mapbox-vector-tile",
                "application/x-protobuf",
            ]
        elif item.collection_type == CollectionType.TILES_RASTER:
            mime_types = ["image/png", "image/jpeg", "image/webp"]

        self.logger.log(self.tr("Parsing tilesets."))
        parsed_tilesets = parse_tilesets(raw_tilesets, mime_types)
        preferred_tileset = next(
            (ts for ts in parsed_tilesets if ts.tms_id == TMS_WEB_MERCATOR_QUAD),
            parsed_tilesets[0],
        )
        templated_url = preferred_tileset.url_template

        os.makedirs(os.path.split(item.file_path)[0], exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mbtiles")
        temp_file_path = temp_file.name
        temp_file.close()

        writer = MbTilesWriter(temp_file_path)
        if not writer.create():
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            self.logger.log(
                self.tr("Failed to create MBTiles file."), LogLevel.CRITICAL
            )
            raise MbTilesError(f"Failed to create MBTiles file {temp_file_path}")

        writer.set_metadata_value("name", item.collection.id)
        writer.set_metadata_value("description", item.collection.title)
        writer.set_metadata_value("minzoom", "0")

        if item.collection_type == CollectionType.TILES_VECTOR:
            writer.set_metadata_value("format", "pbf")
            writer.set_metadata_value("maxzoom", "24")
        elif item.collection_type == CollectionType.TILES_RASTER:
            writer.set_metadata_value("format", "png")
            writer.set_metadata_value("maxzoom", "18")
            writer.set_metadata_value("version", "1.1")
            writer.set_metadata_value("type", "overlay")

        try:
            writer.set_metadata_value("crs", "EPSG:3857")
            bounds_str = (
                f"{item.bbox.xMinimum()},{item.bbox.yMinimum()},"
                f"{item.bbox.xMaximum()},{item.bbox.yMaximum()}"
            )
            writer.set_metadata_value("bounds", bounds_str)
        except QgsCsException:
            pass
        except AttributeError:
            pass

        tile_matrix_set = QgsTileMatrixSet()
        tile_matrix_set.addGoogleCrs84QuadTiles(
            0,
            MAX_ZOOM_TILES_RASTER
            if item.collection_type == CollectionType.TILES_RASTER
            else MAX_ZOOM_TILES_VECTOR,
        )

        # TODO: pass feedback for cancellation and progress reporting
        self.logger.log(self.tr("Saving to MBTiles."))
        for zoom, tile_range in item.tile_ranges.items():
            tiles = tile_matrix_set.tilesInRange(tile_range, zoom)
            for i, tile in enumerate(tiles):
                tile_matrix = tile_matrix_set.tileMatrix(tile.zoomLevel())
                url = format_tile_url(
                    templated_url,
                    tile.column(),
                    tile.row(),
                    tile.zoomLevel(),
                    tile_matrix.matrixHeight(),
                )
                try:
                    data = self.client.get_tile(url)
                except OgcApiClientError as e:
                    self.logger.log(
                        self.tr("Could not download tile '{url}': {error}").format(
                            url=url, error=str(e)
                        ),
                        LogLevel.WARNING,
                    )
                    continue
                row_tms = math.pow(2, tile.zoomLevel()) - tile.row() - 1
                if item.collection_type == CollectionType.TILES_VECTOR:
                    compression_object = zlib.compressobj(
                        zlib.Z_DEFAULT_COMPRESSION,
                        zlib.DEFLATED,
                        zlib.MAX_WBITS + 16,
                        8,
                        zlib.Z_DEFAULT_STRATEGY,
                    )
                    gzip_data = compression_object.compress(data)
                    gzip_data += compression_object.flush()
                    writer.set_tile_data(
                        tile.zoomLevel(), tile.column(), row_tms, gzip_data
                    )
                elif item.collection_type == CollectionType.TILES_RASTER:
                    writer.set_tile_data(tile.zoomLevel(), tile.column(), row_tms, data)

        writer.close()
        shutil.move(temp_file_path, item.file_path)

        return DownloadedLayer(
            item.collection.title, item.collection_type, item.file_path
        )
