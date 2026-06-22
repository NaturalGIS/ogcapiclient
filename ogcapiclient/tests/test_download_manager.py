import os
import tempfile
import unittest

from qgis.core import QgsRectangle

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import BoundingBox, Collection
from ogcapiclient.qgis_backend.download_manager import DownloadManager


class TestDownloadManager(unittest.TestCase):
    def setUp(self):
        self.collection = Collection("test", "test_collection", BoundingBox(), {})
        self.server_url = "https://example.com/test"
        self.crs_map = {"test": "EPSG:4326"}
        self.bbox = QgsRectangle(14.0, 50.0, 14.1, 50.1)

    def test_build_download_list_features(self):
        with tempfile.TemporaryDirectory() as cache_root:
            result = DownloadManager.build_download_list(
                [(self.collection, CollectionType.FEATURES)],
                cache_root,
                self.server_url,
                self.bbox,
                self.crs_map,
            )

        self.assertEqual(len(result), 1)

        item = result[0]

        self.assertEqual(item.collection, self.collection)
        self.assertEqual(item.collection_type, CollectionType.FEATURES)
        self.assertEqual(item.crs, "EPSG:4326")
        self.assertEqual(item.bbox, self.bbox)
        self.assertFalse(item.cache_exists)
        self.assertEqual(item.tile_count, 0)
        self.assertIsNone(item.tile_ranges)
        self.assertTrue(item.file_path.startswith(cache_root))

    def test_build_download_list_vector_tiles(self):
        with tempfile.TemporaryDirectory() as cache_root:
            result = DownloadManager.build_download_list(
                [(self.collection, CollectionType.TILES_VECTOR)],
                cache_root,
                self.server_url,
                self.bbox,
                self.crs_map,
            )

        self.assertEqual(len(result), 1)

        item = result[0]

        self.assertEqual(item.collection, self.collection)
        self.assertEqual(item.collection_type, CollectionType.TILES_VECTOR)
        self.assertEqual(item.bbox, self.bbox)
        self.assertFalse(item.cache_exists)
        self.assertGreater(item.tile_count, 0)
        self.assertIsNotNone(item.tile_ranges)
        self.assertGreater(len(item.tile_ranges), 0)

        for zoom, tile_range in item.tile_ranges.items():
            self.assertIsInstance(zoom, int)
            self.assertIsNotNone(tile_range)

    def test_build_download_list_raster_tiles(self):
        with tempfile.TemporaryDirectory() as cache_root:
            result = DownloadManager.build_download_list(
                [(self.collection, CollectionType.TILES_RASTER)],
                cache_root,
                self.server_url,
                self.bbox,
                self.crs_map,
            )

        self.assertEqual(len(result), 1)

        item = result[0]

        self.assertEqual(item.collection, self.collection)
        self.assertEqual(item.collection_type, CollectionType.TILES_RASTER)
        self.assertEqual(item.bbox, self.bbox)
        self.assertFalse(item.cache_exists)
        self.assertGreater(item.tile_count, 0)
        self.assertIsNotNone(item.tile_ranges)
        self.assertGreater(len(item.tile_ranges), 0)

        for zoom, tile_range in item.tile_ranges.items():
            self.assertIsInstance(zoom, int)
            self.assertIsNotNone(tile_range)

    def test_build_download_list_cache_exists(self):
        with tempfile.TemporaryDirectory() as cache_root:
            result = DownloadManager.build_download_list(
                [(self.collection, CollectionType.FEATURES)],
                cache_root,
                self.server_url,
                self.bbox,
                self.crs_map,
            )

            item = result[0]

            os.makedirs(os.path.split(item.file_path)[0], exist_ok=True)

            with open(item.file_path, "w") as f:
                f.write("test")

            result = DownloadManager.build_download_list(
                [(self.collection, CollectionType.FEATURES)],
                cache_root,
                self.server_url,
                self.bbox,
                self.crs_map,
            )
            item = result[0]
            self.assertTrue(item.cache_exists)

    def test_build_download_list_multiple_collections(self):
        with tempfile.TemporaryDirectory() as cache_root:
            items = [
                (self.collection, CollectionType.FEATURES),
                (self.collection, CollectionType.TILES_VECTOR),
            ]

            result = DownloadManager.build_download_list(
                items, cache_root, self.server_url, self.bbox, self.crs_map
            )

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].collection_type, CollectionType.FEATURES)
            self.assertEqual(result[1].collection_type, CollectionType.TILES_VECTOR)
            self.assertEqual(result[0].tile_count, 0)
            self.assertGreater(result[1].tile_count, 0)
