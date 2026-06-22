import os
import unittest

from ogcapiclient.core.constants import TMS_WEB_MERCATOR_QUAD
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import TileSet
from ogcapiclient.core.utils import (
    cache_path,
    create_uri_parts,
    find_link,
    format_tile_url,
    hash_data,
    parse_collection,
    parse_extent,
    parse_links,
    parse_tilesets,
    sanitize_string,
)
from ogcapiclient.tests.utils import create_tileset_data, load_from_file


class TestParseLinks(unittest.TestCase):
    def test_invalid_inputs_return_empty_list(self):
        invalid_inputs = [
            ({}, "empty dict"),
            (None, "None"),
            ("links", "string"),
            ([], "empty list"),
            (["not-a-dict", 13, None], "list with non-dict items"),
        ]

        for payload, description in invalid_inputs:
            with self.subTest(msg=f"Testing invalid input: {description}"):
                self.assertListEqual(parse_links(payload), [])

    def test_mixed_list_items(self):
        data = [
            {"href": "https://example.com", "rel": "self"},
            "not-a-dict",
            {"href": "https://example.com/conformance", "rel": "conformance"},
            13,
        ]
        links = parse_links(data)
        self.assertEqual(len(links), 2)

    def test_fields_mapped_correctly(self):
        data = [
            {
                "href": "https://example.com",
                "rel": "self",
                "type": "application/json",
                "title": "This document",
                "length": 1024,
                "templated": True,
            }
        ]
        links = parse_links(data)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].href, "https://example.com")
        self.assertEqual(links[0].rel, "self")
        self.assertEqual(links[0].type, "application/json")
        self.assertEqual(links[0].title, "This document")
        self.assertEqual(links[0].length, 1024)
        self.assertTrue(links[0].templated)

    def test_mime_type_property(self):
        data = [
            {
                "href": "https://example.com",
                "rel": "self",
                "type": "application/json; charset=utf-8",
                "title": "This document",
                "length": 1024,
                "templated": True,
            }
        ]
        links = parse_links(data)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].type, "application/json; charset=utf-8")
        self.assertEqual(links[0].mime_type, "application/json")

        links[0].type = "Application/JSON"
        self.assertEqual(links[0].mime_type, "application/json")
        links[0].type = ""
        self.assertEqual(links[0].mime_type, "")

    def test_missing_fields_use_defaults(self):
        data = [{"href": "https://example.com", "rel": "self"}]
        links = parse_links(data)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].href, "https://example.com")
        self.assertEqual(links[0].rel, "self")
        self.assertEqual(links[0].type, "")
        self.assertEqual(links[0].title, "")
        self.assertIsNone(links[0].length)
        self.assertFalse(links[0].templated)

    def test_empty_dict_returns_default_link(self):
        links = parse_links([{}])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].href, "")
        self.assertEqual(links[0].rel, "")
        self.assertEqual(links[0].type, "")
        self.assertEqual(links[0].title, "")
        self.assertIsNone(links[0].length)
        self.assertFalse(links[0].templated)

    def test_unknown_fields_ignored(self):
        data = [{"href": "https://example.com", "rel": "self", "unknown_key": "value"}]
        links = parse_links(data)
        self.assertEqual(len(links), 1)
        self.assertFalse(hasattr(links[0], "unknown_key"))

    def test_profiles_are_parsed(self):
        data = [
            {
                "href": "https://example.com",
                "rel": "items",
                "profile": [
                    "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
                    "http://www.opengis.net/spec/ogcapi-features-2/1.0/req/crs",
                ],
            }
        ]
        links = parse_links(data)
        self.assertEqual(len(links[0].profiles), 2)
        self.assertListEqual(
            links[0].profiles,
            [
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
                "http://www.opengis.net/spec/ogcapi-features-2/1.0/req/crs",
            ],
        )

    def test_missing_profiles_return_empty_list(self):
        data = [{"href": "https://example.com", "rel": "self"}]
        links = parse_links(data)
        self.assertListEqual(links[0].profiles, [])

    def test_string_profile_returns_list(self):
        data = [{"href": "https://example.com", "rel": "self", "profile": "not-a-list"}]
        links = parse_links(data)
        self.assertListEqual(links[0].profiles, ["not-a-list"])

    def test_profiles_converted_to_stringe(self):
        data = [{"href": "https://example.com", "rel": "self", "profile": [1, 2]}]
        links = parse_links(data)
        self.assertEqual(links[0].profiles, ["1", "2"])

    def test_landing_page_fixture(self):
        data = load_from_file("landing_page.json")

        links = parse_links(data["links"])
        self.assertEqual(len(links), 5)

        rels = [lnk.rel for lnk in links]
        self.assertIn("self", rels)
        self.assertIn("conformance", rels)
        self.assertIn("data", rels)

    def test_links_with_profiles_fixture(self):
        data = load_from_file("links_with_profiles.json")

        links = parse_links(data)
        geo_json_link = next(lnk for lnk in links if lnk.type == "application/geo+json")
        self.assertEqual(len(geo_json_link.profiles), 2)


class TestFindLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = [
            {"href": "https://example.com/html", "rel": "self", "type": "text/html"},
            {
                "href": "https://example.com/json",
                "rel": "self",
                "type": "application/json",
            },
            {
                "href": "https://example.com/xml",
                "rel": "self",
                "type": "application/xml",
            },
        ]
        cls._links_with_types = parse_links(data)

        data = load_from_file("landing_page.json")
        cls._landing_page_links = parse_links(data["links"])

    def test_empty_links_returns_none(self):
        self.assertIsNone(find_link([], "self"))

    def test_no_matching_rel_returns_none(self):
        data = [{"href": "https://example.com", "rel": "self"}]
        links = parse_links(data)
        self.assertIsNone(find_link(links, "conformance"))

    def test_href_returned_for_exact_match(self):
        data = [{"href": "https://example.com/conformance", "rel": "conformance"}]
        links = parse_links(data)
        self.assertEqual(
            find_link(links, "conformance"), "https://example.com/conformance"
        )

    def test_no_preferable_types_returns_single_href(self):
        data = [
            {"href": "https://example.com", "rel": "self", "type": "application/json"}
        ]
        links = parse_links(data)
        self.assertEqual(find_link(links, "self"), "https://example.com")
        self.assertEqual(find_link(links, "self"), "https://example.com", [])

    def test_none_preferable_types_same_as_empty_list(self):
        data = [
            {"href": "https://example.com", "rel": "self", "type": "application/json"}
        ]
        links = parse_links(data)
        result_none = find_link(links, "self", None)
        result_empty = find_link(links, "self", [])
        self.assertEqual(result_none, result_empty)

    def test_first_preferred_type_picked(self):
        result = find_link(
            self._links_with_types, "self", ["application/json", "text/html"]
        )
        self.assertEqual(result, "https://example.com/json")

    def test_second_preferred_type_used_when_first_missing(self):
        result = find_link(
            self._links_with_types, "self", ["application/geo+json", "text/html"]
        )
        self.assertEqual(result, "https://example.com/html")

    def test_non_preferred_type_returned_when_preffered_missed(self):
        result = find_link(self._links_with_types, "self", ["application/geo+json"])
        # None of the three links match the preferred type, so the first
        # encountered matching rel is returned.
        self.assertEqual(result, "https://example.com/html")

    def test_preference_order_matters(self):
        result = find_link(
            self._links_with_types, "self", ["application/json", "text/html"]
        )
        self.assertEqual(result, "https://example.com/json")
        result = find_link(
            self._links_with_types, "self", ["text/html", "application/json"]
        )
        self.assertEqual(result, "https://example.com/html")

    def test_first_link_with_same_type_is_returned(self):
        data = [
            {
                "href": "https://first.example.com",
                "rel": "self",
                "type": "application/json",
            },
            {
                "href": "https://second.example.com",
                "rel": "self",
                "type": "application/json",
            },
        ]
        links = parse_links(data)
        self.assertEqual(
            find_link(links, "self", ["application/json"]), "https://first.example.com"
        )

    def test_first_link_with_non_preferred_type_returned_when_no_preferred_type_matched(
        self,
    ):
        data = [
            {"href": "https://first.example.com", "rel": "self", "type": "text/html"},
            {"href": "https://second.example.com", "rel": "self", "type": "text/html"},
        ]
        links = parse_links(data)
        self.assertEqual(
            find_link(links, "self", ["application/json"]), "https://first.example.com"
        )

    def test_find_self_json_preferred(self):
        href = find_link(
            self._landing_page_links, "self", ["application/json", "text/html"]
        )
        self.assertEqual(href, "https://ogcapi.example.com/")

    def test_find_self_html_preferred(self):
        href = find_link(
            self._landing_page_links, "self", ["text/html", "application/json"]
        )
        self.assertEqual(href, "https://ogcapi.example.com/")

    def test_find_conformance_link(self):
        href = find_link(self._landing_page_links, "conformance", ["application/json"])
        self.assertEqual(href, "https://ogcapi.example.com/conformance")

    def test_find_data_link(self):
        href = find_link(self._landing_page_links, "data", ["application/json"])
        self.assertEqual(href, "https://ogcapi.example.com/collections")

    def test_find_missed_rel_returns_none(self):
        self.assertIsNone(find_link(self._landing_page_links, "items"))


class TestParseExtent(unittest.TestCase):
    def test_invalid_inputs_return_none(self):
        invalid_inputs = [
            (None, "None"),
            ("extent", "string"),
            (13, "int"),
            ([], "empty list"),
            ({}, "empty dict"),
        ]
        for payload, description in invalid_inputs:
            with self.subTest(msg=f"Testing invalid input: {description}"):
                self.assertIsNone(parse_extent(payload))

    def test_missing_spatial_extent_returns_none(self):
        self.assertIsNone(parse_extent({"temporal": {}}))

    def test_spatial_not_a_dict_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": "not-a-dict"}))

    def test_empty_spatial_dict_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": {}}))

    def test_missing_bbox_returns_none(self):
        self.assertIsNone(
            parse_extent(
                {"spatial": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}}
            )
        )

    def test_bbox_not_a_list_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": {"bbox": "not-a-list"}}))

    def test_empty_bbox_list_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": {"bbox": []}}))

    def test_first_bbox_entry_not_a_list_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": {"bbox": ["not-a-list"]}}))

    def test_first_bbox_entry_too_short_returns_none(self):
        self.assertIsNone(parse_extent({"spatial": {"bbox": [[-9.51, 36.96, -6.19]]}}))

    def test_non_numeric_coords_return_none(self):
        self.assertIsNone(parse_extent({"spatial": {"bbox": [["a", "b", "c", "d"]]}}))

    def test_none_coords_return_none(self):
        self.assertIsNone(
            parse_extent({"spatial": {"bbox": [[None, None, None, None]]}})
        )

    def test_valid_2d_bbox_parsed_correctly(self):
        extent = {
            "spatial": {
                "bbox": [[-9.51, 36.96, -6.19, 42.15]],
                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            }
        }
        result = parse_extent(extent)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.x_min, -9.51)
        self.assertAlmostEqual(result.y_min, 36.96)
        self.assertAlmostEqual(result.x_max, -6.19)
        self.assertAlmostEqual(result.y_max, 42.15)
        self.assertEqual(result.crs, "http://www.opengis.net/def/crs/OGC/1.3/CRS84")

    def test_only_first_bbox_entry_is_used(self):
        extent = {
            "spatial": {
                "bbox": [
                    [-9.51, 36.96, -6.19, 42.15],
                    [-180.0, -90.0, 180.0, 90.0],
                ],
                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            }
        }
        result = parse_extent(extent)
        self.assertAlmostEqual(result.x_min, -9.51)
        self.assertAlmostEqual(result.x_max, -6.19)

    def test_missing_crs_defaults_to_empty_string(self):
        extent = {"spatial": {"bbox": [[-9.51, 36.96, -6.19, 42.15]]}}
        result = parse_extent(extent)
        self.assertIsNotNone(result)
        self.assertEqual(result.crs, "")

    def test_valid_3d_bbox_parsed_correctly(self):
        extent = {
            "spatial": {
                "bbox": [[-9.51, 36.96, 0.0, -6.19, 42.15, 1000.0]],
                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            }
        }
        result = parse_extent(extent)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.x_min, -9.51)
        self.assertAlmostEqual(result.y_min, 36.96)
        self.assertAlmostEqual(result.x_max, -6.19)
        self.assertAlmostEqual(result.y_max, 42.15)

    def test_string_coords_are_coerced_to_float(self):
        extent = {
            "spatial": {
                "bbox": [["-9.51", "36.96", "-6.19", "42.15"]],
                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            }
        }
        result = parse_extent(extent)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.x_min, -9.51)
        self.assertAlmostEqual(result.y_max, 42.15)


class TestParseCollection(unittest.TestCase):
    def test_invalid_inputs_return_none(self):
        invalid_inputs = [
            (None, "None"),
            ("collection", "string"),
            (13, "int"),
            ([], "empty list"),
        ]
        for payload, description in invalid_inputs:
            with self.subTest(msg=f"Testing invalid input: {description}"):
                self.assertIsNone(parse_collection(payload))

    def test_missing_id_returns_none(self):
        self.assertIsNone(parse_collection({"title": "No ID"}))

    def test_empty_id_returns_none(self):
        self.assertIsNone(parse_collection({"id": "", "title": "Empty ID"}))

    def test_record_item_type_returns_none(self):
        data = load_from_file("collection_record_type.json")
        self.assertIsNone(parse_collection(data))

    def test_record_item_type_skipped_even_with_capabilities(self):
        data = {
            "id": "my-records",
            "itemType": "record",
            "links": [
                {
                    "type": "application/geo+json",
                    "rel": "items",
                    "href": "https://example.com/collections/my-records/items?f=json",
                }
            ],
        }
        self.assertIsNone(parse_collection(data))

    def test_feature_item_type_is_not_skipped(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertIsNotNone(result)

    def test_absent_item_type_is_not_skipped(self):
        data = load_from_file("collection_maps_only.json")
        result = parse_collection(data)
        self.assertIsNotNone(result)

    def test_unknown_item_type_is_not_skipped(self):
        data = {
            "id": "future-type",
            "itemType": "coverage",
            "links": [],
        }
        result = parse_collection(data)
        self.assertIsNotNone(result)

    def test_id_and_title_parsed(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertEqual(result.id, "municipios")
        self.assertEqual(result.title, "CAOP2025 Municípios")
        self.assertIn("Municípios", result.description)

    def test_missing_title_falls_back_to_id(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertEqual(result.title, "my-collection")

    def test_missing_description_defaults_to_empty_string(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertEqual(result.description, "")

    def test_extent_parsed_from_fixture(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertIsNotNone(result.extent)
        self.assertAlmostEqual(result.extent.x_min, -9.51)
        self.assertAlmostEqual(result.extent.y_min, 36.96)
        self.assertAlmostEqual(result.extent.x_max, -6.19)
        self.assertAlmostEqual(result.extent.y_max, 42.15)

    def test_missing_extent_results_in_none(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertIsNone(result.extent)

    def test_supported_crs_parsed(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertEqual(len(result.supported_crs), 4)
        self.assertListEqual(
            result.supported_crs,
            [
                "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                "http://www.opengis.net/def/crs/EPSG/0/4326",
                "http://www.opengis.net/def/crs/EPSG/0/3857",
                "http://www.opengis.net/def/crs/EPSG/0/3763",
            ],
        )

    def test_missing_crs_defaults_to_crs84(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertEqual(
            result.supported_crs, ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
        )

    def test_storage_crs_parsed(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertEqual(
            result.storage_crs, "http://www.opengis.net/def/crs/EPSG/0/3763"
        )

    def test_missing_storage_crs_is_none(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertIsNone(result.storage_crs)

    def test_features_capability_detected(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertIn(CollectionType.FEATURES, result.capabilities)

    def test_features_href_points_to_items_endpoint(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        href = result.capabilities[CollectionType.FEATURES]
        self.assertEqual(
            href,
            "https://ogcapi.dgterritorio.gov.pt/collections/municipios/items?f=json",
        )

    def test_features_only_collection_has_no_tiles_or_maps(self):
        data = load_from_file("collection_features_only.json")
        result = parse_collection(data)
        self.assertNotIn(CollectionType.TILES_VECTOR, result.capabilities)
        self.assertNotIn(CollectionType.TILES_RASTER, result.capabilities)
        self.assertNotIn(CollectionType.MAPS, result.capabilities)

    def test_features_and_vector_tiles_both_detected(self):
        data = load_from_file("collection_features_and_vector_tiles.json")
        result = parse_collection(data)
        self.assertIn(CollectionType.FEATURES, result.capabilities)
        self.assertIn(CollectionType.TILES_VECTOR, result.capabilities)

    def test_features_href_correct_in_mixed_collection(self):
        data = load_from_file("collection_features_and_vector_tiles.json")
        result = parse_collection(data)
        self.assertEqual(
            result.capabilities[CollectionType.FEATURES],
            "https://ogcapi.dgterritorio.gov.pt/collections/nuts1/items?f=json",
        )

    def test_tiles_vector_href_points_to_tilesets_listing(self):
        data = load_from_file("collection_features_and_vector_tiles.json")
        result = parse_collection(data)
        href = result.capabilities[CollectionType.TILES_VECTOR]
        self.assertEqual(
            href, "https://ogcapi.dgterritorio.gov.pt/collections/nuts1/tiles?f=json"
        )

    def test_mixed_collection_has_no_raster_tiles_or_maps(self):
        data = load_from_file("collection_features_and_vector_tiles.json")
        result = parse_collection(data)
        self.assertNotIn(CollectionType.TILES_RASTER, result.capabilities)
        self.assertNotIn(CollectionType.MAPS, result.capabilities)

    def test_maps_capability_detected(self):
        data = load_from_file("collection_maps_only.json")
        result = parse_collection(data)
        self.assertIn(CollectionType.MAPS, result.capabilities)

    def test_maps_href_points_to_map_endpoint(self):
        data = load_from_file("collection_maps_only.json")
        result = parse_collection(data)
        href = result.capabilities[CollectionType.MAPS]
        self.assertEqual(
            href, "https://ogcapi.dgterritorio.gov.pt/collections/ortos-rgb/map?f=png"
        )

    def test_maps_only_collection_has_no_features_or_tiles(self):
        data = load_from_file("collection_maps_only.json")
        result = parse_collection(data)
        self.assertNotIn(CollectionType.FEATURES, result.capabilities)
        self.assertNotIn(CollectionType.TILES_VECTOR, result.capabilities)
        self.assertNotIn(CollectionType.TILES_RASTER, result.capabilities)

    def test_no_capability_links_results_in_empty_capabilities(self):
        data = {
            "id": "empty-caps",
            "title": "No capabilities",
            "links": [
                {
                    "type": "application/json",
                    "rel": "self",
                    "href": "https://example.com/collections/empty-caps?f=json",
                }
            ],
        }
        result = parse_collection(data)
        self.assertIsNotNone(result)
        self.assertEqual(result.capabilities, {})

    def test_geojson_preferred_over_html_for_features(self):
        data = {
            "id": "pref-test",
            "links": [
                {
                    "type": "text/html",
                    "rel": "items",
                    "href": "https://example.com/items?f=html",
                },
                {
                    "type": "application/geo+json",
                    "rel": "items",
                    "href": "https://example.com/items?f=json",
                },
            ],
        }
        result = parse_collection(data)
        self.assertEqual(
            result.capabilities[CollectionType.FEATURES],
            "https://example.com/items?f=json",
        )

    def test_json_preferred_over_html_for_vector_tiles(self):
        data = {
            "id": "pref-test",
            "links": [
                {
                    "type": "text/html",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-vector",
                    "href": "https://example.com/tiles?f=html",
                },
                {
                    "type": "application/json",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/tilesets-vector",
                    "href": "https://example.com/tiles?f=json",
                },
            ],
        }
        result = parse_collection(data)
        self.assertEqual(
            result.capabilities[CollectionType.TILES_VECTOR],
            "https://example.com/tiles?f=json",
        )


class TestParseTilesets(unittest.TestCase):
    def test_invalid_inputs_return_empty_list(self):
        invalid_inputs = [
            ({}, "empty dict"),
            (None, "None"),
            ("links", "string"),
            ([], "empty list"),
            (13, "number"),
        ]

        for payload, description in invalid_inputs:
            with self.subTest(msg=f"Testing invalid input: {description}"):
                self.assertListEqual(parse_tilesets(payload), [])

    def test_missing_tilesets_key_returns_empty_list(self):
        self.assertEqual(parse_tilesets({"links": []}), [])

    def test_non_list_tilesets_value_returns_empty_list(self):
        self.assertEqual(parse_tilesets({"tilesets": "bad"}), [])

    def test_empty_tilesets_list_returns_empty_list(self):
        self.assertEqual(parse_tilesets({"tilesets": []}), [])

    def test_invalid_tileset_values_retuns_empty_list(self):
        data = {"tilesets": ["not-a-dict", None, 13]}
        self.assertEqual(parse_tilesets(data), [])

    def test_tms_id_extracted_from_url(self):
        data = create_tileset_data(
            TMS_WEB_MERCATOR_QUAD,
            "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
        )
        result = parse_tilesets(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tms_id, TMS_WEB_MERCATOR_QUAD)

    def test_tms_id_extracted_from_urn(self):
        data = create_tileset_data(
            TMS_WEB_MERCATOR_QUAD,
            "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
            True,
        )
        result = parse_tilesets(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tms_id, TMS_WEB_MERCATOR_QUAD)

    def test_tms_id_extracted_from_tile_matrix_set_uri(self):
        data = {
            "tilesets": [
                {
                    "tileMatrixSetURI": "https://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "item",
                            "href": "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
                            "templated": True,
                        },
                    ],
                }
            ]
        }
        result = parse_tilesets(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tms_id, TMS_WEB_MERCATOR_QUAD)

    def test_tms_id_extracted_from_tiling_scheme_link(self):
        data = {
            "tilesets": [
                {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "tiling-scheme",
                            "href": "https://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                        },
                        {
                            "rel": "item",
                            "href": "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
                            "templated": True,
                        },
                    ],
                }
            ]
        }
        result = parse_tilesets(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tms_id, TMS_WEB_MERCATOR_QUAD)

    def test_tileset_without_tms_id_is_skipped(self):
        data = {
            "tilesets": [
                {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                    "links": [
                        {
                            "rel": "item",
                            "href": "https://example.com/{tileMatrix}/{tileRow}/{tileCol}",
                            "templated": True,
                        }
                    ],
                }
            ]
        }
        self.assertEqual(parse_tilesets(data), [])

    def test_web_mercator_placeholders_replaced_with_qgis_xyz(self):
        template = (
            "https://example.com/WebMercatorQuad/{tileMatrix}/{tileRow}/{tileCol}"
        )
        data = create_tileset_data(TMS_WEB_MERCATOR_QUAD, template)
        result = parse_tilesets(data)
        self.assertEqual(
            result[0].url_template, "https://example.com/WebMercatorQuad/{z}/{y}/{x}"
        )

    def test_tile_matrix_set_id_placeholder_replaced(self):
        template = (
            "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        )
        data = create_tileset_data(TMS_WEB_MERCATOR_QUAD, template)
        result = parse_tilesets(data)
        url = result[0].url_template
        self.assertNotIn("{tileMatrixSetId}", url)
        self.assertIn("WebMercatorQuad", url)

    def test_non_web_mercator_tms_returns_empty_list(self):
        template = (
            "https://example.com/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        )
        data = create_tileset_data("ETRS89-TM35FIN", template)
        result = parse_tilesets(data)
        self.assertEqual(result, [])

    def test_root_item_link_has_priority_over_tileset(self):
        root_template = "https://example.com/root/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        tileset_template = "https://example.com/tileset/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        data = {
            "links": [{"rel": "item", "href": root_template, "templated": True}],
            "tilesets": [
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [
                        {"rel": "item", "href": tileset_template, "templated": True}
                    ],
                }
            ],
        }
        result = parse_tilesets(data)
        self.assertIn("tileset", result[0].url_template)
        self.assertNotIn("root", result[0].url_template)

    def test_root_item_link_used_when_tileset_item_link_missed(self):
        root_template = "https://example.com/root/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}"
        data = {
            "links": [{"rel": "item", "href": root_template, "templated": True}],
            "tilesets": [
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [],
                }
            ],
        }
        result = parse_tilesets(data)
        self.assertIn("root", result[0].url_template)

    def test_tileset_with_no_template_skipped(self):
        data = {
            "tilesets": [
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [],
                }
            ]
        }
        result = parse_tilesets(data)
        self.assertEqual(result, [])

    def test_preferred_mime_type_link_is_selected(self):
        data = {
            "tilesets": [
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [
                        {
                            "rel": "item",
                            "type": "image/png",
                            "href": "https://example.com/png/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
                        },
                        {
                            "rel": "item",
                            "type": "application/vnd.mapbox-vector-tile",
                            "href": "https://example.com/mvt/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}",
                        },
                    ],
                }
            ]
        }
        result = parse_tilesets(
            data, preferable_types=["application/vnd.mapbox-vector-tile"]
        )
        self.assertIn("mvt", result[0].url_template)

    def test_multiple_tilesets_all_parsed(self):
        data = {
            "tilesets": [
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [
                        {
                            "rel": "item",
                            "href": f"https://example.com/{TMS_WEB_MERCATOR_QUAD}/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}",
                        }
                    ],
                },
                {
                    "tileMatrixSetURI": f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{TMS_WEB_MERCATOR_QUAD}",
                    "links": [
                        {
                            "rel": "item",
                            "href": f"https://test.com/{TMS_WEB_MERCATOR_QUAD}/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}",
                        }
                    ],
                },
            ]
        }
        result = parse_tilesets(data)
        self.assertEqual(len(result), 2)
        tms_ids = {ts.tms_id for ts in result}
        self.assertEqual(tms_ids, {TMS_WEB_MERCATOR_QUAD})


class TestCreateUriParts(unittest.TestCase):
    LANDING_PAGE = "https://example.com"
    COLLECTION_ID = "testCollection"
    TILE_URL = "https://example.com/tiles/{z}/{y}/{x}"

    def _create_tileset(self, url: str = TILE_URL) -> TileSet:
        """Creates a TileSet object."""
        return TileSet(tms_id=TMS_WEB_MERCATOR_QUAD, url_template=url)

    def test_features_uri_contains_url_and_typename(self):
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.FEATURES
        )
        self.assertEqual(parts["url"], self.LANDING_PAGE)
        self.assertEqual(parts["typename"], self.COLLECTION_ID)

    def test_features_uri_has_no_extra_keys_without_auth(self):
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.FEATURES
        )
        self.assertSetEqual(set(parts.keys()), {"url", "typename", "srsname"})

    def test_features_uri_includes_authcfg_when_provided(self):
        parts = create_uri_parts(
            self.COLLECTION_ID,
            self.LANDING_PAGE,
            CollectionType.FEATURES,
            auth_cfg="authId",
        )
        self.assertEqual(parts["authcfg"], "authId")

    def test_raster_tiles_uri_contains_template_url(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.TILES_RASTER, ts
        )
        self.assertEqual(parts["url"], self.TILE_URL)

    def test_raster_tiles_uri_type_is_xyz(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.TILES_RASTER, ts
        )
        self.assertEqual(parts["type"], "xyz")

    def test_raster_tiles_uri_includes_authcfg_when_provided(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID,
            self.LANDING_PAGE,
            CollectionType.TILES_RASTER,
            ts,
            auth_cfg="authId",
        )
        self.assertEqual(parts["authcfg"], "authId")

    def test_vector_tiles_uri_contains_template_url(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.TILES_VECTOR, ts
        )
        self.assertEqual(parts["url"], self.TILE_URL)

    def test_vector_tiles_uri_type_is_xyz(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.TILES_VECTOR, ts
        )
        self.assertEqual(parts["type"], "xyz")

    def test_vector_tiles_uri_includes_authcfg_when_provided(self):
        ts = self._create_tileset()
        parts = create_uri_parts(
            self.COLLECTION_ID,
            self.LANDING_PAGE,
            CollectionType.TILES_VECTOR,
            ts,
            auth_cfg="authId",
        )
        self.assertEqual(parts["authcfg"], "authId")

    def test_unsupported_collection_type_returns_empty_dict(self):
        parts = create_uri_parts(
            self.COLLECTION_ID, self.LANDING_PAGE, CollectionType.MAPS
        )
        self.assertEqual(parts, {})

    def test_authcfg_not_present_when_not_supplied(self):
        for ct in (CollectionType.FEATURES, CollectionType.TILES_VECTOR):
            with self.subTest(collection_type=ct):
                ts = self._create_tileset()
                parts = create_uri_parts(
                    self.COLLECTION_ID, self.LANDING_PAGE, ct, tileset=ts
                )
                self.assertNotIn("authcfg", parts)


class TestHashData(unittest.TestCase):
    def test_returns_eight_characters(self):
        value = "http://example.com/ogc"
        result = hash_data(value)

        self.assertEqual(len(result), 8)

    def test_hash_contains_valid_characters(self):
        value = "http://example.com/ogc"
        result = hash_data(value)

        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_hash_correctness(self):
        self.assertEqual(hash_data("test"), "9f86d081")

    def test_hash_is_deterministic(self):
        value = "http://example.com/ogc"
        self.assertEqual(hash_data(value), hash_data(value))

    def test_different_inputs_produce_different_hashes(self):
        self.assertNotEqual(
            hash_data("http://example.com/ogc/a"), hash_data("http://example.com/ogc/b")
        )

    def test_empty_string_returns_valid_hash(self):
        self.assertEqual(len(hash_data("")), 8)

    def test_unicode_string_returns_valid_hash(self):
        self.assertEqual(len(hash_data("uñicøde_перевірка")), 8)


class TestSanitizeString(unittest.TestCase):
    def test_special_characters_collapsed(self):
        self.assertEqual(sanitize_string("osm:!!@#$layer"), "osm_layer")

    def test_empty_string_returns_fallback(self):
        self.assertEqual(sanitize_string(""), "dummy")

    def test_invalid_inputs_return_fallback(self):
        valid_inputs = [
            ("!@#$%^&*()", "special characters"),
            ("          ", "spaces only"),
        ]

        for payload, description in valid_inputs:
            with self.subTest(msg=f"Testing valid input: {description}"):
                self.assertEqual(sanitize_string(payload), "dummy")

    def test_valid_inputs_returned_unchanged(self):
        valid_inputs = [
            ("collection-123", "with dash"),
            ("collection_name", "with underscore"),
            ("simpleName", "letters only"),
            ("collection123", "alphanumeric"),
            ("1234567", "numbers only"),
        ]

        for payload, description in valid_inputs:
            with self.subTest(msg=f"Testing valid input: {description}"):
                self.assertEqual(sanitize_string(payload), payload)

    def test_non_alphanumeric_inputs_sanitized(self):
        valid_inputs = [
            ("osm:transportation", "osm_transportation", "with colon"),
            ("hydro/rivers/main", "hydro_rivers_main", "with slash"),
            ("simple name", "simple_name", "with space"),
            ("points.shp", "points_shp", "with dot"),
        ]

        for payload, expected, description in valid_inputs:
            with self.subTest(msg=f"Testing input: {description}"):
                self.assertEqual(sanitize_string(payload), expected)


class TestCachePath(unittest.TestCase):
    def _collection_segment(self, collection_id: str) -> str:
        """Helper that generates collection segment as in the cache_path()."""
        safe_id = sanitize_string(collection_id)
        return f"{safe_id}-{hash_data(collection_id)}"

    def test_cache_path_features(self):
        root = "/test/cache/directory"
        server_url = "http://example.com"
        collection_id = "osm:buildings"
        bbox_str = "1.000000,2.000000,3.000000,4.000000"
        crs = "EPSG4326"

        expected = os.path.join(
            root,
            hash_data(server_url),
            self._collection_segment(collection_id),
            crs,
            hash_data(bbox_str),
            "data.gpkg",
        )

        result = cache_path(
            root, server_url, collection_id, crs, bbox_str, CollectionType.FEATURES
        )
        self.assertEqual(result, expected)

    def test_cache_path_raster_tiles(self):
        root = "/test/cache/directory"
        server_url = "http://example.com"
        collection_id = "dem"
        bbox_str = "-10.500000,35.200000,-9.100000,40.000000"
        crs = "EPSG3857"

        expected = os.path.join(
            root,
            hash_data(server_url),
            self._collection_segment(collection_id),
            crs,
            hash_data(bbox_str),
            "data.mbtiles",
        )

        result = cache_path(
            root, server_url, collection_id, crs, bbox_str, CollectionType.TILES_RASTER
        )
        self.assertEqual(result, expected)

    def test_cache_path_vector_tiles(self):
        root = "/test/cache/directory"
        server_url = "http://example.com"
        collection_id = "nuts1"
        bbox_str = "-10.500000,35.200000,-9.100000,40.000000"
        crs = "EPSG25832"

        expected = os.path.join(
            root,
            hash_data(server_url),
            self._collection_segment(collection_id),
            crs,
            hash_data(bbox_str),
            "data.mbtiles",
        )

        result = cache_path(
            root, server_url, collection_id, crs, bbox_str, CollectionType.TILES_VECTOR
        )
        self.assertEqual(result, expected)

    def test_collection_ids_that_sanitize_identically_produce_different_paths(self):
        root = "/cache"
        server_url = "http://example.com"
        bbox_str = "0.000000,0.000000,1.000000,1.000000"
        crs = "EPSG4326"

        path_ab = cache_path(
            root, server_url, "a:b", crs, bbox_str, CollectionType.FEATURES
        )
        path_aab = cache_path(
            root, server_url, "a::b", crs, bbox_str, CollectionType.FEATURES
        )

        self.assertNotEqual(path_ab, path_aab)

    def test_collection_segment_contains_safe_id_prefix(self):
        root = "/cache"
        result = cache_path(
            root,
            "http://example.com",
            "osm:buildings",
            "EPSG4326",
            "0,0,1,1",
            CollectionType.FEATURES,
        )
        parts = result.split(os.sep)
        collection_segment = parts[3]
        self.assertTrue(collection_segment.startswith("osm_buildings-"))

    def test_features_produces_gpkg_extension(self):
        result = cache_path(
            "/c",
            "http://test.com",
            "col",
            "EPSG4326",
            "0,0,1,1",
            CollectionType.FEATURES,
        )
        self.assertTrue(result.endswith("data.gpkg"))

    def test_raster_tiles_produces_mbtiles_extension(self):
        result = cache_path(
            "/c",
            "http://test.com",
            "col",
            "EPSG3857",
            "0,0,1,1",
            CollectionType.TILES_RASTER,
        )
        self.assertTrue(result.endswith("data.mbtiles"))

    def test_vector_tiles_produces_mbtiles_extension(self):
        result = cache_path(
            "/c",
            "http://test.com",
            "col",
            "EPSG3857",
            "0,0,1,1",
            CollectionType.TILES_VECTOR,
        )
        self.assertTrue(result.endswith("data.mbtiles"))

    def test_different_server_urls_produce_different_paths(self):
        kwargs = {
            "collection_id": "col",
            "crs": "EPSG4326",
            "bbox": "0,0,1,1",
            "collection_type": CollectionType.FEATURES,
        }
        p1 = cache_path("/c", "http://server-a.com", **kwargs)
        p2 = cache_path("/c", "http://server-b.com", **kwargs)
        self.assertNotEqual(p1, p2)

    def test_different_bboxes_produce_different_paths(self):
        kwargs = {
            "server_url": "http://example.com",
            "collection_id": "col",
            "crs": "EPSG4326",
            "collection_type": CollectionType.FEATURES,
        }
        p1 = cache_path("/c", bbox="0.000000,0.000000,1.000000,1.000000", **kwargs)
        p2 = cache_path("/c", bbox="0.000000,0.000000,2.000000,2.000000", **kwargs)
        self.assertNotEqual(p1, p2)


class TestFormatTileUrl(unittest.TestCase):
    def test_basic_substitution(self):
        result = format_tile_url("{z}/{x}/{y}", 3, 5, 10, 1024)
        self.assertEqual(result, "10/3/5")

    def test_x_zero(self):
        result = format_tile_url("{z}/{x}/{y}", 0, 7, 4, 16)
        self.assertEqual(result, "4/0/7")

    def test_y_zero(self):
        result = format_tile_url("{z}/{x}/{y}", 2, 0, 3, 8)
        self.assertEqual(result, "3/2/0")

    def test_z_zero(self):
        result = format_tile_url("{z}/{x}/{y}", 0, 0, 0, 1)
        self.assertEqual(result, "0/0/0")

    def test_large_coordinates(self):
        result = format_tile_url("{z}/{x}/{y}", 131072, 98304, 18, 262144)
        self.assertEqual(result, "18/131072/98304")

    def test_full_https_url(self):
        template = "https://tiles.example.com/tilesets/dem/{z}/{x}/{y}.png"
        result = format_tile_url(template, 4, 6, 5, 32)
        self.assertEqual(result, "https://tiles.example.com/tilesets/dem/5/4/6.png")

    def test_url_with_query_parameters(self):
        template = "https://api.example.com/tiles/{z}/{x}/{y}?format=png&apikey=abc"
        result = format_tile_url(template, 1, 2, 3, 8)
        self.assertEqual(
            result, "https://api.example.com/tiles/3/1/2?format=png&apikey=abc"
        )

    def test_basic_tms_flip(self):
        result = format_tile_url("{z}/{x}/{-y}", 3, 2, 4, 8)
        self.assertEqual(result, "4/3/5")

    def test_tms_flip_y_at_zero(self):
        result = format_tile_url("{z}/{x}/{-y}", 0, 0, 2, 4)
        self.assertEqual(result, "2/0/3")

    def test_tms_flip_y_at_max(self):
        result = format_tile_url("{z}/{x}/{-y}", 0, 7, 3, 8)
        self.assertEqual(result, "3/0/0")

    def test_tms_flip_matrix_height_1(self):
        result = format_tile_url("{z}/{x}/{-y}", 0, 0, 0, 1)
        self.assertEqual(result, "0/0/0")

    def test_tms_flip_full_url(self):
        template = "https://tiles.example.com/layer/{z}/{x}/{-y}.pbf"
        result = format_tile_url(template, 10, 3, 5, 32)
        self.assertEqual(result, "https://tiles.example.com/layer/5/10/28.pbf")

    def test_tms_template_does_not_leave_literal_y_token(self):
        result = format_tile_url("{z}/{x}/{-y}", 1, 2, 3, 10)
        self.assertNotIn("{y}", result)
        self.assertNotIn("{-y}", result)

    def test_xyz_template_does_not_trigger_tms_branch(self):
        result = format_tile_url("{z}/{x}/{y}", 1, 2, 3, 10)
        self.assertEqual(result, "3/1/2")

    def test_no_token_mutation_on_unrelated_text(self):
        template = "https://example.com/{z}/{x}/{y}?style=default&tile-y=fixed"
        result = format_tile_url(template, 1, 5, 7, 128)
        self.assertEqual(result, "https://example.com/7/1/5?style=default&tile-y=fixed")


if __name__ == "__main__":
    unittest.main()
