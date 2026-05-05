from ogcapiclient.plugin import OgcApiClientPlugin


def classFactory(iface):
    return OgcApiClientPlugin(iface)
