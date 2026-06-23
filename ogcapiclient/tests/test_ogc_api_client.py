import unittest

from ogcapiclient.core.constants import TMS_WEB_MERCATOR_QUAD
from ogcapiclient.core.enums import ClientError, CollectionType, LogLevel
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.ogc_api_client import OgcApiClient
from ogcapiclient.tests.mocks import MockLoader, MockLogger
from ogcapiclient.tests.utils import (
    create_collection,
    load_from_file,
    raw_tileset,
)


class MockFeedback:
    """Mocks the feedback object to track progress and simulate cancellation."""

    def __init__(self, cancel_at_progress: float = None):
        self.cancel_at_progress = cancel_at_progress
        self._is_canceled = False
        self.progress = 0.0
        self.progress_history = []

    def set_progress(self, progress: float) -> None:
        self.progress = progress
        self.progress_history.append(progress)

    def is_canceled(self) -> bool:
        if (
            self.cancel_at_progress is not None
            and self.progress >= self.cancel_at_progress
        ):
            return True
        return self._is_canceled


class TestOgcApiClient(unittest.TestCase):
    def setUp(self):
        self.base_url = "https://ogcapi.example.com"
        self.auth_cfg = "test_auth_id"

        self.valid_landing_page = {
            "title": "Test OGC API",
            "links": [
                {
                    "rel": "conformance",
                    "type": "application/json",
                    "href": f"{self.base_url}/conformance",
                },
                {
                    "rel": "data",
                    "type": "application/json",
                    "href": f"{self.base_url}/collections",
                },
            ],
        }
        self.valid_conformance = {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/req/core",
                "http://www.opengis.net/spec/ogcapi-common-1/1.0/req/oas30",
            ]
        }
        self.valid_collections = load_from_file("collections.json")

        self.loader = MockLoader(
            {
                self.base_url: self.valid_landing_page,
                f"{self.base_url}/conformance": self.valid_conformance,
                f"{self.base_url}/collections": self.valid_collections,
            }
        )
        self.logger = MockLogger()
        self.feedback = MockFeedback()
        self.client = OgcApiClient(
            self.loader, self.logger, self.feedback, auth_cfg=self.auth_cfg
        )

    def test_successful_connection(self):
        result = self.client.connect(self.base_url)
        self.assertEqual(result.url, self.base_url)
        self.assertEqual(result.title, "Test OGC API")

    def test_ogc_api_calls_order(self):
        _ = self.client.connect(self.base_url)

        called_urls = [call[0] for call in self.loader.calls]
        self.assertEqual(
            called_urls,
            [
                self.base_url,
                f"{self.base_url}/conformance",
                f"{self.base_url}/collections",
            ],
        )

    def test_auth_cfg_passed_to_loader(self):
        self.client.connect(self.base_url)
        for _, auth_cfg in self.loader.calls:
            self.assertEqual(auth_cfg, self.auth_cfg)

    def test_progress_reporting(self):
        self.client.connect(self.base_url)
        self.assertEqual(self.feedback.progress_history[0], 0)
        self.assertEqual(self.feedback.progress_history[-1], 100)
        self.assertEqual(
            self.feedback.progress_history, sorted(self.feedback.progress_history)
        )

    def test_empty_landing_page_raises_error(self):
        self.loader.responses[self.base_url] = {}
        with self.assertRaises(OgcApiClientError) as context:
            self.client.connect(self.base_url)
        self.assertEqual(context.exception.error_code, ClientError.EMPTY_RESPONSE)

    def test_landing_page_request_failure_raises_error(self):
        self.loader.responses[self.base_url] = OgcApiClientError(
            ClientError.SERVER_ERROR, "500 Error"
        )
        with self.assertRaises(OgcApiClientError) as context:
            self.client.connect(self.base_url)
        self.assertEqual(context.exception.error_code, ClientError.SERVER_ERROR)

    def test_missing_conformance_link_ignored(self):
        self.loader.responses[self.base_url] = {
            "title": "No Conformance Link",
            "links": [
                {
                    "rel": "data",
                    "type": "application/json",
                    "href": f"{self.base_url}/collections",
                }
            ],
        }
        result = self.client.connect(self.base_url)
        self.assertEqual(result.conformance, [])
        self.assertTrue(
            any(
                "No conformance link found on landing page." in msg
                for _, msg in self.logger.messages
            )
        )

    def test_conformance_request_fails_safely(self):
        self.loader.responses[f"{self.base_url}/conformance"] = OgcApiClientError(
            ClientError.SERVER_ERROR, "500 Error"
        )
        result = self.client.connect(self.base_url)
        warnings = [
            msg for level, msg in self.logger.messages if level == LogLevel.WARNING
        ]
        self.assertTrue(any("Conformance request failed" in msg for msg in warnings))
        self.assertEqual(result.conformance, [])

    def test_empty_conformance_list(self):
        self.loader.responses[f"{self.base_url}/conformance"] = {"conformsTo": []}
        result = self.client.connect(self.base_url)
        self.assertEqual(result.conformance, [])

    def test_conformance_classes_parsed(self):
        result = self.client.connect(self.base_url)
        self.assertEqual(len(result.conformance), 2)
        self.assertCountEqual(result.conformance, self.valid_conformance["conformsTo"])

    def test_missing_collections_link_raises_error(self):
        self.loader.responses[self.base_url] = {
            "title": "No Data Link",
            "links": [{"rel": "conformance", "href": f"{self.base_url}/conformance"}],
        }
        with self.assertRaises(OgcApiClientError) as context:
            self.client.connect(self.base_url)
        self.assertEqual(context.exception.error_code, ClientError.PARSE_ERROR)

    def test_empty_collections_response_raises_error(self):
        self.loader.responses[f"{self.base_url}/collections"] = {}
        with self.assertRaises(OgcApiClientError) as context:
            self.client.connect(self.base_url)
        self.assertEqual(context.exception.error_code, ClientError.EMPTY_RESPONSE)
        self.assertEqual(
            "Empty body returned for collections page request.",
            context.exception.message,
        )

    def test_collection_request_failure_raises_error(self):
        self.loader.responses[f"{self.base_url}/collections"] = OgcApiClientError(
            ClientError.SERVER_ERROR, "503 Error"
        )
        with self.assertRaises(OgcApiClientError) as context:
            self.client.connect(self.base_url)
        self.assertEqual(context.exception.error_code, ClientError.SERVER_ERROR)

    def test_missing_collections_key_returns_empty_list(self):
        self.loader.responses[f"{self.base_url}/collections"] = {"links": []}
        result = self.client.connect(self.base_url)
        self.assertEqual(result.collections, [])

    def test_collections_with_unsupported_types_return_empty_list(self):
        self.loader.responses[f"{self.base_url}/collections"] = {
            "collections": [
                {"id": "catalogue-a", "itemType": "record", "links": []},
                {"id": "catalogue-b", "itemType": "record", "links": []},
            ]
        }
        result = self.client.connect(self.base_url)
        self.assertEqual(result.collections, [])

    def test_collections_parsed(self):
        result = self.client.connect(self.base_url)
        self.assertEqual(len(result.collections), 3)
        collection_ids = [c.id for c in result.collections]
        self.assertCountEqual(collection_ids, ["municipios", "nuts1", "ortos-rgb"])

    def test_connect_cancellation(self):
        checkpoints = {
            0: "Before landing page",
            5: "After landing page",
            10: "After conformance (before collections fetch)",
            20: "Before parsing loop",
            25: "During parsing loop (assuming >0 collections)",
        }

        for threshold, description in checkpoints.items():
            with self.subTest(msg=f"Cancel at {threshold}%: {description}"):
                loader = MockLoader(
                    {
                        self.base_url: self.valid_landing_page,
                        f"{self.base_url}/conformance": self.valid_conformance,
                        f"{self.base_url}/collections": self.valid_collections,
                    }
                )
                logger = MockLogger()
                feedback = MockFeedback(cancel_at_progress=threshold)
                client = OgcApiClient(loader, logger, feedback)

                with self.assertRaises(OgcApiClientError) as context:
                    client.connect(self.base_url)

                self.assertEqual(context.exception.error_code, ClientError.CANCELLED)

                if threshold == 0:
                    self.assertEqual(len(loader.calls), 0)

    def test_features_layer_prepared_without_loader_call(self):
        collection = create_collection()
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(len(self.loader.calls), 0)

    def test_features_layer_has_correct_name(self):
        collection = create_collection(title="test-features")
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result[0].name, "test-features")

    def test_features_layer_collection_type_is_features(self):
        collection = create_collection()
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result[0].collection_type, CollectionType.FEATURES)

    def test_features_uri_parts_contain_url_and_typename(self):
        collection = create_collection("municipios", "Municípios")
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result[0].uri_parts["url"], self.base_url)
        self.assertEqual(result[0].uri_parts["typename"], "municipios")

    def test_features_tilesets_list_is_empty(self):
        collection = create_collection()
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result[0].tilesets, [])

    def test_vector_tiles_layer_fetches_tilesets_from_server(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        called_urls = [url for url, _ in self.loader.calls]
        self.assertIn(tiles_url, called_urls)

    def test_vector_tiles_layer_prepared_with_correct_name(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        collection = create_collection(
            "nuts1", "NUTS 1", CollectionType.TILES_VECTOR, tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result[0].name, "NUTS 1")

    def test_vector_tiles_layer_tilesets_are_populated(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertGreater(len(result[0].tilesets), 0)

    def test_vector_tiles_prefers_web_mercator_quad(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertIn(TMS_WEB_MERCATOR_QUAD, result[0].uri_parts["url"])

    def test_vector_tiles_without_web_mercator_tileset_skipped(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset("ETRS89-TM35FIN")
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(len(result), 0)

    def test_collection_with_missing_tiles_url_is_skipped(self):
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=""
        )
        collection.capabilities = {}
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result, [])
        warnings = [
            msg for level, msg in self.logger.messages if level == LogLevel.WARNING
        ]
        self.assertTrue(any("Missing tiles URL" in msg for msg in warnings))

    def test_collection_with_empty_tilesets_response_is_skipped(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = {"tilesets": []}
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertEqual(result, [])
        warnings = [
            msg for level, msg in self.logger.messages if level == LogLevel.WARNING
        ]
        self.assertTrue(any("No tileset found" in msg for msg in warnings))

    def test_tilesets_request_failure_raises_error(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = OgcApiClientError(
            ClientError.SERVER_ERROR, "503"
        )
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        with self.assertRaises(OgcApiClientError) as context:
            self.client.prepare_layers(
                self.base_url,
                [(collection, CollectionType.TILES_VECTOR)],
                {collection.id: "EPSG:4326"},
            )
        self.assertEqual(context.exception.error_code, ClientError.SERVER_ERROR)

    def test_multiple_collections_all_prepared(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        features_collection = create_collection(
            "municipios", "Municípios", CollectionType.FEATURES
        )
        tiles_collection = create_collection(
            "nuts1", "NUTS 1", CollectionType.TILES_VECTOR, tiles_url
        )
        result = self.client.prepare_layers(
            self.base_url,
            [
                (features_collection, CollectionType.FEATURES),
                (tiles_collection, CollectionType.TILES_VECTOR),
            ],
            {features_collection.id: "EPSG:4326"},
        )
        self.assertEqual(len(result), 2)
        names = {layer.name for layer in result}
        self.assertEqual(names, {"Municípios", "NUTS 1"})

    def test_progress_reported_during_prepare_layers(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.TILES_VECTOR)],
            {collection.id: "EPSG:4326"},
        )
        self.assertGreater(len(self.feedback.progress_history), 0)

    def test_cancellation_during_prepare_layers_raises_error(self):
        tiles_url = f"{self.base_url}/collections/nuts1/tiles?f=json"
        self.loader.responses[tiles_url] = raw_tileset()
        self.feedback._is_canceled = True
        collection = create_collection(
            collection_type=CollectionType.TILES_VECTOR, capabilities_url=tiles_url
        )
        with self.assertRaises(OgcApiClientError) as ctx:
            self.client.prepare_layers(
                self.base_url,
                [(collection, CollectionType.TILES_VECTOR)],
                {collection.id: "EPSG:4326"},
            )
        self.assertEqual(ctx.exception.error_code, ClientError.CANCELLED)

    def test_prepared_layer_count_is_logged(self):
        collection = create_collection()
        self.client.prepare_layers(
            self.base_url,
            [(collection, CollectionType.FEATURES)],
            {collection.id: "EPSG:4326"},
        )
        self.assertTrue(
            any("Prepared" in msg and "layer" in msg for _, msg in self.logger.messages)
        )


if __name__ == "__main__":
    unittest.main()
