"""OGC API client.

Stateless HTTP helper that performs a discovery workflow: landing page → conformance → collections.
"""

from ogcapiclient.core.enums import ClientError, LogLevel
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.interfaces import Feedback, Loader, Logger
from ogcapiclient.core.models import DiscoveryResult
from ogcapiclient.core.utils import find_link, parse_collection, parse_links


class OgcApiClient:
    """Client for interacting with OGC API servers.

    Fetches the landing page, conformance classes, and collections from an OGC API endpoint
    and returns structured result.
    """

    def __init__(
        self, loader: Loader, logger: Logger, feedback: Feedback, auth_cfg: str = None
    ) -> None:
        """Initializes the client.

        :param loader: HTTP backend that fetches and parses JSON responses.
        :type loader: Loader
        :param logger: Sink for log messages produced by the client.
        :type logger: Logger
        :param feedback: Progress and cancelation reporter.
        :type feedback: Feedback
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        """
        self.loader = loader
        self.logger = logger
        self.feedback = feedback
        self.auth_cfg = auth_cfg

    def connect(self, url: str) -> DiscoveryResult:
        """Initiates the discovery process on an OGC API server.

        Performs a sequence of requests (landing page, conformance classes, collections)
        and returns a structured result.

        :param url: The base URL (landing page) of the OGC API server.
        :type url: str

        :returns: Structured details from the OGC API server.
        :rtype: DiscoveryResult

        :raises OgcApiClientError: On any network, decode, or parse failure, or if
        the operation is cancelled.
        """
        self.feedback.set_progress(0)
        self._check_canceled()

        landing_page = self.get_landing_page(url)
        if not landing_page:
            raise OgcApiClientError(
                ClientError.EMPTY_RESPONSE,
                "Empty body returned for landing page request.",
            )

        self.feedback.set_progress(5)
        self._check_canceled()

        server_title = landing_page.get("title", "")

        self.logger.log(f"Resolving conformace and collections URLs.")

        links = parse_links(landing_page.get("links", []))
        collections_url = find_link(links, "data", ["application/json"]) or find_link(
            links, "http://www.opengis.net/def/rel/ogc/1.0/data", ["application/json"]
        )
        if not collections_url:
            raise OgcApiClientError(
                ClientError.PARSE_ERROR, "No collections link found on landing page."
            )

        conformance_url = find_link(
            links, "conformance", ["application/json"]
        ) or find_link(
            links,
            "http://www.opengis.net/def/rel/ogc/1.0/conformance",
            ["application/json"],
        )
        conformance_classes = []
        if conformance_url:
            try:
                conformance = self.get_conformance(conformance_url)
                conformance_classes = conformance.get("conformsTo", [])
            except OgcApiClientError as e:
                self.logger.log(f"Conformance request failed: {e}", LogLevel.WARNING)
        else:
            self.logger.log(f"No conformance link found on landing page.")

        self.feedback.set_progress(10)
        self._check_canceled()

        collections = self.get_collections(collections_url)
        if not collections:
            raise OgcApiClientError(
                ClientError.EMPTY_RESPONSE,
                "Empty body returned for collections page request.",
            )

        self.feedback.set_progress(20)
        self._check_canceled()

        self.logger.log(f"Parsing collections.")

        raw_collections = collections.get("collections", [])

        parsed_collections = []
        collections_count = len(raw_collections)
        step = 80 / collections_count if collections_count > 0 else 0
        for i, col in enumerate(raw_collections):
            self._check_canceled()

            collection = parse_collection(col)
            if collection:
                parsed_collections.append(collection)

            self.feedback.set_progress(20 + i * step)

        self.logger.log(f"Found {len(parsed_collections)} collection(s).")

        self.feedback.set_progress(100)
        return DiscoveryResult(
            url=url,
            title=server_title,
            conformance=conformance_classes,
            collections=parsed_collections,
        )

    def get_landing_page(self, url: str) -> dict:
        """Performs landing page request on an OGC API server.

        :param url: The base URL (landing page) of the OGC API server.
        :type url: str

        :returns: The raw landing page data
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure.
        """
        self.logger.log(f"Fetching landing page: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_conformance(self, url: str) -> dict:
        """Performs conformance request on an OGC API server.

        :param url: The URL of the conformance page of the OGC API server.
        :type url: str

        :returns: The raw conformance data
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure..
        """
        self.logger.log(f"Fetching conformance: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_collections(self, url: str) -> dict:
        """Performs collections request on an OGC API server.

        :param url: The URL of the collections page of the OGC API server.
        :type url: str

        :returns: The raw collections data
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure..
        """
        self.logger.log(f"Fetching collections: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def _check_canceled(self) -> None:
        """Checks if operation should be terminated.

        :raises OgcApiClientError: When cancellation is requested.
        """
        if self.feedback.is_canceled():
            raise OgcApiClientError(ClientError.CANCELLED, "Operation was cancelled.")
