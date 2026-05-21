"""Enumerations shared across the OGC API client core."""

from enum import Enum, auto


class LogLevel(Enum):
    """Severity level for log messages emitted by the plugin."""

    INFO = auto()
    """informational message."""
    WARNING = auto()
    """Non-fatal situation that may affect results."""
    CRITICAL = auto()
    """Critical error that prevents completion of the current operation."""
    SUCCESS = auto()
    """Successful completion of the operation."""


class ClientError(Enum):
    """Error codes used in the OgcApiClientError exceptions."""

    NO_ERROR = auto()
    """No error occurred.  Not used in exceptions."""
    NETWORK_ERROR = auto()
    """Network failure, e.g. DNS, TCP or SSL error."""
    TIMEOUT_ERROR = auto()
    """No response within the configured timeout."""
    SERVER_ERROR = auto()
    """Server returned an HTTP error status."""
    EMPTY_RESPONSE = auto()
    """Server returned an empty body."""

    CANCELLED = auto()
    """Operation was cancelled by the user."""

    DECODE_ERROR = auto()
    """Data could not be decoded as UTF-8."""
    PARSE_ERROR = auto()
    """Data could not be parsed (e.g. not valid JSON) or a required field is absent."""


class CollectionType(Enum):
    """Type of an OGC API collection."""

    FEATURES = auto()
    """OGC API - Features collection."""
    TILES_RASTER = auto()
    """OGC API - Tiles collection serving raster tiles."""
    TILES_VECTOR = auto()
    """OGC API - Tiles collection serving vector tiles."""
    MAPS = auto()
    """OGC API - Maps collection."""
    COVERAGES = auto()
    """OGC API - Coverages collection."""
    UNKNOWN = auto()
    """Unknown collection type or type could not be determined."""
