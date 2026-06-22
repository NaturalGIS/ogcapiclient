"""Manager to prepare collections for download."""

import os

from qgis.core import QgsRectangle

from ogcapiclient.core.constants import MAX_ZOOM_TILES_RASTER, MAX_ZOOM_TILES_VECTOR
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import Collection, OfflineDownload
from ogcapiclient.core.utils import cache_path
from ogcapiclient.qgis_backend.utils import (
    collect_tiles,
    rectangle_to_string,
    sanitize_crs_string,
)


class DownloadManager:
    """Computes the offline download plan for a set of selected collections."""

    @staticmethod
    def build_download_list(
        items: list[tuple[Collection, CollectionType]],
        cache_root: str,
        server_url: str,
        bbox: QgsRectangle,
        crs_map: dict[str:str],
    ) -> list[OfflineDownload]:
        """Builds a list of objectd describing collections selected for offline use.

        :param items: A list of tuples containing the Collection and type.
        :type items: list[tuple[Collection, CollectionType]]
        :param cache_root: A full path to the cache root directory.
        :type cache_root: str
        :param server_url:  The base URL (landing page) of the OGC API server.
        :type server_url: str
        :param bbox: A bounding box used to filter collection.
        :type bbox: QgsRectangle
        :param crs_map: A dictionary that maps collection and its CRS.
        :type crs_map: dict[str, str]
        :returns: A list of objects descriting collection.
        :rtype: list[OfflineItem]
        """
        download_list: list[OfflineDownload] = []

        bbox_string = rectangle_to_string(bbox)
        for collection, collection_type in items:
            crs = crs_map.get(collection.id)

            file_path = cache_path(
                cache_root,
                server_url,
                collection.id,
                sanitize_crs_string(crs),
                bbox_string,
                collection_type,
            )

            cache_exists = os.path.exists(file_path)

            tile_count = 0
            tile_ranges = None
            if collection_type in (
                CollectionType.TILES_RASTER,
                CollectionType.TILES_VECTOR,
            ):
                max_zoom = (
                    MAX_ZOOM_TILES_VECTOR
                    if collection_type == CollectionType.TILES_VECTOR
                    else MAX_ZOOM_TILES_RASTER
                )
                tile_count, tile_ranges = collect_tiles(bbox, max_zoom)

            download_list.append(
                OfflineDownload(
                    collection,
                    collection_type,
                    file_path,
                    crs,
                    bbox,
                    cache_exists,
                    tile_count,
                    tile_ranges,
                )
            )

        return download_list
