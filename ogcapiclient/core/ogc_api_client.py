"""OGC API client.

Stateless HTTP helper that performs a discovery workflow:
landing page - conformance - collections.

Also provides methods to retrieve tilesets for a collection
and download individual tiles.
"""

from ogcapiclient.core.constants import TMS_WEB_MERCATOR_QUAD
from ogcapiclient.core.enums import ClientError, CollectionType, LogLevel
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.interfaces import Feedback, Loader, Logger
from ogcapiclient.core.models import Collection, DiscoveryResult, PreparedLayer
from ogcapiclient.core.utils import (
    create_uri_parts,
    find_link,
    parse_collection,
    parse_links,
    parse_tilesets,
)


class OgcApiClient:
    """Client for interacting with OGC API servers.

    Fetches the landing page, conformance classes, and collections
    from an OGC API endpoint and returns structured result.
    """

    def __init__(
        self,
        loader: Loader,
        logger: Logger,
        feedback: Feedback,
        auth_cfg: str | None = None,
    ) -> None:
        """Initializes the client.

        :param loader: HTTP backend that fetches and parses JSON responses.
        :type loader: Loader
        :param logger: Sink for log messages produced by the client.
        :type logger: Logger
        :param feedback: Progress and cancelation reporter.
        :type feedback: Feedback
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str | None
        """
        self.loader: Loader = loader
        self.logger: Logger = logger
        self.feedback: Feedback = feedback
        self.auth_cfg: str = auth_cfg

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
        self.logger.log(f"Discovering {url}.")
        self.feedback.set_progress(0)
        self._check_canceled()

        landing_page = self.get_landing_page(url)
        if not landing_page:
            self.logger.log("Empty body returned for landing page request.")
            raise OgcApiClientError(
                ClientError.EMPTY_RESPONSE,
                "Empty body returned for landing page request.",
            )

        self.feedback.set_progress(5)
        self._check_canceled()

        server_title = landing_page.get("title", "")

        self.logger.log("Resolving conformance and collections URLs.")

        links = parse_links(landing_page.get("links", []))
        collections_url = find_link(links, "data", ["application/json"]) or find_link(
            links, "http://www.opengis.net/def/rel/ogc/1.0/data", ["application/json"]
        )
        if not collections_url:
            self.logger.log("No collections link found on landing page.")
            raise OgcApiClientError(
                ClientError.PARSE_ERROR, "No collections link found on landing page."
            )
        self.logger.log(f"Collections link {collections_url}.")

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
                self.logger.log(f"Conformance link {conformance_url}.")
            except OgcApiClientError as e:
                self.logger.log(f"Conformance request failed: {e}.", LogLevel.WARNING)
        else:
            self.logger.log("No conformance link found on landing page.")

        self.feedback.set_progress(10)
        self._check_canceled()

        collections = self.get_collections(collections_url)
        if not collections:
            self.logger.log("Empty body returned for collections page request.")
            raise OgcApiClientError(
                ClientError.EMPTY_RESPONSE,
                "Empty body returned for collections page request.",
            )

        self.feedback.set_progress(20)
        self._check_canceled()

        self.logger.log("Parsing collections.")

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

    def prepare_layers(
        self,
        landing_page: str,
        collections: list[tuple[Collection, CollectionType]],
        crs_map: dict[str, str],
    ) -> list[PreparedLayer]:
        """Fetches tilesets and generates configurations for selected collections.

        :param landing_page: The landing page URL.
        :type landing_page: str
        :param collections: A list of tuples containing the Collection and type.
        :type collections: list[tuple[Collection, CollectionType]]
        :param crs_map: A dictionary mapping collection to requested CRS.
        :type crs_map: dicr[str, str]

        :returns: List of structured objects for creating QGIS layers.
        :rtype: list[PreparedLayer]

        :raises OgcApiClientError: If the process is canceled or hits network errors.
        """
        self.logger.log("Fetching additional details for collections.")
        prepared_layers: list[PreparedLayer] = []

        collections_count = len(collections)
        step = 100 / collections_count if collections_count > 0 else 0
        for i, (collection, collection_type) in enumerate(collections):
            self._check_canceled()

            if collection_type == CollectionType.FEATURES:
                crs = crs_map.get(collection.id)
                uri_parts = create_uri_parts(
                    collection.id,
                    landing_page,
                    collection_type,
                    crs=crs,
                    auth_cfg=self.auth_cfg,
                )
                prepared_layers.append(
                    PreparedLayer(collection.title, collection_type, uri_parts)
                )
            elif collection_type in (
                CollectionType.TILES_RASTER,
                CollectionType.TILES_VECTOR,
            ):
                tiles_url = collection.capabilities.get(collection_type)
                if not tiles_url:
                    self.logger.log(
                        f"Missing tiles URL for collection {collection.id}.",
                        LogLevel.WARNING,
                    )
                    continue

                if collection_type == CollectionType.TILES_VECTOR:
                    mime_types = [
                        "application/vnd.mapbox-vector-tile",
                        "application/x-protobuf",
                    ]
                elif collection_type == CollectionType.TILES_RASTER:
                    mime_types = ["image/png", "image/jpeg", "image/webp"]

                tilesets = self.get_tilesets(tiles_url)
                self.logger.log(f"Parsing tilesets for {collection.id}.")
                parsed_tilesets = parse_tilesets(tilesets, mime_types)
                if not parsed_tilesets:
                    self.logger.log(
                        f"No tileset found for collection {collection.id}.",
                        LogLevel.WARNING,
                    )
                    continue

                preferred_tileset = next(
                    (
                        ts
                        for ts in parsed_tilesets
                        if ts.tms_id == TMS_WEB_MERCATOR_QUAD
                    ),
                    parsed_tilesets[0],
                )
                uri_parts = create_uri_parts(
                    collection.id,
                    landing_page,
                    collection_type,
                    preferred_tileset,
                    self.auth_cfg,
                )

                prepared_layers.append(
                    PreparedLayer(
                        name=collection.title,
                        collection_type=collection_type,
                        uri_parts=uri_parts,
                        tilesets=parsed_tilesets,
                    )
                )

            self.feedback.set_progress(i * step)

        self.logger.log(f"Prepared {len(prepared_layers)} layer(s).")

        return prepared_layers

    def get_landing_page(self, url: str) -> dict:
        """Performs landing page request on an OGC API server.

        :param url: The base URL (landing page) of the OGC API server.
        :type url: str

        :returns: The raw landing page data.
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure.
        """
        self.logger.log(f"Fetching landing page: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_conformance(self, url: str) -> dict:
        """Performs conformance request on an OGC API server.

        :param url: The URL of the conformance page of the OGC API server.
        :type url: str

        :returns: The raw conformance data.
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure.
        """
        self.logger.log(f"Fetching conformance: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_collections(self, url: str) -> dict:
        """Performs collections request on an OGC API server.

        :param url: The URL of the collections page of the OGC API server.
        :type url: str

        :returns: The raw collections data.
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure.
        """
        self.logger.log(f"Fetching collections: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_tilesets(self, url: str) -> dict:
        """Performs tilesets request on an OGC API server.

        :param url: The URL of the tiles page.
        :type url: str

        :returns: The raw tilesets data.
        :rtype: dict

        :raises OgcApiClientError: On network or parse failure.
        """
        self.logger.log(f"Fetching tilesets: {url}")
        return self.loader.get_json(url, self.auth_cfg)

    def get_tile(self, url: str) -> bytes:
        """Performs tilesets request on an OGC API server.

        :param url: The URL of the tiles page.
        :type url: str

        :returns: The raw tilesets data.
        :rtype: bytes

        :raises OgcApiClientError: On network or parse failure.
        """
        return self.loader.get_data(url, self.auth_cfg)

    def _check_canceled(self) -> None:
        """Checks if operation should be terminated.

        :raises OgcApiClientError: When cancellation is requested.
        """
        if self.feedback.is_canceled():
            raise OgcApiClientError(ClientError.CANCELLED, "Operation was cancelled.")
