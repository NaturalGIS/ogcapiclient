import json
import os
import unittest

from ogcapiclient.core.utils import find_link, parse_links

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


class TestParseLinks(unittest.TestCase):
    def test_dict_returns_empty_list(self):
        self.assertListEqual(parse_links({}), [])

    def test_none_returns_empty_list(self):
        self.assertListEqual(parse_links(None), [])

    def test_string_returns_empty_list(self):
        self.assertListEqual(parse_links("links"), [])

    def test_empty_list_returns_empty_list(self):
        self.assertListEqual(parse_links([]), [])

    def test_list_with_non_dict_items(self):
        links = parse_links(["not-a-dict", 13, None])
        self.assertListEqual(links, [])

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

    def test_nprofiles_converted_to_stringe(self):
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

    def test_preference_order_metters(self):
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


if __name__ == "__main__":
    unittest.main()
