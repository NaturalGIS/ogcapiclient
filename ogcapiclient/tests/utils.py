"""Test helpers."""

import json
import os

from ogcapiclient.core.constants import TMS_WEB_MERCATOR_QUAD
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import (
    BoundingBox,
    Collection,
    DownloadedLayer,
    PreparedLayer,
    TileSet,
)

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


def load_from_file(file_name: str) -> dict:
    """Loads JSON data from file.

    :param file_name: A full path to the JSON file.
    :type links: str
    :returns: A dictionary containing raw JSON data.
    :rtype: dict
    """
    with open(os.path.join(TEST_DATA_PATH, file_name), encoding="utf-8") as f:
        return json.load(f)


def create_collection(
    collection_id: str = "test-collection",
    title: str = "Test Collection",
    collection_type: CollectionType = CollectionType.FEATURES,
    capabilities_url: str = "https://example.com/collections/test-collection/items",
    description: str = "Abstract",
    storage_crs: str | None = "EPSG:4326",
    supported_crs: list[str] = ["EPSG:3857"],
) -> Collection:
    """Creates Collection object.

    :param collection_id: ID of the collection.
    :type collection_id: str
    :param title: Collection title.
    :type title: str
    :param collection_type: Collection type.
    :type collection_type: CollectionType
    :param capabilities_url: URL used to fetch collection data.
    :type capabilities_url: str
    :param description: Collection description.
    :type description: str
    :param storage_crs: Storage CRS.
    :type storage_crs: str | None
    :param supported_crs: Supported CRSs.
    :type supported_crs: list[str]
    :returns: A Collection object.
    :rtype: Collection
    """
    return Collection(
        collection_id,
        title,
        BoundingBox(-180, -90, 180, 90),
        {collection_type: capabilities_url},
        supported_crs,
        description,
        storage_crs,
    )


def create_tileset(
    tms_id: str = TMS_WEB_MERCATOR_QUAD,
    url_template: str = "https://example.com/tiles/{z}/{y}/{x}",
):
    return TileSet(tms_id, url_template)


def create_prepared_layer(
    name: str = "layer",
    collection_type: CollectionType = CollectionType.FEATURES,
    uri_parts: dict[str, str] = {},
    tilesets: list[TileSet] = [],
):
    return PreparedLayer(name, collection_type, uri_parts, tilesets)


def create_downloaded_layer(
    name: str = "layer",
    collection_type: CollectionType = CollectionType.FEATURES,
    file_path: str = "/tmp/test.gpkg",
):
    return DownloadedLayer(name, collection_type, file_path)


def raw_tileset(
    tms_id: str = TMS_WEB_MERCATOR_QUAD,
    template_url: str = "https://example.com/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}?f=pbf",
    use_urn: bool = False,
) -> dict:
    """Creates a minimal OGC API Tiles tilesets response for a single tileset.

    :param tms_id: A tile matrix set ID.
    :type tms_id: str
    :param template_url: A temmplated URL to load single tile.
    :type template_url: str
    :param use_urn: Whether to use URN instead of OGC CRS URL.
    :type use_urn: bool
    :returns: A dictionary representing s single tileset.
    :rtype: dict
    """
    if use_urn:
        tms_uri = f"urn:ogc:def:tilematrixset:OGC:1.0:{tms_id}"
    else:
        tms_uri = f"https://www.opengis.net/def/tilematrixset/OGC/1.0/{tms_id}"

    return {
        "tilesets": [
            {
                "tileMatrixSetURI": tms_uri,
                "crs": "http://www.opengis.net/def/crs/EPSG/0/3857",
                "links": [
                    {
                        "rel": "item",
                        "type": "application/vnd.mapbox-vector-tile",
                        "href": template_url,
                        "templated": True,
                    }
                ],
            }
        ]
    }
