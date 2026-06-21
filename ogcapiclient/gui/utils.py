"""GUI utilities and helpers."""

from qgis.PyQt.QtCore import QCoreApplication

from ogcapiclient.core.enums import CollectionType


def collection_type_to_string(collection_type: CollectionType) -> str:
    """Returns a localized, human-readable string for a CollectionType enum."""
    context = "OgcApiClientPlugin"

    types_map = {
        CollectionType.FEATURES: QCoreApplication.translate(context, "Features"),
        CollectionType.TILES_RASTER: QCoreApplication.translate(context, "Tiles"),
        CollectionType.TILES_VECTOR: QCoreApplication.translate(context, "Tiles"),
        CollectionType.MAPS: QCoreApplication.translate(context, "Maps"),
        CollectionType.COVERAGES: QCoreApplication.translate(context, "Coverages"),
        CollectionType.UNKNOWN: QCoreApplication.translate(context, "Unknown Type"),
    }

    return types_map.get(
        collection_type, QCoreApplication.translate(context, "Unknown Type")
    )
