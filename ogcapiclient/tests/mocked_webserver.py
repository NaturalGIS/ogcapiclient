"""Minimal mock HTTP server for plugin tests.

Provides a route-based request handler so the same endpoint can be hit multiple times
without re-registration.
"""

import json
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional


@dataclass
class LoggedRequest:
    """A log record for a single HTTP request received by the server."""

    method: str
    path: str
    headers: dict


@dataclass
class ServerReply:
    """A HTTP response to return for a matched route."""

    status: int
    body: bytes
    content_type: str
    delay: float = 0.0


class RouteHandler:
    """Maps (METHOD, path) pairs to ServerReply instances.

    Route matching is case-sensitive on both method and path.  The same
    route may be requested any number of times; every request is recorded
    in requests for later assertion.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], ServerReply] = {}
        self.requests: list[LoggedRequest] = []

    def add_route(
        self,
        method: str,
        path: str,
        status: int,
        body: bytes,
        content_type: str,
        delay: float = 0.0,
    ) -> None:
        """Registers a route.

        :param method: HTTP method (e.g. ``"GET"``).
        :param path: URL path including leading slash (e.g. ``"/collections"``).
        :param status: HTTP status code to return.
        :param body: Raw response body bytes.
        :param content_type: Value of the ``Content-Type`` response header.
        :param delay: Seconds to sleep before sending the response.
        """
        self.routes[(method.upper(), path)] = ServerReply(
            status=status,
            body=body,
            content_type=content_type,
            delay=delay,
        )

    def add_json_route(
        self, path: str, body: dict, status: int = 200, delay: float = 0.0
    ) -> None:
        """Serialises body as JSON and registers a GET route.

        :param path: URL path.
        :param body: Python dict that will be JSON-serialised.
        :param status: HTTP status code (default 200).
        :param delay: Optional artificial delay in seconds.
        """
        encoded = json.dumps(body).encode("utf-8")
        self.add_route("GET", path, status, encoded, "application/json", delay)

    def add_file_route(
        self,
        path: str,
        file_path: str,
        content_type: str = "application/json",
        status: int = 200,
        delay: float = 0.0,
    ) -> None:
        """Registers a GET route whose body is read from file_path on disk.

        :param path: URL path.
        :param file_path: Absolute path to a file whose contents become the body.
        :param content_type: Content-Type header value.
        :param status: HTTP status code.
        :param delay: Optional artificial delay in seconds.
        """
        with open(file_path, "rb") as fh:
            body = fh.read()
        self.add_route("GET", path, status, body, content_type, delay)

    def add_error_route(self, path: str, status: int, message: str = "") -> None:
        """Registers route with error responses (4xx / 5xx).

        :param path: URL path.
        :param status: HTTP error status code.
        :param message: Optional plain-text body.
        """
        self.add_route("GET", path, status, message.encode("utf-8"), "text/plain")

    @property
    def recorded_requests(self) -> list[LoggedRequest]:
        """All requests received since the last reset call."""
        return list(self.requests)

    def assert_requested(self, method: str, path: str) -> None:
        """Asserts that at least one request matched metho and path.

        :raises AssertionError: If no matching request was recorded.
        """
        method = method.upper()
        matches = [r for r in self.requests if r.method == method and r.path == path]
        assert matches, (
            f"Expected at least one {method} {path} request, but recorded requests were: {[(r.method, r.path) for r in self.requests]}"
        )

    def assert_request_count(self, count: int) -> None:
        """Asserts that exactly count requests were received in total.

        :raises AssertionError: If the count does not match.
        """
        actual = len(self.requests)
        assert actual == count, (
            f"Expected {count} request(s) but got {actual}: {[(r.method, r.path) for r in self.requests]}"
        )

    def assert_not_requested(self, method: str, path: str) -> None:
        """Asserts that no request matched method and path.

        :raises AssertionError: If a matching request was recorded.
        """
        method = method.upper()
        matches = [r for r in self.requests if r.method == method and r.path == path]
        assert not matches, (
            f"Expected no {method} {path} request, but one was recorded."
        )

    def reset(self) -> None:
        """Clears recorded requests and registered routes."""
        self.routes.clear()
        self.requests.clear()

    def dispatch(self, method: str, path: str, request: BaseHTTPRequestHandler) -> None:
        """Dispatches request to the matching route or returns 500.

        :param method: HTTP method of the incoming request.
        :param path: URL path of the incoming request.
        :param request: The BaseHTTPRequestHandler instance.
        """
        clean_path = path.split("?")[0]

        self.requests.append(
            LoggedRequest(
                method=method.upper(), path=path, headers=dict(request.headers)
            )
        )

        reply = self.routes.get((method.upper(), clean_path))
        if reply is None:
            request.send_error(
                500,
                f"No route registered for {method} {path}. Registered: {list(self.routes.keys())}",
            )
            return

        if reply.delay > 0:
            time.sleep(reply.delay)

        body = reply.body or b""
        request.send_response(reply.status)
        request.send_header("Content-Type", reply.content_type)
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        if body:
            try:
                request.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError) as e:
                pass


class _DispatchHandler(BaseHTTPRequestHandler):
    """Request handler that forwards every GET to RouteHandler.dispatch."""

    route_handler: RouteHandler | None = None

    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        self.route_handler.dispatch("GET", self.path, self)


class MockedWebServer:
    """A lightweight HTTP server for use in tests. Can be used as a context manager."""

    def __init__(self) -> None:
        self.handler = RouteHandler()
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None
        self._port: int = 0

    def start(self) -> int:
        """Starts the server on a random available port.

        :returns: The TCP port the server is listening on.
        :rtype: int
        """
        handler_class = type(
            "_BoundDispatchHandler",
            (_DispatchHandler,),
            {"route_handler": self.handler},
        )
        self._server = HTTPServer(("127.0.0.1", 0), handler_class)
        self._port = self._server.server_address[1]

        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._port

    def stop(self) -> None:
        """Shuts down the server and joins the background thread."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def port(self) -> int:
        """The TCP port the server is listening on."""
        return self._port

    @property
    def base_url(self) -> str:
        """Root URL of the server, e.g. http://127.0.0.1:54321."""
        return f"http://127.0.0.1:{self._port}"

    def __enter__(self) -> "MockedWebServer":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
