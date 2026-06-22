import os
import threading
import time
import unittest

from qgis.core import QgsFeedback

from ogcapiclient.core.enums import ClientError, LogLevel
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


class MockLogger:
    """Mocks the logger and stores messages for assertion."""

    def __init__(self):
        self.messages: list[tuple[LogLevel, str]] = []

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        self.messages.append((level, message))


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

    def test_get_json_returns_parsed_dict(self):
        payload = {"title": "Test", "links": []}
        self.server.handler.add_json_route("/landing", payload)

        result = self.loader.get_json(f"{self.server.base_url}/landing")
        self.assertEqual(result, payload)

    def test_get_json_sends_accept_json_header(self):
        self.server.handler.add_json_route("/landing", {})
        self.loader.get_json(f"{self.server.base_url}/landing")

        request = self.server.handler.requests[0]
        accept = request.headers.get("Accept", request.headers.get("accept", ""))
        self.assertIn("application/json", accept)

    def test_get_json_load_landing_page(self):
        self.server.handler.add_file_route(
            "/", os.path.join(TEST_DATA_PATH, "landing_page.json")
        )
        result = self.loader.get_json(f"{self.server.base_url}/")
        self.assertEqual(result["title"], "Test OGC API")

    def test_get_json_load_collections(self):
        self.server.handler.add_file_route(
            "/collections", os.path.join(TEST_DATA_PATH, "collections.json")
        )
        result = self.loader.get_json(f"{self.server.base_url}/collections")
        self.assertIn("collections", result)
        self.assertEqual(len(result["collections"]), 4)

    def test_get_json_invalid_json_raises_parse_error(self):
        self.server.handler.add_route(
            "GET", "/badjson", 200, b"not json {{{", "application/json"
        )

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/badjson")

        self.assertEqual(ctx.exception.error_code, ClientError.PARSE_ERROR)

    def test_get_josn_http_error_raises_server_error(self):
        self.server.handler.add_error_route("/missing", 404, "Not Found")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/missing")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_get_json_server_error_raises_server_error(self):
        self.server.handler.add_error_route("/broken", 500, "Internal Server Error")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/broken")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_get_json_empty_body_raises_empty_response_error(self):
        self.server.handler.add_route("GET", "/empty", 200, b"", "application/json")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json(f"{self.server.base_url}/empty")

        self.assertEqual(ctx.exception.error_code, ClientError.EMPTY_RESPONSE)

    def test_get_json_unknown_host_raises_network_error(self):
        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_json("http://does-not-exist.invalid/")

        self.assertIn(
            ctx.exception.error_code,
            (ClientError.NETWORK_ERROR, ClientError.SERVER_ERROR),
        )

    def test_get_json_cancel_mid_request_raises_cancelled(self):
        self.server.handler.add_json_route("/slow", {"ok": True}, delay=2.0)

        feedback = MockFeedback()
        loader = QgisLoader(feedback=feedback)
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
        self.assertIsNotNone(error)
        self.assertEqual(error.error_code, ClientError.CANCELLED)

    def test_get_json_pre_cancelled_feedback_cancels_immediately(self):
        self.server.handler.add_json_route("/collections", {"collections": []})

        feedback = MockFeedback()
        feedback.cancel()
        loader = QgisLoader(feedback=feedback)

        with self.assertRaises(OgcApiClientError) as ctx:
            loader.get_json(f"{self.server.base_url}/collections")

        self.assertEqual(ctx.exception.error_code, ClientError.CANCELLED)
        self.server.handler.assert_request_count(0)

    def test_get_data_returns_bytes(self):
        raw_payload = b"raw binary data or image contents"
        self.server.handler.add_route(
            "GET", "/bytes", 200, raw_payload, "application/octet-stream"
        )

        result = self.loader.get_data(f"{self.server.base_url}/bytes")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertEqual(result, raw_payload)

    def test_get_data_does_not_send_accept_header(self):
        self.server.handler.add_route(
            "GET", "/bytes", 200, b"data", "application/octet-stream"
        )
        self.loader.get_data(f"{self.server.base_url}/bytes")

        request = self.server.handler.requests[0]
        accept = request.headers.get("Accept", request.headers.get("accept", ""))
        self.assertEqual(accept, "")

    def test_get_data_http_error_raises_server_error(self):
        self.server.handler.add_error_route("/missing", 404, "Not Found")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_data(f"{self.server.base_url}/missing")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_get_data_server_error_raises_server_error(self):
        self.server.handler.add_error_route("/broken", 500, "Internal Server Error")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_data(f"{self.server.base_url}/broken")

        self.assertEqual(ctx.exception.error_code, ClientError.SERVER_ERROR)

    def test_get_data_empty_body_raises_empty_response_error(self):
        self.server.handler.add_route("GET", "/empty", 200, b"", "application/json")

        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_data(f"{self.server.base_url}/empty")

        self.assertEqual(ctx.exception.error_code, ClientError.EMPTY_RESPONSE)

    def test_get_data_unknown_host_raises_network_error(self):
        with self.assertRaises(OgcApiClientError) as ctx:
            self.loader.get_data("http://does-not-exist.invalid/")

        self.assertIn(
            ctx.exception.error_code,
            (ClientError.NETWORK_ERROR, ClientError.SERVER_ERROR),
        )

    def test_get_data_cancel_mid_request_raises_cancelled(self):
        self.server.handler.add_route(
            "GET",
            "/slow-bytes",
            200,
            b"some bytes",
            "application/octet-stream",
            delay=2.0,
        )

        feedback = MockFeedback()
        loader = QgisLoader(feedback=feedback)
        result = {}

        def run():
            try:
                loader.get_data(f"{self.server.base_url}/slow-bytes")
                result["error"] = None
            except OgcApiClientError as e:
                result["error"] = e

        thread = threading.Thread(target=run)
        thread.start()

        time.sleep(0.1)
        feedback.cancel()

        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

        error = result.get("error")
        self.assertIsNotNone(error)
        self.assertEqual(error.error_code, ClientError.CANCELLED)

    def test_get_data_pre_cancelled_feedback_cancels_immediately(self):
        self.server.handler.add_route(
            "GET", "/bytes", 200, b"abc", "application/octet-stream"
        )

        feedback = MockFeedback()
        feedback.cancel()
        loader = QgisLoader(feedback=feedback)

        with self.assertRaises(OgcApiClientError) as ctx:
            loader.get_data(f"{self.server.base_url}/collections")

        self.assertEqual(ctx.exception.error_code, ClientError.CANCELLED)
        self.server.handler.assert_request_count(0)

    def test_logger(self):
        mock_logger = MockLogger()
        loader_with_logger = QgisLoader(logger=mock_logger)

        self.server.handler.add_error_route(
            "/broken-route", 500, "Internal Server Error"
        )

        with self.assertRaises(OgcApiClientError):
            loader_with_logger.get_json(f"{self.server.base_url}/broken-route")

        self.assertTrue(len(mock_logger.messages) > 0)
        log_level, log_msg = mock_logger.messages[0]
        self.assertEqual(log_level, LogLevel.CRITICAL)
        self.assertIn("HTTP request failed", log_msg)


if __name__ == "__main__":
    unittest.main()
