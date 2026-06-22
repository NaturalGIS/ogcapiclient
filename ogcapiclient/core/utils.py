"""Core utilities and helpers."""

import hashlib
import os
import re

from ogcapiclient.core.constants import (
    FEATURES_MIME_TYPES,
    MAPS_MIME_TYPES,
    OGC_TILE_COL,
    OGC_TILE_MATRIX,
    OGC_TILE_MATRIX_SET_ID,
    OGC_TILE_ROW,
    QGIS_INVERTED_Y,
    QGIS_X,
    QGIS_Y,
    QGIS_Z,
    REL_COVERAGES_FULL,
    REL_COVERAGES_SHORT,
    REL_FEATURES_FULL,
    REL_FEATURES_SHORT,
    REL_MAPS_FULL,
    REL_MAPS_SHORT,
    REL_TILES_RASTER_FULL,
    REL_TILES_RASTER_SHORT,
    REL_TILES_VECTOR_FULL,
    REL_TILES_VECTOR_SHORT,
    TILES_MIME_TYPES,
    TMS_WEB_MERCATOR_QUAD,
)
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import BoundingBox, Collection, Link, TileSet

SKIP_ITEM_TYPES = frozenset({"record"})


def parse_links(links: list[dict]) -> list[Link]:
    """Parses the links JSON object into a list of Link objects.

    :param links:
    :type links: list[dict]
    :returns: A list of structured objects describing links.
    :rtype: list[Link]
    """
    parsed_links: list[Link] = []

    if not isinstance(links, list):
        return parsed_links

    for i in links:
        if not isinstance(i, dict):
            continue

        link = Link(
            href=str(i.get("href", "")),
            rel=str(i.get("rel", "")),
            type=str(i.get("type", "")),
            title=str(i.get("title", "")),
        )

        templated = i.get("templated")
        if isinstance(templated, bool):
            link.templated = templated

        length = i.get("length")
        if isinstance(length, (int, float)):
            link.length = int(length)

        profiles = i.get("profile")
        if isinstance(profiles, list):
            link.profiles = [str(p) for p in profiles]
        elif isinstance(profiles, str):
            link.profiles = [profiles]

        parsed_links.append(link)

    return parsed_links


def find_link(
    links: list[Link], rel: str, preferable_types: list[str] | None = None
) -> str | None:
    """Finds the href of the best-matching link.

     :param links: List of parsed links.
     :type links: list[Link]
    :param rel: The rel value to match.
    :type rel: str
    :param preferable_types: Ordered list of preferred MIME types.
    :type preferable_types: list[str]
    :returns: The URL of the best match or an empty string.
    :rtype: str, None

    """
    if preferable_types is None:
        preferable_types = []

    best_href = None
    best_priority = float("inf")

    for link in links:
        if link.rel == rel:
            mime = link.mime_type
            priority = (
                preferable_types.index(mime)
                if mime in preferable_types
                else len(preferable_types)
            )

            if priority < best_priority:
                best_href = link.href
                best_priority = priority
    return best_href


def parse_extent(extent: dict) -> BoundingBox | None:
    """Parses a raw extent dictionary into a BoundingBox object.

    :param extent: Raw extent dictionary.
    :type links: dict
    :returns: A BoundingBox built from the first bbox entry, or None if the data is absent or malformed.
    :rtype: BoundingBox | None
    """
    if not isinstance(extent, dict) or not extent:
        return None

    spatial_extent = extent.get("spatial", {})
    if not isinstance(spatial_extent, dict) or not spatial_extent:
        return None

    crs = spatial_extent.get("crs", "")

    bboxes = spatial_extent.get("bbox", [])
    if not isinstance(bboxes, list) or len(bboxes) == 0:
        return None

    first = bboxes[0]
    if not isinstance(first, list) or len(first) < 4:
        return None

    if len(first) == 6:
        x_min, y_min, z_min, x_max, y_max, z_max = first
    else:
        x_min, y_min, x_max, y_max = first

    try:
        return BoundingBox(
            x_min=float(x_min),
            y_min=float(y_min),
            x_max=float(x_max),
            y_max=float(y_max),
            crs=crs,
        )
    except (TypeError, ValueError) as e:
        return None


def parse_collection(collection: dict) -> Collection | None:
    """Parses a raw collection dictionary into a Collection object.

    :param data: Raw collection dictionary.
    :type links: dict
    :returns: Structured information about collection.
    :rtype: Collection
    """
    if not isinstance(collection, dict):
        return None

    cid = collection.get("id", "")
    if not cid:
        return None

    item_type = str(collection.get("itemType", "")).lower().strip()
    if item_type in SKIP_ITEM_TYPES:
        return None

    title = str(collection.get("title", "") or cid)
    description = str(collection.get("description", "") or "")
    bbox = parse_extent(collection.get("extent", {}))

    crs = collection.get("crs", [])
    if isinstance(crs, list):
        supported_crs = [str(i) for i in crs]
    else:
        supported_crs = []

    if not supported_crs:
        supported_crs = ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]

    crs = str(collection.get("storageCrs", ""))
    storage_crs = crs if crs else None

    capabilities: dict[CollectionType, str] = {}

    links = parse_links(collection.get("links", []))

    def _find_href(
        short_rel: str, full_rel: str, preferable_types: list[str]
    ) -> str | None:
        return find_link(links, short_rel, preferable_types) or find_link(
            links, full_rel, preferable_types
        )

    features_href = _find_href(
        REL_FEATURES_SHORT, REL_FEATURES_FULL, FEATURES_MIME_TYPES
    )
    if features_href:
        capabilities[CollectionType.FEATURES] = features_href

    tiles_vector_href = _find_href(
        REL_TILES_VECTOR_SHORT, REL_TILES_VECTOR_FULL, TILES_MIME_TYPES
    )
    if tiles_vector_href:
        capabilities[CollectionType.TILES_VECTOR] = tiles_vector_href

    tiles_raster_href = _find_href(
        REL_TILES_RASTER_SHORT, REL_TILES_RASTER_FULL, TILES_MIME_TYPES
    )
    if tiles_raster_href:
        capabilities[CollectionType.TILES_RASTER] = tiles_raster_href

    map_href = _find_href(REL_MAPS_SHORT, REL_MAPS_FULL, MAPS_MIME_TYPES)
    if map_href:
        capabilities[CollectionType.MAPS] = map_href

    coverage_href = _find_href(REL_COVERAGES_SHORT, REL_COVERAGES_FULL, [])
    if coverage_href:
        capabilities[CollectionType.COVERAGES] = coverage_href

    return Collection(
        id=cid,
        title=title,
        description=description,
        extent=bbox,
        capabilities=capabilities,
        supported_crs=supported_crs,
        storage_crs=storage_crs,
    )


def get_tms_id(tileset: dict) -> str | None:
    """Extracts the tile matrix set identifier from the tileset dictionary.

    :param tilset: Raw tileset dictionary.
    :type tileset: dict
    :returns: Tile matrix set ID.
    :rtype: str
    """

    href = tileset.get("tileMatrixSetURI", "")
    if href:
        if href.startswith("urn:"):
            return str(href).strip().split(":")[-1]
        return str(href).rstrip("/").split("/")[-1]

    links = parse_links(tileset.get("links", []))
    href = find_link(links, "tiling-scheme") or find_link(links, "self")
    if href:
        if href.startswith("urn:"):
            return str(href).strip().split(":")[-1]
        return str(href).rstrip("/").split("/")[-1]

    return None


def create_template_url(template: str, tms_id: str) -> str:
    """Creates a QGIS-ready templated tiles URL from an OGC API templated link.

    :param template: OGC API templated URL.
    :type templaye: str
    :param tms_id: TMS ID.
    :type tms_id: str
    :returns: Tiles URL that can be used in QGIS.
    :rtype: str
    """
    url = template.replace(OGC_TILE_MATRIX_SET_ID, tms_id)
    url = url.replace(OGC_TILE_MATRIX, QGIS_Z)
    url = url.replace(OGC_TILE_ROW, QGIS_Y)
    url = url.replace(OGC_TILE_COL, QGIS_X)
    return url


def parse_tilesets(data: dict, preferable_types: list[str] = None) -> list[TileSet]:
    """Parses OGC API Tiles response into a list of TileSet objects.

    :param data: Raw tilesets dictionary.
    :type data: dict
    :param preferable_types: Ordered list of preferred MIME types.
    :type preferable_types: list[str]
    :returns: A list of structured objects describing links.
    :rtype: list[Link]
    """
    parsed_tilesets: list[TileSet] = []

    if not isinstance(data, dict):
        return parsed_tilesets

    links = parse_links(data.get("links", []))
    root_templated_url = find_link(links, "item", preferable_types)

    tilesets = data.get("tilesets", [])
    if not isinstance(tilesets, list):
        return parsed_tilesets

    for tileset in tilesets:
        if not isinstance(tileset, dict):
            continue

        tms_id = get_tms_id(tileset)
        if not tms_id:
            continue

        if tms_id != TMS_WEB_MERCATOR_QUAD:
            continue

        tileset_links = parse_links(tileset.get("links", []))
        templated_url = (
            find_link(tileset_links, "item", preferable_types) or root_templated_url
        )
        if templated_url is None:
            continue

        url = create_template_url(templated_url, tms_id)
        parsed_tilesets.append(TileSet(tms_id=tms_id, url_template=url))

    return parsed_tilesets


def create_uri_parts(
    collection_id: str,
    landing_page_url: str,
    collection_type: CollectionType,
    tileset: TileSet | None = None,
    crs: str | None = None,
    auth_cfg: str | None = None,
) -> dict[str, str]:
    """Creates dictionary with parts required to build a connection string for collection.

    :param collection_id: Collection ID.
    :type collection_id: str
    :param landing_page_url: Landing page URL.
    :type landing_page_url: str
    :param collection_type: Type of the collection.
    :type collection_type: CollectionType
    :param tileset: Tile matrix set to use. Only needed for Tiles collections.
    :type tileset: Tileset | None
    :param crs: A coordinate reference system used for loading collection..
    :type crs: str | None
    :param auth_cfg: QGIS authentication configuration ID.
    :type auth_cfg: str | None
    :returns: A dictionary with data source URI building blocks.
    :rtype: dict[str, str]
    """
    parts = {}
    if collection_type == CollectionType.FEATURES:
        parts = {"url": landing_page_url, "typename": collection_id, "srsname": crs}
    elif collection_type == CollectionType.TILES_RASTER:
        parts = {"url": tileset.url_template, "type": "xyz"}
    elif collection_type == CollectionType.TILES_VECTOR:
        parts = {"url": tileset.url_template, "type": "xyz"}

    if auth_cfg:
        parts["authcfg"] = auth_cfg

    return parts


def hash_data(value: str) -> str:
    """Returns the first 8 hex characters of the SHA-256 hash of value.

    :param value: String to hash.
    :type value: str
    :returns: first 8 characters of hex digest.
    :rtype: str
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def sanitize_string(string: str) -> str:
    """Sanitizes a string to be completely safe for all file systems.

    :param string: String to sanitize.
    :type string: str
    :returns: Sanitized version of the input string.
    :rtype: str
    """
    safe_string = re.sub(r"[^a-zA-Z0-9_\-]", "_", string)

    safe_string = re.sub(r"_+", "_", safe_string)
    safe_string = safe_string.strip("_")

    return safe_string if safe_string else "dummy"


def cache_path(
    root: str,
    server_url: str,
    collection_id: str,
    crs: str,
    bbox: str,
    collection_type: CollectionType,
) -> str:
    """Computes the deterministic cache path for a collection download.

    The path structure is::

        <cache_root>/<url_hash>/<collection_id>/<crs>/<bbox_hash>/<filename>

    :param root: Root directory chosen by the user for offline storage.
    :type root: str
    :param server_url: Base URL of the OGC API server.
    :type server_url: str
    :param collection_id: Collection identifier as returned by the server.
    :type collection_id: str
    :param collection_type: The capability type being cached.
    :type collection_type: CollectionType
    :param crs: Sanitized CRS auth ID.
    :type crs: str
    :param bbox: Bounding box string
    :type bbox: str.
    :returns: Absolute path to the cache file (file may not exist yet).
    :rtype: str
    """
    is_tiles = collection_type in (
        CollectionType.TILES_RASTER,
        CollectionType.TILES_VECTOR,
    )

    safe_id = sanitize_string(collection_id)
    suffix = "mbtiles" if is_tiles else "gpkg"

    return os.path.join(
        root,
        hash_data(server_url),
        f"{safe_id}-{hash_data(collection_id)}",
        crs,
        hash_data(bbox),
        f"data.{suffix}",
    )


def format_tile_url(
    url_template: str, column: int, row: int, zoom_level: int, matrix_height: int
) -> str:
    """Returns tile URL from the templated URL.

    :param url_template: Templated tiles URL.
    :type url_template: str
    :param colunn: Tile column.
    :type column: int
    :param row: Tile row.
    :type row: int
    :param zoom_level: Tile zoom level.
    :type zoom_level: int
    :param matrix_height: Number of rows of the tile matrix.
    :type matrix_height: int
    :returns: Download URL for the input tile.
    :rtype: str
    """
    out_url = url_template.replace(QGIS_X, f"{column}")
    if QGIS_INVERTED_Y in out_url:
        out_url = out_url.replace(QGIS_INVERTED_Y, f"{matrix_height - row - 1}")
    else:
        out_url = out_url.replace(QGIS_Y, f"{row}")
    out_url = out_url.replace(QGIS_Z, f"{zoom_level}")
    return out_url
