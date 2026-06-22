"""Dataclasses shared across the OGC API client core."""

from dataclasses import dataclass, field

from ogcapiclient.core.enums import CollectionType


@dataclass
class Link:
    """A single link object as defined by OGC API."""

    href: str = ""
    """The URI of the linked resource."""
    rel: str = ""
    """The link relation type."""
    type: str = ""
    """The media type of the linked resource."""
    title: str = ""
    """A human-readable label for the link."""
    templated: bool = False
    """Indicates if the href string is a URI template containing variables."""
    length: int | None = None
    """The content length of the linked resource in bytes, if available."""
    profiles: list[str] = field(default_factory=list)
    """A list of schemas or profiles that the linked resource conforms to."""

    @property
    def mime_type(self) -> str:
        """Returns a normalized, parameter-free MIME type."""
        if not self.type:
            return ""
        return self.type.lower().split(";")[0].strip()


@dataclass
class BoundingBox:
    """A spatial bounding box defining geographic extent."""

    x_min: float = 0
    """The minimum X coordinate."""
    y_min: float = 0
    """The minimum Y coordinate."""
    x_max: float = 0
    """The maximum X coordinate."""
    y_max: float = 0
    """The maximum Y coordinate."""
    crs: str = ""
    """The coordinate reference system of the extent."""

    def __iter__(self):
        """Allows unpacking the bounding box as a tuple."""
        return iter((self.x_min, self.y_min, self.x_max, self.y_max))


@dataclass
class Collection:
    """A single collection as defined by OGC API."""

    id: str
    """The unique identifier of the collection."""
    title: str
    """A human-readable title for the collection."""
    extent: BoundingBox
    """The spatial extent of the data within this collection."""
    capabilities: dict[CollectionType, str]
    """Supported OGC API building blocks and their endpoints."""
    supported_crs: list[str] = field(default_factory=list)
    """List of CRSs supported for querying or output."""
    description: str = ""
    """A detailed text description of the collection's contents."""
    storage_crs: str | None = None
    """The CRS used to natively store the data."""


@dataclass
class DiscoveryResult:
    """The complete result of the OGC API server discovery process."""

    url: str
    """The landing-page URL that was queried."""
    title: str
    """Server title from the landing page."""
    conformance: list[str]
    """Conformance classes reported by the /conformance endpoint."""
    collections: list[Collection]
    """All parsed geospatial collections available on the server."""


@dataclass
class TileSet:
    """A single Tile Matrix Set available for a collection."""

    tms_id: str
    """Identifier of the Tile Matrix Set."""
    url_template: str
    """Tile URL template."""


@dataclass
class PreparedLayer:
    """All data needed to add a single layer to the QGIS project."""

    name: str
    """Human-readable name for the layer."""
    collection_type: CollectionType
    """Type of the collection."""
    uri_parts: dict[str, str]
    """Primary datasource URI parts used to create layer URI."""
    tilesets: list[TileSet] = field(default_factory=list)
    """All available tilesets (populated for tiles collections only)."""

    @property
    def provider_key(self) -> str:
        """Returns the QGIS provider key based on the collection type."""
        if self.collection_type == CollectionType.FEATURES:
            return "oapif"
        if self.collection_type == CollectionType.TILES_RASTER:
            return "wms"
        if self.collection_type == CollectionType.TILES_VECTOR:
            return "xyzvectortiles"
        return ""


@dataclass
class OfflineItem:
    """Defines a collection prepared for offline use."""

    collection: Collection
    """The collection to download."""
    collection_type: CollectionType
    """Type of the collection."""
    file_path: str
    """Full path to the downloaded data."""
    crs: str
    """Coordinate reference system to use for Features collection."""
    bbox: object
    """Bounding box for spatial filtering."""
    cache_exists: bool
    """Whether a cached file already exists."""
    tile_count: int = 0
    """Estimated total number of tiles across all zoom levels."""
    tile_ranges: dict[int, object] | None = None
    """Tile ranges to download for Features collections."""


@dataclass
class OfflineDownload:
    """Defines a collection for offline download."""

    collection: Collection
    """The collection to download."""
    collection_type: CollectionType
    """Type of the collection."""
    file_path: str
    """Full path to the file where the downloaded data should be saved."""
    bbox: object | None = None
    """Bounding box for spatial filtering."""
    crs: str | None = None
    """Coordinate reference system to use for Features collection."""
    tile_ranges: dict[int, object] | None = None
    """Tile ranges to download for Features collections."""


@dataclass
class DownloadedLayer:
    """All data needed to add downloaded layer to the QGIS project."""

    name: str
    """Human-readable layer name."""
    collection_type: CollectionType
    """Type of the downloaded collection."""
    file_path: str
    """Absolute path to the downloaded file."""

    @property
    def provider_key(self) -> str:
        """Returns the QGIS provider key based on the collection type."""
        if self.collection_type == CollectionType.FEATURES:
            return "ogr"
        if self.collection_type == CollectionType.TILES_RASTER:
            return "wms"
        if self.collection_type == CollectionType.TILES_VECTOR:
            return "xyzvectortiles"
        return ""
