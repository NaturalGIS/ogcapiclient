"""OGC API client dialog."""

import os

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsTask,
    QgsTaskManager,
)
from qgis.gui import QgisInterface, QgsFileWidget, QgsGui
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QItemSelectionModel, QModelIndex, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QDialogButtonBox, QMessageBox, QWidget

from ogcapiclient.core.constants import TILE_COUNT_THRESHOLD
from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import (
    Collection,
    DiscoveryResult,
    DownloadedLayer,
    OfflineDownload,
)
from ogcapiclient.gui.constants import (
    MAXIMUM_ABSTRACT_WIDTH,
    MAXIMUM_COLUMN_WIDTH,
    SUPPORTED_COLLECTIONS,
)
from ogcapiclient.gui.enums import CollectionModelColumn
from ogcapiclient.gui.utils import collection_type_to_string
from ogcapiclient.qgis_backend.download_manager import DownloadManager
from ogcapiclient.qgis_backend.layer_manager import LayerManager
from ogcapiclient.qgis_backend.tasks.download_task import DownloadTask
from ogcapiclient.qgis_backend.tasks.layer_preparation_task import LayerPreparationTask
from ogcapiclient.qgis_backend.tasks.ogc_discovery_task import OgcDiscoveryTask

PLUGIN_PATH = os.path.split(os.path.dirname(__file__))[0]
WIDGET, BASE = uic.loadUiType(
    os.path.join(PLUGIN_PATH, "ui", "ogc_api_client_dialog.ui")
)


class OgcApiClientDialog(BASE, WIDGET):
    """Main dialog of the plugin.

    Provides the interface for server connection, AOI selection,
    and collection browsing.
    """

    def __init__(self, iface: QgisInterface, parent: QWidget = None) -> None:
        """Initialises the dialog.

        :param iface: The QGIS interface instance.
        :type iface: QgisInterface
        :param parent: Optional parent widget.
        :type parent: QWidget
        """
        super().__init__(parent)
        self.setupUi(self)

        self.iface: QgisInterface = iface
        self.task_manager: QgsTaskManager = QgsApplication.taskManager()
        self.available_crs: dict[str, list[str]] = {}
        self.discovery_result: DiscoveryResult = None
        self.task: QgsTask = None

        QgsGui.instance().enableAutoGeometryRestore(self)

        self.progress_bar.hide()
        self.button_cancel.hide()

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderItem(
            CollectionModelColumn.TITLE, QStandardItem(self.tr("Title"))
        )
        self.model.setHorizontalHeaderItem(
            CollectionModelColumn.NAME, QStandardItem(self.tr("Name"))
        )
        self.model.setHorizontalHeaderItem(
            CollectionModelColumn.TYPE, QStandardItem(self.tr("Type"))
        )
        self.model.setHorizontalHeaderItem(
            CollectionModelColumn.ABSTRACT, QStandardItem(self.tr("Abstract"))
        )
        self.collections_tree.setModel(self.model)
        self.collections_tree.selectionModel().currentRowChanged.connect(
            self.current_row_changed
        )

        self.init_extent_selector()
        self.widget_cache_path.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)

        self.button_add = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
        self.button_add.setText(self.tr("Add"))
        self.button_add.setEnabled(False)

        self.button_connect.clicked.connect(self.connect_to_server)
        self.button_online.toggled.connect(self.toggle_offline_mode)
        self.button_add.clicked.connect(self.prepare_layers)
        self.buttonBox.helpRequested.connect(self.open_help)
        self.buttonBox.rejected.connect(self.reject)

        self.button_online.setChecked(True)

    def init_extent_selector(self) -> None:
        """Configures the extent selector widget to output in EPSG:4326."""
        self.group_extent.setOutputCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        if self.iface.mapCanvas() is None:
            return

        self.group_extent.setCurrentExtent(
            self.iface.mapCanvas().extent(),
            self.iface.mapCanvas().mapSettings().destinationCrs(),
        )
        self.group_extent.setOutputExtentFromCurrent()
        self.group_extent.setMapCanvas(self.iface.mapCanvas())

    def toggle_offline_mode(self, checked: bool) -> None:
        """Toggles between online and offline modes.

        :param checked: Whether the offline mode (radio button) is disabled.
        :type checked: bool
        """
        self.label_cache_path.setVisible(not checked)
        self.widget_cache_path.setVisible(not checked)
        if not checked:
            self.button_add.setText(self.tr("Download"))
        else:
            self.button_add.setText(self.tr("Add"))

    def current_row_changed(self, current: QModelIndex, previour: QModelIndex) -> None:
        """Triggered when the  current row in the collections tree is changed.

        Enables Add/Download button if a valid collection is selected.

        :param current: The newly selected model index.
        :type current: QModelIndex
        :param previous: The previously selected model index.
        :type previous: QModelIndex
        """
        if current.isValid() and self.task is None:
            self.button_add.setEnabled(True)

    def open_help(self) -> None:
        """Opens plugin documentation."""
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.join(PLUGIN_PATH, "help", "ogcapiclient.pdf"))
        )

    def connect_to_server(self) -> None:
        """Triggered by the 'Connect' button. Starts the discovery task."""
        url = self.edit_server_url.text()
        if not url:
            QMessageBox.warning(
                None, self.tr("Empty URL"), self.tr("Server URL is missed.")
            )
            return

        self.button_connect.setEnabled(False)
        self.button_add.setEnabled(False)

        auth_cfg = self.auth_widget.configId()

        if self.model is not None:
            self.model.removeRows(0, self.model.rowCount())

        self.task = OgcDiscoveryTask(url, auth_cfg)
        self.task.progressChanged.connect(lambda x: self.progress_bar.setValue(int(x)))
        self.task.taskTerminated.connect(self.discovery_finished)
        self.task.taskCompleted.connect(self.update_collections)
        self.button_cancel.clicked.connect(self.task.cancel)

        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.button_cancel.show()

        self.task_manager.addTask(self.task)

    def discovery_finished(self):
        """Triggered when server discovery finishes."""
        self.button_connect.setEnabled(True)
        self.button_add.setEnabled(False)
        task = self.sender()
        if self.task == task:
            if task.isCanceled():
                QMessageBox.information(
                    None, self.tr("Canceled"), self.tr("Operation was canceled.")
                )
            if not task.isCanceled() and task.exception:
                QMessageBox.critical(
                    None,
                    self.tr("Error"),
                    self.tr(
                        "An error occured when connecting to the server. "
                        "Check Message Log for more details."
                    ),
                )
            self.progress_bar.setValue(-1)
            self.progress_bar.hide()
            self.button_cancel.hide()
            self.button_cancel.clicked.disconnect(self.task.cancel)
            self.task = None

    def update_collections(self) -> None:
        """Populates collections tree view with the collections
        returned by the server.
        """
        task = self.sender()
        if self.task != task:
            return

        self.button_connect.setEnabled(True)
        self.button_add.setEnabled(False)
        self.available_crs.clear()

        self.discovery_result = task.data
        self.discovery_finished()

        for collection in self.discovery_result.collections:
            for collection_type, collection_url in collection.capabilities.items():
                if collection_type not in SUPPORTED_COLLECTIONS:
                    continue

                title_item = QStandardItem(collection.title)
                name_item = QStandardItem(collection.id)
                abstract_item = QStandardItem(collection.description)
                abstract_item.setToolTip(
                    "<font color=black>" + collection.description + "</font>"
                )
                abstract_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
                type_item = QStandardItem(collection_type_to_string(collection_type))
                self.model.appendRow([title_item, name_item, type_item, abstract_item])
                title_item.setData(
                    (collection, collection_type), Qt.ItemDataRole.UserRole
                )

                crs_list = []
                if collection.storage_crs:
                    crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(
                        collection.storage_crs
                    )
                    crs_list.append(crs.authid())
                for i in collection.supported_crs:
                    crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(i)
                    if crs.authid() not in crs_list:
                        crs_list.append(crs.authid())
                self.available_crs[collection.id] = crs_list

        self.adjust_columns()

    def adjust_columns(self) -> None:
        """Resizes collection tree view columns."""
        if self.model.rowCount() > 0:
            self.collections_tree.resizeColumnToContents(CollectionModelColumn.TITLE)
            self.collections_tree.resizeColumnToContents(CollectionModelColumn.NAME)
            self.collections_tree.resizeColumnToContents(CollectionModelColumn.ABSTRACT)
            for column in CollectionModelColumn:
                if self.collections_tree.columnWidth(column) > MAXIMUM_COLUMN_WIDTH:
                    self.collections_tree.setColumnWidth(column, MAXIMUM_COLUMN_WIDTH)

            if (
                self.collections_tree.columnWidth(CollectionModelColumn.ABSTRACT)
                > MAXIMUM_ABSTRACT_WIDTH
            ):
                self.collections_tree.setColumnWidth(
                    CollectionModelColumn.ABSTRACT, MAXIMUM_ABSTRACT_WIDTH
                )

            self.collections_tree.selectionModel().setCurrentIndex(
                self.model.index(0, 0),
                QItemSelectionModel.SelectionFlag.SelectCurrent
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            self.collections_tree.setFocus()
        else:
            self.button_add.setEnabled(False)
            QMessageBox.information(
                None,
                self.tr("No Layers"),
                self.tr("Collections document contained no layers."),
            )

    def prepare_layers(self):
        """Prepares selected collections for adding to the project."""
        current_index = self.collections_tree.selectionModel().currentIndex()
        if not current_index.isValid():
            return

        if self.button_online.isChecked():
            self.online_mode()
        else:
            self.offline_mode()

    def online_mode(self):
        """Prepares selected collections for addition to the project in online mode."""
        crs_map, items = self._selected_items()
        if not items:
            return

        self.button_add.setEnabled(False)

        auth_cfg = self.auth_widget.configId()

        self.task = LayerPreparationTask(
            self.discovery_result.url, items, crs_map, auth_cfg
        )
        self.task.taskTerminated.connect(self.layer_preparation_finished)
        self.task.taskCompleted.connect(self.add_online_layers)

        self.task_manager.addTask(self.task)

    def layer_preparation_finished(self) -> None:
        """Triggered when layers preparation finished."""
        task = self.sender()
        if self.task == task:
            self.button_add.setEnabled(True)

            if task.isCanceled():
                QMessageBox.information(
                    None, self.tr("Canceled"), self.tr("Operation was canceled.")
                )
            if not task.isCanceled() and task.exception:
                QMessageBox.critical(
                    None,
                    self.tr("Error"),
                    self.tr(
                        "An error occured when loading layer(s). "
                        "Check Message Log for more details."
                    ),
                )
            self.task = None

    def add_online_layers(self) -> None:
        """Adds collections to QGIS in online mode."""
        task = self.sender()
        if self.task != task:
            return

        bbox = self.group_extent.outputExtent()

        prepared_layers = task.data
        self.layer_preparation_finished()
        for layer in prepared_layers:
            ok = LayerManager.add_online_layer(layer, bbox)
            if not ok:
                # TODO: log failure?
                pass

    def offline_mode(self):
        """Prepares selected collections for addition to the project in offline mode."""
        cache_root = self.widget_cache_path.filePath()
        if not cache_root:
            QMessageBox.warning(
                None, self.tr("No cache path"), self.tr("Cache path is not set.")
            )
            return

        self.button_add.setEnabled(False)

        if not os.path.exists(cache_root):
            os.makedirs(cache_root)

        bbox = self.group_extent.outputExtent()

        crs_map, items = self._selected_items()
        if not items:
            return

        download_items = DownloadManager.build_download_list(
            items, cache_root, self.discovery_result.url, bbox, crs_map
        )

        local_list = []
        download_list = []
        for item in download_items:
            if item.cache_exists:
                answer = QMessageBox.question(
                    None,
                    self.tr("Cached data found"),
                    self.tr(
                        "Data for this collection has already been downloaded. "
                        "Would you like to use the existing data?"
                    ),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    local_list.append(
                        DownloadedLayer(
                            item.collection.title, item.collection_type, item.file_path
                        )
                    )
                    continue
                if answer == QMessageBox.StandardButton.Cancel:
                    return

            if item.tile_count > TILE_COUNT_THRESHOLD:
                answer = QMessageBox.question(
                    None,
                    self.tr("Large tile count"),
                    self.tr(
                        "Downloading selected area requires approximately"
                        "{count} tiles. Do you want to proceed?"
                    ).format(count=item.tile_count),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.No:
                    continue

            download_list.append(item)

        for i in local_list:
            LayerManager.add_offline_layer(i)

        if not download_list:
            self.button_add.setEnabled(True)
            return

        auth_cfg = self.auth_widget.configId()

        self.task = DownloadTask(self.discovery_result.url, download_list, auth_cfg)
        self.task.taskTerminated.connect(self.download_finished)
        self.task.taskCompleted.connect(self.add_offline_layers)

        self.task_manager.addTask(self.task)

    def download_finished(self) -> None:
        """Triggered when data download finished."""
        task = self.sender()
        if self.task == task:
            self.button_add.setEnabled(True)

            if task.isCanceled():
                QMessageBox.information(
                    None, self.tr("Canceled"), self.tr("Operation was canceled.")
                )
            if not task.isCanceled() and task.exception:
                QMessageBox.critical(
                    None,
                    self.tr("Error"),
                    self.tr(
                        "An error occured when downloading data. "
                        "Check Message Log for more details."
                    ),
                )
            self.task = None

    def add_offline_layers(self) -> None:
        """Adds collections to QGIS in offline mode."""
        task = self.sender()
        if self.task != task:
            return

        downloaded_layers = task.data
        self.download_finished()
        for layer in downloaded_layers:
            ok = LayerManager.add_offline_layer(layer)
            if not ok:
                # TODO: log failure?
                pass

    def _selected_items(
        self,
    ) -> tuple[dict[str, str], list[tuple[Collection, CollectionType]]]:
        layers_to_prepare = []
        crs_map = {}
        selected_indexes = self.collections_tree.selectionModel().selectedRows()
        for index in selected_indexes:
            item = self.model.itemFromIndex(index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                collection, collection_type = data
                layers_to_prepare.append((collection, collection_type))
                crs_map[collection.id] = (
                    self.available_crs.get(collection.id, ["EPSG:4326"])[0]
                    if collection_type == CollectionType.FEATURES
                    else "EPSG:3857"
                )
        return crs_map, layers_to_prepare
