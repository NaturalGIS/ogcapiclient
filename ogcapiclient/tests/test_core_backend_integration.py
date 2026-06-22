import unittest

from ogcapiclient.core.constants import TMS_WEB_MERCATOR_QUAD
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import PreparedLayer, TileSet
from ogcapiclient.core.utils import create_uri_parts
from ogcapiclient.qgis_backend.utils import create_layer_uri


class TestCreateLayerUriIntegration(unittest.TestCase):
    def _create_tileset(self):
        return TileSet(
            tms_id=TMS_WEB_MERCATOR_QUAD,
            url_template="https://example.com/tiles/{z}/{y}/{x}",
        )

    def test_create_uri_parts_and_create_layer_uri(self):
        cases = [
            (
                CollectionType.FEATURES,
                {"crs": "EPSG:4326"},
                ["https://example.com"],
            ),
            (
                CollectionType.TILES_RASTER,
                {"tileset": self._create_tileset()},
                [
                    "type=xyz",
                    "https%3A%2F%2Fexample.com%2Ftiles%2F%7Bz%7D%2F%7By%7D%2F%7Bx%7D",
                ],
            ),
            (
                CollectionType.TILES_VECTOR,
                {"tileset": self._create_tileset()},
                [
                    "type=xyz",
                    "https%3A%2F%2Fexample.com%2Ftiles%2F%7Bz%7D%2F%7By%7D%2F%7Bx%7D",
                ],
            ),
        ]

        for collection_type, kwargs, expected in cases:
            with self.subTest(msg=f"Testing collection: {collection_type.name}"):
                uri_parts = create_uri_parts(
                    collection_id="testCollection",
                    landing_page_url="https://example.com",
                    collection_type=collection_type,
                    auth_cfg="testAuthId",
                    **kwargs,
                )

                layer = PreparedLayer(
                    name="layer",
                    collection_type=collection_type,
                    uri_parts=uri_parts,
                )

                uri = create_layer_uri(layer)

                self.assertTrue(uri)
                for i in expected:
                    self.assertIn(i, uri)


if __name__ == "__main__":
    unittest.main()
