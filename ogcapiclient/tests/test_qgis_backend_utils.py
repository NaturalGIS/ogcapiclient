import unittest

from qgis.core import QgsRectangle

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.exceptions import CrsNormalizationError
from ogcapiclient.core.models import PreparedLayer, TileSet
from ogcapiclient.qgis_backend.utils import (
    create_layer_uri,
    filter_from_bbox,
    rectangle_to_string,
    sanitize_crs_string,
)


def _features_layer(
    url: str = "https://example.com", typename: str = "nuts1", auth_cfg: str = ""
) -> PreparedLayer:
    """Returns a PreparedLayer for Features collection.

    :param url: The URL used to load features.
    :type url: str
    :param typename: A collection id.
    :param typename: str
    :param typename: QGIS authentication configuration ID.
    :param typename: str
    :returns: A prepared layer object.
    :rtype: PreparedLayer
    """
    parts: dict = {"url": url, "typename": typename}
    if auth_cfg:
        parts["authcfg"] = auth_cfg
    return PreparedLayer("NUTS I", CollectionType.FEATURES, parts)


def _raster_tiles_layer(
    url: str = "https://example.com/tiles/{z}/{y}/{x}", auth_cfg: str = ""
) -> PreparedLayer:
    """Returns a PreparedLayer for Tiles (raster) collection.

    :param url: The URL used to load features.
    :type url: str
    :param typename: A collection id.
    :param typename: str
    :param typename: QGIS authentication configuration ID.
    :param typename: str
    :returns: A prepared layer object.
    :rtype: PreparedLayer
    """
    parts: dict = {"url": url, "type": "xyz", "zmin": "0", "zmax": "18"}
    if auth_cfg:
        parts["authcfg"] = auth_cfg
    return PreparedLayer("Raster Tiles", CollectionType.TILES_RASTER, parts)


def _vector_tiles_layer(
    url: str = "https://example.com/tiles/{z}/{y}/{x}", auth_cfg: str = ""
) -> PreparedLayer:
    """Returns a PreparedLayer for Tiles (vector) collection.

    :param url: The URL used to load features.
    :type url: str
    :param typename: A collection id.
    :param typename: str
    :param typename: QGIS authentication configuration ID.
    :param typename: str
    :returns: A prepared layer object.
    :rtype: PreparedLayer
    """
    parts: dict = {"url": url, "zmin": "0", "zmax": "14"}
    if auth_cfg:
        parts["authcfg"] = auth_cfg
    return PreparedLayer("Vector Tiles", CollectionType.TILES_VECTOR, parts)


class TestFilterFromBbox(unittest.TestCase):
    def test_returns_string(self):
        result = filter_from_bbox(QgsRectangle(-10, 36, -6, 42), "EPSG:4326")
        self.assertIsInstance(result, str)

    def test_starts_with_intersects_bbox(self):
        result = filter_from_bbox(QgsRectangle(-10, 36, -6, 42), "EPSG:4326")
        self.assertTrue(result.startswith("intersects_bbox($geometry,"))

    def test_contains_geom_from_wkt(self):
        result = filter_from_bbox(QgsRectangle(-10, 36, -6, 42), "EPSG:4326")
        self.assertIn("geomFromWkt(", result)

    def test_wkt_is_polygon(self):
        result = filter_from_bbox(QgsRectangle(-10, 36, -6, 42), "EPSG:4326")
        self.assertIn("Polygon ((", result)

    def test_all_four_coordinates_present(self):
        result = filter_from_bbox(QgsRectangle(-10.0, 36.0, -6.0, 42.0), "EPSG:4326")
        for coord in ["-10", "36", "-6", "42"]:
            self.assertIn(coord, result)

    def test_wkt_ring_is_closed(self):
        result = filter_from_bbox(QgsRectangle(-10.0, 36.0, -6.0, 42.0), "EPSG:4326")
        start = result.index("Polygon ((") + len("Polygon ((")
        end = result.index("))")
        pairs = [p.strip() for p in result[start:end].split(",")]
        self.assertEqual(pairs[0], pairs[-1])

    def test_wkt_ring_has_five_points(self):
        result = filter_from_bbox(QgsRectangle(-10.0, 36.0, -6.0, 42.0), "EPSG:4326")
        start = result.index("Polygon ((") + len("Polygon ((")
        end = result.index("))")
        pairs = [p.strip() for p in result[start:end].split(",")]
        self.assertEqual(len(pairs), 5)

    def test_all_four_corners_present(self):
        result = filter_from_bbox(QgsRectangle(-10.0, 36.0, -6.0, 42.0), "EPSG:4326")
        start = result.index("Polygon ((") + len("Polygon ((")
        end = result.index("))")
        pairs = {
            tuple(float(v) for v in p.strip().split())
            for p in result[start:end].split(",")
        }
        expected_corners = {(-10.0, 36.0), (-6.0, 36.0), (-6.0, 42.0), (-10.0, 42.0)}
        self.assertEqual(pairs, expected_corners)

    def test_degenerate_point_bbox_does_not_raise(self):
        try:
            result = filter_from_bbox(QgsRectangle(0.0, 0.0, 0.0, 0.0), "EPSG:4326")
        except Exception as exc:
            self.fail(f"filter_from_bbox raised unexpectedly: {exc}")
        self.assertIn("intersects_bbox", result)

    def test_bbox_transformation(self):
        result = filter_from_bbox(QgsRectangle(10.0, 45.0, 20.0, 55.0), "EPSG:4326")
        self.assertIn("10", result)
        self.assertIn("45", result)
        self.assertIn("20", result)
        self.assertIn("55", result)

        result = filter_from_bbox(QgsRectangle(10.0, 45.0, 20.0, 55.0), "EPSG:3857")
        self.assertIn("1113194.9", result)
        self.assertIn("5621521.4", result)
        self.assertIn("2226389.8", result)
        self.assertIn("7361866.1", result)


class TestCreateLayerUri(unittest.TestCase):
    def test_features_returns_string(self):
        uri = create_layer_uri(_features_layer())
        self.assertIsInstance(uri, str)

    def test_features_uri_is_not_empty(self):
        uri = create_layer_uri(_features_layer())
        self.assertTrue(uri)

    def test_features_url_present_in_uri(self):
        uri = create_layer_uri(_features_layer("https://test.server.com"))
        self.assertIn("test.server.com", uri)

    def test_features_typename_present_in_uri(self):
        uri = create_layer_uri(_features_layer(typename="testCollection"))
        self.assertIn("testCollection", uri)

    def test_features_url_is_percent_encoded(self):
        uri = create_layer_uri(_features_layer(url="https://example.com/api"))
        self.assertNotIn("url=https://", uri)

    def test_features_no_filter_param_when_no_bbox(self):
        uri = create_layer_uri(_features_layer())
        self.assertNotIn("filter=", uri)
        self.assertNotIn("filter%3D", uri)

    def test_features_filter_param_present_when_bbox_given(self):
        bbox = QgsRectangle(-10.0, 36.0, -6.0, 42.0)
        uri = create_layer_uri(_features_layer(), bbox=bbox)
        self.assertTrue("filter" in uri)

    def test_features_filter_contains_bbox_coordinates(self):
        bbox = QgsRectangle(-10.0, 36.0, -6.0, 42.0)
        uri = create_layer_uri(_features_layer(), bbox=bbox)
        self.assertIn("36", uri)
        self.assertIn("42", uri)

    # authcfg is ommited from URL
    @unittest.expectedFailure
    def test_features_auth_cfg_present(self):
        layer = _features_layer(auth_cfg="testAuthId")
        uri = create_layer_uri(_features_layer(auth_cfg="testAuthId"))
        self.assertIn("testAuthId", uri)

    def test_features_original_uri_parts_not_mutated(self):
        layer = _features_layer(auth_cfg="testAuthId")
        original_parts = dict(layer.uri_parts)
        create_layer_uri(layer)
        self.assertEqual(layer.uri_parts, original_parts)

    def test_features_different_typenames_produce_different_uris(self):
        uri_a = create_layer_uri(_features_layer(typename="nuts1"))
        uri_b = create_layer_uri(_features_layer(typename="municipios"))
        self.assertNotEqual(uri_a, uri_b)

    def test_features_different_bboxes_produce_different_uris(self):
        layer = _features_layer()
        uri_a = create_layer_uri(layer, bbox=QgsRectangle(-10, 36, -6, 42))
        uri_b = create_layer_uri(layer, bbox=QgsRectangle(-8, 38, -7, 40))
        self.assertNotEqual(uri_a, uri_b)

    def test_raster_tiles_returns_string(self):
        uri = create_layer_uri(_raster_tiles_layer())
        self.assertIsInstance(uri, str)

    def test_raster_tiles_uri_is_not_empty(self):
        uri = create_layer_uri(_raster_tiles_layer())
        self.assertTrue(uri)

    def test_raster_tiles_tile_url_present_in_uri(self):
        uri = create_layer_uri(
            _raster_tiles_layer(url="https://example.com/tiles/{z}/{y}/{x}")
        )
        self.assertIn("example.com", uri)

    def test_raster_tiles_bbox_is_not_used(self):
        layer = _raster_tiles_layer()
        uri_with_bbox = create_layer_uri(layer, bbox=QgsRectangle(-10, 36, -6, 42))
        uri_without_bbox = create_layer_uri(layer, bbox=None)
        self.assertEqual(uri_with_bbox, uri_without_bbox)

    def test_raster_tiles_original_uri_parts_not_mutated(self):
        layer = _raster_tiles_layer()
        original_parts = dict(layer.uri_parts)
        create_layer_uri(layer)
        self.assertEqual(layer.uri_parts, original_parts)

    def test_raster_tiles_auth_cfg_present(self):
        uri = create_layer_uri(_raster_tiles_layer(auth_cfg="testAuthId"))
        self.assertIn("testAuthId", uri)

    def test_raster_tiles_different_urls_produce_different_uris(self):
        uri_a = create_layer_uri(
            _raster_tiles_layer(url="https://a.example.com/tiles/{z}/{y}/{x}")
        )
        uri_b = create_layer_uri(
            _raster_tiles_layer(url="https://b.example.com/tiles/{z}/{y}/{x}")
        )
        self.assertNotEqual(uri_a, uri_b)

    def test_vector_tiles_returns_string(self):
        uri = create_layer_uri(_vector_tiles_layer())
        self.assertIsInstance(uri, str)

    def test_vector_tiles_uri_is_not_empty(self):
        uri = create_layer_uri(_vector_tiles_layer())
        self.assertTrue(uri)

    def test_vector_tiles_tile_url_present_in_uri(self):
        uri = create_layer_uri(
            _vector_tiles_layer(url="https://vt.example.com/tiles/{z}/{y}/{x}")
        )
        self.assertIn("vt.example.com", uri)

    def test_vector_tiles_bbox_has_no_effect(self):
        layer = _vector_tiles_layer()
        uri_with_bbox = create_layer_uri(layer, bbox=QgsRectangle(-10, 36, -6, 42))
        uri_without_bbox = create_layer_uri(layer, bbox=None)
        self.assertEqual(uri_with_bbox, uri_without_bbox)

    def test_vector_tiles_original_uri_parts_not_mutated(self):
        layer = _vector_tiles_layer()
        original_parts = dict(layer.uri_parts)
        create_layer_uri(layer)
        self.assertEqual(layer.uri_parts, original_parts)

    def test_vector_tiles_auth_cfg_present(self):
        uri = create_layer_uri(_vector_tiles_layer(auth_cfg="testAuthId"))
        self.assertIn("testAuthId", uri)


class TestRectangleToString(unittest.TestCase):
    def test_numbers_trimmed_to_six_decimal_places(self):
        bbox = QgsRectangle(-8.612345678, 41.145678123, -8.600000000, 41.150000000)
        result = rectangle_to_string(bbox)
        self.assertEqual(result, "-8.612346,41.145678,-8.600000,41.150000")

    def test_trailing_zeros_preserved(self):
        bbox = QgsRectangle(0, -90.0, 180, 0)
        result = rectangle_to_string(bbox)
        self.assertEqual(result, "0.000000,-90.000000,180.000000,0.000000")

    def test_output_format_is_xmin_ymin_xmax_ymax(self):
        bbox = QgsRectangle(1.0, 2.0, 3.0, 4.0)
        result = rectangle_to_string(bbox)
        parts = result.split(",")
        self.assertEqual(len(parts), 4)
        self.assertEqual(float(parts[0]), bbox.xMinimum())
        self.assertEqual(float(parts[1]), bbox.yMinimum())
        self.assertEqual(float(parts[2]), bbox.xMaximum())
        self.assertEqual(float(parts[3]), bbox.yMaximum())

    def test_negative_coordinates(self):
        bbox = QgsRectangle(-180.0, -90.0, -1.0, -1.0)
        result = rectangle_to_string(bbox)
        self.assertEqual(result, "-180.000000,-90.000000,-1.000000,-1.000000")


class TestSanitizeCrs(unittest.TestCase):
    def test_epsg_uppercase_colon(self):
        self.assertEqual(sanitize_crs_string("EPSG:4326"), "EPSG4326")

    def test_epsg_lowercase_colon(self):
        self.assertEqual(sanitize_crs_string("epsg:4326"), "EPSG4326")

    def test_epsg_mixed_case(self):
        self.assertEqual(sanitize_crs_string("Epsg:4326"), "EPSG4326")

    def test_epsg_3857(self):
        self.assertEqual(sanitize_crs_string("EPSG:3857"), "EPSG3857")

    def test_epsg_25832(self):
        self.assertEqual(sanitize_crs_string("EPSG:25832"), "EPSG25832")

    def test_ogc_urn_epsg_4326(self):
        self.assertEqual(sanitize_crs_string("urn:ogc:def:crs:EPSG::4326"), "EPSG4326")

    def test_ogc_urn_epsg_3857(self):
        self.assertEqual(sanitize_crs_string("urn:ogc:def:crs:EPSG::3857"), "EPSG3857")

    def test_output_contains_no_colon(self):
        result = sanitize_crs_string("EPSG:4326")
        self.assertNotIn(":", result)

    def test_output_is_uppercase(self):
        result = sanitize_crs_string("epsg:4326")
        self.assertEqual(result, result.upper())

    def test_output_is_deterministic(self):
        self.assertEqual(
            sanitize_crs_string("EPSG:4326"), sanitize_crs_string("EPSG:4326")
        )

    def test_epsg_short_form_and_urn_produce_same_output(self):
        self.assertEqual(
            sanitize_crs_string("EPSG:4326"),
            sanitize_crs_string("urn:ogc:def:crs:EPSG::4326"),
        )

    def test_unrecognised_authority_raises(self):
        with self.assertRaises(CrsNormalizationError):
            sanitize_crs_string("FAKE:9999")

    def test_empty_string_raises(self):
        with self.assertRaises(CrsNormalizationError):
            sanitize_crs_string("")

    def test_malformed_string_raises(self):
        with self.assertRaises(CrsNormalizationError):
            sanitize_crs_string("not-a-crs-at-all")

    def test_raises_correct_exception_type(self):
        with self.assertRaises(CrsNormalizationError) as ctx:
            sanitize_crs_string("INVALID:0000")
        self.assertIn("INVALID:0000", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
