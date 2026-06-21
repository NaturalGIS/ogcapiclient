"""Helper to create QGIS layers and adding them to the project."""

from qgis.core import (
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
    QgsVectorTileLayer,
)

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import PreparedLayer
from ogcapiclient.qgis_backend.utils import create_layer_uri


class LayerManager:
    """Creates QGIS map layers from plugin data models and adds them to the project."""

    @staticmethod
    def add_online_layer(layer: PreparedLayer, bbox: QgsRectangle = None) -> bool:
        """Creates an online QGIS layer and adds it to the current project.

        :param layer: Prepared layer configuration.
        :type layer: PreparedLayer
        :param bbox: Area of interest used to filter layers.
        :type bbox: QgsRectangle
        :returns: True if the layer was valid and added to the project.
        :rtype: bool
        """
        uri = create_layer_uri(layer, bbox)
        qgis_layer = LayerManager.create_online_layer(layer, uri)
        return LayerManager.add_layer(qgis_layer)

    @staticmethod
    def create_online_layer(layer: PreparedLayer, uri: str) -> QgsMapLayer:
        """Instantiates the appropriate QGIS layer type for an online layer.

        :param layer: Prepared layer configuration.
        :type layer: PreparedLayer
        :param uri: QGIS-compatible data source URI.
        :type uri: str
        :returns: A QGIS map layer instance.
        """
        if layer.collection_type == CollectionType.TILES_RASTER:
            return QgsRasterLayer(uri, layer.name, layer.provider_key)
        if layer.collection_type == CollectionType.TILES_VECTOR:
            return QgsVectorTileLayer(uri, layer.name)
        return QgsVectorLayer(uri, layer.name, layer.provider_key)

    @staticmethod
    def add_layer(layer: QgsMapLayer) -> bool:
        """Adds a layer to the current project if it is valid.

        :param layer: A QGIS map layer instance.
        :type layer: QgsMapLayer
        :returns: True if the layer was added.
        :rtype: bool
        """
        if layer is not None and layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return True
        return False
