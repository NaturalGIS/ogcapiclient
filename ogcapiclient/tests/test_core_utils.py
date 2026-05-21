import json
import os
import unittest

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.utils import (
    find_link,
    parse_collection,
    parse_extent,
    parse_links,
)

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


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
        file_path = os.path.join(TEST_DATA_PATH, "landing_page.json")
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        links = parse_links(data["links"])
        self.assertEqual(len(links), 5)

        rels = [lnk.rel for lnk in links]
        self.assertIn("self", rels)
        self.assertIn("conformance", rels)
        self.assertIn("data", rels)

    def test_links_with_profiles_fixture(self):
        file_path = os.path.join(TEST_DATA_PATH, "links_with_profiles.json")
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

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

        file_path = os.path.join(TEST_DATA_PATH, "landing_page.json")
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_record_type.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertIsNotNone(result)

    def test_absent_item_type_is_not_skipped(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_maps_only.json"), encoding="utf-8"
        ) as f:
            data = json.load(f)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
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
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertEqual(
            result.storage_crs, "http://www.opengis.net/def/crs/EPSG/0/3763"
        )

    def test_missing_storage_crs_is_none(self):
        data = {"id": "my-collection", "links": []}
        result = parse_collection(data)
        self.assertIsNone(result.storage_crs)

    def test_features_capability_detected(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertIn(CollectionType.FEATURES, result.capabilities)

    def test_features_href_points_to_items_endpoint(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        href = result.capabilities[CollectionType.FEATURES]
        self.assertEqual(
            href,
            "https://ogcapi.dgterritorio.gov.pt/collections/municipios/items?f=json",
        )

    def test_features_only_collection_has_no_tiles_or_maps(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_only.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertNotIn(CollectionType.TILES_VECTOR, result.capabilities)
        self.assertNotIn(CollectionType.TILES_RASTER, result.capabilities)
        self.assertNotIn(CollectionType.MAPS, result.capabilities)

    def test_features_and_vector_tiles_both_detected(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_and_vector_tiles.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertIn(CollectionType.FEATURES, result.capabilities)
        self.assertIn(CollectionType.TILES_VECTOR, result.capabilities)

    def test_features_href_correct_in_mixed_collection(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_and_vector_tiles.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertEqual(
            result.capabilities[CollectionType.FEATURES],
            "https://ogcapi.dgterritorio.gov.pt/collections/nuts1/items?f=json",
        )

    def test_tiles_vector_href_points_to_tilesets_listing(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_and_vector_tiles.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        href = result.capabilities[CollectionType.TILES_VECTOR]
        self.assertEqual(
            href, "https://ogcapi.dgterritorio.gov.pt/collections/nuts1/tiles?f=json"
        )

    def test_mixed_collection_has_no_raster_tiles_or_maps(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_features_and_vector_tiles.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertNotIn(CollectionType.TILES_RASTER, result.capabilities)
        self.assertNotIn(CollectionType.MAPS, result.capabilities)

    def test_maps_capability_detected(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_maps_only.json"), encoding="utf-8"
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        self.assertIn(CollectionType.MAPS, result.capabilities)

    def test_maps_href_points_to_map_endpoint(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_maps_only.json"), encoding="utf-8"
        ) as f:
            data = json.load(f)
        result = parse_collection(data)
        href = result.capabilities[CollectionType.MAPS]
        self.assertEqual(
            href, "https://ogcapi.dgterritorio.gov.pt/collections/ortos-rgb/map?f=png"
        )

    def test_maps_only_collection_has_no_features_or_tiles(self):
        with open(
            os.path.join(TEST_DATA_PATH, "collection_maps_only.json"), encoding="utf-8"
        ) as f:
            data = json.load(f)
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


if __name__ == "__main__":
    unittest.main()
