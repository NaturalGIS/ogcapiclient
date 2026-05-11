import os

from qgis.core import QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction

from ogcapiclient.gui.ogc_api_client_dialog import OgcApiClientDialog

PLUGIN_PATH = os.path.dirname(__file__)


class OgcApiClientPlugin:
    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.dialog = None

        locale = QgsApplication.locale()
        qm_path = f"{PLUGIN_PATH}/i18n/ogcapiclient_{locale}.qm"

        if os.path.exists(qm_path):
            self.translator = QTranslator()
            self.translator.load(qm_path)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self) -> None:
        self.action_open = QAction(self.tr("OGC API Client"), self.iface.mainWindow())
        self.action_open.setIcon(QIcon(os.path.join(PLUGIN_PATH, "icons", "icon.svg")))
        self.action_open.setObjectName("openOgcApiClient")
        self.action_open.triggered.connect(self.open_dialog)

        self.action_help = QAction(self.tr("Help"), self.iface.mainWindow())
        self.action_help.setObjectName("openOgcApiClientHelp")
        self.action_help.triggered.connect(self.open_help)

        self.iface.addPluginToWebMenu(self.tr("OGC API Client"), self.action_open)
        self.iface.addPluginToWebMenu(self.tr("OGC API Client"), self.action_help)
        self.iface.addWebToolBarIcon(self.action_open)

    def unload(self) -> None:
        self.iface.removePluginWebMenu(self.tr("OGC API Client"), self.action_open)
        self.iface.removePluginWebMenu(self.tr("OGC API Client"), self.action_help)
        self.iface.removeWebToolBarIcon(self.action_open)

    def open_dialog(self) -> None:
        self.dialog = OgcApiClientDialog(self.iface)
        self.dialog.show()

    def open_help(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.join(PLUGIN_PATH, "help", "ogcapiclient.pdf"))
        )

    def tr(self, text: str) -> str:
        return QCoreApplication.translate(self.__class__.__name__, text)
