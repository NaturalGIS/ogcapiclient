"""Constants shared across the OGC API client GUI."""

from ogcapiclient.core.enums import CollectionType

SUPPORTED_COLLECTIONS = frozenset(
    [CollectionType.FEATURES, CollectionType.TILES_RASTER, CollectionType.TILES_VECTOR]
)

MAXIMUM_COLUMN_WIDTH = 300
MAXIMUM_ABSTRACT_WIDTH = 150
