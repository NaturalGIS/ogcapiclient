from qgis.gui import QgisInterface

from ogcapiclient.plugin import OgcApiClientPlugin


def classFactory(iface: QgisInterface):
    return OgcApiClientPlugin(iface)
