"""Constants shared across the OGC API client core."""

REL_FEATURES_SHORT = "items"
REL_FEATURES_FULL = "http://www.opengis.net/def/rel/ogc/1.0/items"
REL_TILES_VECTOR_SHORT = "tilesets-vector"
REL_TILES_VECTOR_FULL = "http://www.opengis.net/def/rel/ogc/1.0/tilesets-vector"
REL_TILES_RASTER_SHORT = "tilesets-map"
REL_TILES_RASTER_FULL = "http://www.opengis.net/def/rel/ogc/1.0/tilesets-map"
REL_MAPS_SHORT = "map"
REL_MAPS_FULL = "http://www.opengis.net/def/rel/ogc/1.0/map"
REL_COVERAGES_SHORT = "coverage"
REL_COVERAGES_FULL = "http://www.opengis.net/def/rel/ogc/1.0/coverage"

FEATURES_MIME_TYPES = ["application/geo+json", "application/json"]
TILES_MIME_TYPES = ["application/json"]
MAPS_MIME_TYPES = ["image/png", "image/jpeg", "image/webp"]

TMS_WEB_MERCATOR_QUAD = "WebMercatorQuad"

OGC_TILE_MATRIX = "{tileMatrix}"
OGC_TILE_ROW = "{tileRow}"
OGC_TILE_COL = "{tileCol}"
OGC_TILE_MATRIX_SET_ID = "{tileMatrixSetId}"

QGIS_X = "{x}"
QGIS_Y = "{y}"
QGIS_Z = "{z}"
