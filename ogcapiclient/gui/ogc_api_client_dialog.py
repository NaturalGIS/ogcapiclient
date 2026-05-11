import os

from qgis.core import QgsCoordinateReferenceSystem
from qgis.gui import QgisInterface, QgsFileWidget, QgsGui
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDialogButtonBox, QWidget

PLUGIN_PATH = os.path.split(os.path.dirname(__file__))[0]
WIDGET, BASE = uic.loadUiType(
    os.path.join(PLUGIN_PATH, "ui", "ogc_api_client_dialog.ui")
)


class OgcApiClientDialog(BASE, WIDGET):
    def __init__(self, iface: QgisInterface, parent: QWidget = None) -> Mone:
        super().__init__(parent)
        self.setupUi(self)

        self.iface = iface

        QgsGui.instance().enableAutoGeometryRestore(self)

        self.init_extent()
        self.widget_cache_path.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)

        self.button_add = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
        self.button_add.setText(self.tr("Add"))
        self.button_add.setEnabled(False)

        self.button_connect.clicked.connect(self.connect_to_server)
        self.button_online.toggled.connect(self.toggle_offline_mode)
        self.button_add.clicked.connect(self.add_layers)
        self.buttonBox.helpRequested.connect(self.open_help)
        self.buttonBox.rejected.connect(self.reject)

        self.button_online.setChecked(True)

    def init_extent(self) -> None:
        self.group_extent.setOutputCrs(QgsCoordinateReferenceSystem("EPGS:4326"))
        if self.iface.mapCanvas() is None:
            return
        self.group_extent.setCurrentExtent(
            self.iface.mapCanvas().extent(),
            self.iface.mapCanvas().mapSettings().destinationCrs(),
        )
        self.group_extent.setOutputExtentFromCurrent()
        self.group_extent.setMapCanvas(self.iface.mapCanvas())

    def connect_to_server(self) -> None:
        uri = self.edit_server_url.text()

    def toggle_offline_mode(self, checked: bool) -> None:
        self.label_cache_path.setVisible(not checked)
        self.widget_cache_path.setVisible(not checked)
        if not checked:
            self.button_add.setText(self.tr("Download"))
        else:
            self.button_add.setText(self.tr("Add"))

    def add_layers(self):
        pass

    def open_help(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.join(PLUGIN_PATH, "ogcapiclient.pdf"))
        )
