from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsProject,
    QgsProviderRegistry,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QUrl

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import PreparedLayer


def filter_from_bbox(bbox: QgsRectangle, crs: str) -> str:
    """Builds a QGIS filter expression that constrains features to a bounding box.

    :param bbox: The bounding box in EPSG:4326/CRS84.
    :type bbox: QgsRectangle
    :param crs: The target layer CRS.
    :type crs: str
    :returns: A QGIS expression string suitable for the 'filter' URI parameter.
    :rtype: str
    """
    filter_bbox = QgsRectangle(bbox)
    if crs:
        source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        target_crs = QgsCoordinateReferenceSystem(crs)
        if target_crs.isValid() and target_crs != source_crs:
            transform = QgsCoordinateTransform(
                source_crs, target_crs, QgsProject.instance()
            )
            filter_bbox = transform.transform(bbox)

    return f"intersects_bbox($geometry, geomFromWkt('{filter_bbox.asWktPolygon()}'))"


def create_layer_uri(layer: PreparedLayer, bbox: QgsRectangle = None) -> str:
    """Creates a QGIS connection string for a prepared layer.

    For Features layers an optional bounding box can be supplied to limit
    amount of requested daata.

    :param layer: Information about the layer to add.
    :type layer: PreparedLayer
    :param bbox: Optional AOI in EPSG:4326/CRS84.
    :type bbox: QgsRectangle
    :returns: A URI suitable for constructing a QGIS layer.
    :rtype: str
    """
    parts = layer.uri_parts.copy()

    if layer.collection_type == CollectionType.TILES_RASTER:
        return QgsProviderRegistry.instance().encodeUri("wms", parts)

    auth_cfg = parts.pop("authcfg", "")
    crs = parts.get("srsname")
    ds_uri = QgsDataSourceUri()

    for k, v in parts.items():
        if k == "url" and layer.collection_type == CollectionType.FEATURES:
            v = QUrl(v).toEncoded().data().decode("utf-8")
        if k == "srsname" and layer.collection_type == CollectionType.FEATURES:
            continue
        ds_uri.setParam(k, v)

    if auth_cfg:
        ds_uri.setAuthConfigId(auth_cfg)

    if layer.collection_type == CollectionType.FEATURES and bbox is not None:
        ds_uri.setParam("filter", filter_from_bbox(bbox, crs))

    if layer.collection_type == CollectionType.FEATURES:
        return ds_uri.uri()
    else:
        return ds_uri.encodedUri().data().decode("utf-8")
