import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from qgis.core import (
    QgsMapLayer,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorTileLayer,
)

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import DownloadedLayer, PreparedLayer
from ogcapiclient.qgis_backend.layer_manager import LayerManager


class TestLayerManager(unittest.TestCase):
    def test_create_online_features_layer(self):
        prepared = PreparedLayer(
            name="features",
            collection_type=CollectionType.FEATURES,
            uri_parts={},
        )

        layer = LayerManager.create_online_layer(prepared, "dummy")

        self.assertIsInstance(layer, QgsVectorLayer)
        self.assertEqual(layer.name(), "features")
        self.assertEqual(layer.providerType(), "oapif")

    def test_create_online_raster_layer(self):
        prepared = PreparedLayer(
            name="raster",
            collection_type=CollectionType.TILES_RASTER,
            uri_parts={},
        )

        layer = LayerManager.create_online_layer(prepared, "dummy")

        self.assertIsInstance(layer, QgsRasterLayer)
        self.assertEqual(layer.name(), "raster")
        self.assertEqual(layer.providerType(), "wms")

    def test_create_online_vector_tiles_layer(self):
        prepared = PreparedLayer(
            name="pbf",
            collection_type=CollectionType.TILES_VECTOR,
            uri_parts={},
        )

        layer = LayerManager.create_online_layer(prepared, "dummy")

        self.assertIsInstance(layer, QgsVectorTileLayer)
        self.assertEqual(layer.name(), "pbf")

    def test_create_offline_features_layer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.geojson")

            with open(path, "w", encoding="utf-8") as f:
                f.write('{"type":"FeatureCollection","features":[]}')

            downloaded = DownloadedLayer(
                name="features",
                collection_type=CollectionType.FEATURES,
                file_path=path,
            )

            layer = LayerManager.create_offline_layer(downloaded)

            self.assertIsInstance(layer, QgsVectorLayer)
            self.assertEqual(layer.name(), "features")
            self.assertEqual(layer.providerType(), "ogr")
            self.assertTrue(layer.isValid())

    def test_create_offline_raster_layer(self):
        downloaded = DownloadedLayer(
            name="raster",
            collection_type=CollectionType.TILES_RASTER,
            file_path="/does/not/exist.tif",
        )

        layer = LayerManager.create_offline_layer(downloaded)

        self.assertIsInstance(layer, QgsRasterLayer)
        self.assertEqual(layer.name(), "raster")
        self.assertEqual(layer.providerType(), "gdal")

    def test_create_offline_vector_tiles_layer(self):
        downloaded = DownloadedLayer(
            name="pbf",
            collection_type=CollectionType.TILES_VECTOR,
            file_path="/tmp/test.mbtiles",
        )

        layer = LayerManager.create_offline_layer(downloaded)

        self.assertIsInstance(layer, QgsVectorTileLayer)
        self.assertEqual(layer.name(), "pbf")

    @patch("ogcapiclient.qgis_backend.layer_manager.QgsProject")
    def test_add_valid_layer(self, mock_project):
        layer = Mock(spec=QgsMapLayer)
        layer.isValid.return_value = True

        result = LayerManager.add_layer(layer)

        self.assertTrue(result)
        mock_project.instance.return_value.addMapLayer.assert_called_once_with(layer)

    @patch("ogcapiclient.qgis_backend.layer_manager.QgsProject")
    def test_add_invalid_layer(self, mock_project):
        layer = Mock(spec=QgsMapLayer)
        layer.isValid.return_value = False

        result = LayerManager.add_layer(layer)

        self.assertFalse(result)
        mock_project.instance.return_value.addMapLayer.assert_not_called()
