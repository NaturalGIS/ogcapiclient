import json
import os
import threading
import time
import unittest

from qgis.core import QgsFeedback

from ogcapiclient.core.enums import ClientError
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.qgis_backend.loader import QgisLoader
from ogcapiclient.tests.mocked_webserver import MockedWebServer

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


class MockFeedback(QgsFeedback):
    """A lightweight mock of the Feedback."""

    def is_canceled(self) -> bool:
        return self.isCanceled()

    def set_progress(self, progress: float) -> None:
        pass


class TestQgisLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = MockedWebServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        super().tearDownClass()

    def setUp(self):
        self.server.handler.reset()
        self.loader = QgisLoader()

    def test_returns_parsed_dict(self):
        payload = {"title": "Test", "links": []}
        self.server.handler.add_json_route("/landing", payload)

        result = self.loader.get_json(f"{self.server.base_url}/landing")
        self.assertEqual(result, payload)

    def test_sends_accept_json_header(self):
        self.server.handler.add_json_route("/landing", {})
        self.loader.get_json(f"{self.server.base_url}/landing")

        request = self.server.handler.requests[0]
        accept = request.headers.get("Accept", request.headers.get("accept", ""))
        self.assertIn("application/json", accept)

    def test_load_landing_page(self):
        self.server.handler.add_file_route(
            "/", os.path.join(TEST_DATA_PATH, "landing_page.json")
        )
        result = self.loader.get_json(f"{self.server.base_url}/")
        self.assertEqual(result["title"], "Test OGC API")

    def test_load_collections(self):
        self.server.handler.add_file_route(
            "/collections", os.path.join(TEST_DATA_PATH, "collections.json")
        )
        result = self.loader.get_json(f"{self.server.base_url}/collections")
        self.assertIn("collections", result)
        self.assertEqual(len(result["collections"]), 4)

    def test_http_client_error_raises_server_error(self):
        self.server.handler.add_error_route("/missing", 404, "Not Found")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/missing")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_http_server_error_raises_server_error(self):
        self.server.handler.add_error_route("/broken", 500, "Internal Server Error")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/broken")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_empty_body_raises_parse_error(self):
        self.server.handler.add_route("GET", "/empty", 200, b"", "application/json")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/empty")

        self.assertEqual(ctx.exception.error_code, ClientError.PARSE_ERROR)

    def test_invalid_json_raises_parse_error(self):
        self.server.handler.add_route(
            "GET", "/badjson", 200, b"not json {{{", "application/json"
        )

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/badjson")

        self.assertEqual(ctx.exception.error_code, ClientError.PARSE_ERROR)

    def test_unknown_host_raises_network_error(self):
        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json("http://does-not-exist.invalid/")

        self.assertIn(
            ctx.exception.error_code,
            (ClientError.NETWORK_ERROR, ClientError.SERVER_ERROR),
        )

    def test_cancel_mid_request_raises_cancelled(self):
        self.server.handler.add_json_route("/slow", {"ok": True}, delay=2.0)

        feedback = MockFeedback()
        loader = QgisLoader(feedback)
        result = {}

        def run():
            try:
                loader.get_json(f"{self.server.base_url}/slow")
                result["error"] = None
            except OgcApiClientError as e:
                result["error"] = e

        thread = threading.Thread(target=run)
        thread.start()

        time.sleep(0.1)
        feedback.cancel()

        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "Request thread did not finish in time")

        error = result.get("error")
        self.assertIsNotNone(error, "Expected an OgcApiClientError but got none")
        self.assertEqual(error.error_code, ClientError.CANCELLED)

    def test_pre_cancelled_feedback_cancels_immediately(self):
        self.server.handler.add_json_route("/collections", {"collections": []})

        feedback = MockFeedback()
        feedback.cancel()
        loader = QgisLoader(feedback)

        with self.assertRaises(OgcApiClientError) as ctx:
            loader.get_json(f"{self.server.base_url}/collections")

        self.assertEqual(ctx.exception.error_code, ClientError.CANCELLED)
        self.server.handler.assert_request_count(0)


if __name__ == "__main__":
    unittest.main()
