from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsProject,
    QgsProviderRegistry,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QUrl

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.exceptions import CrsNormalizationError
from ogcapiclient.core.models import PreparedLayer


def filter_from_bbox(bbox: QgsRectangle, crs: str) -> str:
    """Builds a QGIS filter expression that constrains features to a bounding box.

    :param bbox: The bounding box in EPSG:4326/CRS84.
    :type bbox: QgsRectangle
    :param crs: The target layer CRS.
    :type crs: str
    :returns: A QGIS expression string suitable for the 'filter' URI parameter.
    :rtype: str
    """
    filter_bbox = QgsRectangle(bbox)
    if crs:
        source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        target_crs = QgsCoordinateReferenceSystem(crs)
        if target_crs.isValid() and target_crs != source_crs:
            transform = QgsCoordinateTransform(
                source_crs, target_crs, QgsProject.instance()
            )
            filter_bbox = transform.transform(bbox)

    return f"intersects_bbox($geometry, geomFromWkt('{filter_bbox.asWktPolygon()}'))"


def create_layer_uri(layer: PreparedLayer, bbox: QgsRectangle = None) -> str:
    """Creates a QGIS connection string for a prepared layer.

    For Features layers an optional bounding box can be supplied to limit
    amount of requested daata.

    :param layer: Information about the layer to add.
    :type layer: PreparedLayer
    :param bbox: Optional AOI in EPSG:4326/CRS84.
    :type bbox: QgsRectangle
    :returns: A URI suitable for constructing a QGIS layer.
    :rtype: str
    """
    parts = layer.uri_parts.copy()

    if layer.collection_type == CollectionType.TILES_RASTER:
        return QgsProviderRegistry.instance().encodeUri("wms", parts)

    auth_cfg = parts.pop("authcfg", "")
    crs = parts.get("srsname")
    ds_uri = QgsDataSourceUri()

    for k, v in parts.items():
        if k == "url" and layer.collection_type == CollectionType.FEATURES:
            v = QUrl(v).toEncoded().data().decode("utf-8")
        if k == "srsname" and layer.collection_type == CollectionType.FEATURES:
            continue
        ds_uri.setParam(k, v)

    if auth_cfg:
        ds_uri.setAuthConfigId(auth_cfg)

    if layer.collection_type == CollectionType.FEATURES and bbox is not None:
        ds_uri.setParam("filter", filter_from_bbox(bbox, crs))

    if layer.collection_type == CollectionType.FEATURES:
        return ds_uri.uri()
    else:
        return ds_uri.encodedUri().data().decode("utf-8")


def rectangle_to_string(bbox: QgsRectangle) -> str:
    """Formats QgsRectangle to string representation.

       Trims coordinates to 6 decimal places.
    :param bbox: QgsRectangle to convert into string.
    :type bbox: str
    :returns: String representation of the input bbox.
    :rtype: str
    """
    return f"{bbox.xMinimum():.6f},{bbox.yMinimum():.6f},{bbox.xMaximum():.6f},{bbox.yMaximum():.6f}"


def sanitize_crs_string(crs_string: str) -> str:
    """ "Resolves a CRS identifier string to a normalised, filesystem-safe identifier.

    :param crs_string: CRS identifier string in any form accepted by QgsCoordinateReferenceSystem.createFromOgcWmsCrs().
    :type crs_string: str
    :returns: Normalised, filesystem-safe CRS identifier.
    :rtype: str
    :raises CrsNormalizationError: If crs_string cannot be resolved to a valid CRS.
    """
    crs = QgsCoordinateReferenceSystem()
    crs.createFromOgcWmsCrs(crs_string)
    if not crs.isValid():
        raise CrsNormalizationError(
            f"Could not resolve CRS identifier '{crs_string!r}'."
        )

    return crs.authid().replace(":", "").upper()


def collect_tiles(bbox, max_zoom: int) -> dict:
    """Computes the tile range for each zoom level from 0 to *max_zoom*.

    Uses the WebMercatorQuad tile matrix set. The bounding box must be
    provided in EPSG:4326 (geographic coordinates); QGIS reprojects
    internally when computing the tile range.

    The returned dictionary is keyed by zoom level (int) and maps to a
    ``QgsTileRange`` object. The same dict is reused by the download task
    so that tile ranges are computed only once.

    :param bbox: Area of interest as a QgsRectangle in EPSG:4326.
    :param max_zoom: Maximum zoom level to include (inclusive).
    :type max_zoom: int
    :returns: Mapping of zoom level → QgsTileRange.
    :rtype: dict[int, QgsTileRange]
    """
    tile_matrix_set = QgsVectorTileMatrixSet.fromWebMercator(0, max_zoom)
    tile_count = 0
    tile_ranges = dict()
    for i in range(max_zoom + 1):
        tile_matrix = tile_matrix_set.tileMatrix(i)
        tile_range = tile_matrix.tileRangeFromExtent(bbox)
        tile_ranges[i] = tile_range
        tile_count += (tile_range.endColumn() - tile_range.startColumn() + 1) * (
            tile_range.endRow() - tile_range.startRow() + 1
        )

    return tile_count, tile_ranges
