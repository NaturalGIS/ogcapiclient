"""Plugins entry point."""

from qgis.gui import QgisInterface

from ogcapiclient.plugin import OgcApiClientPlugin


def classFactory(iface: QgisInterface) -> OgcApiClientPlugin:
    return OgcApiClientPlugin(iface)
