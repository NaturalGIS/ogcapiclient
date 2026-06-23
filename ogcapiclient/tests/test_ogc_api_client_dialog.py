import tempfile
import unittest
from unittest.mock import MagicMock, patch

from qgis.PyQt.QtCore import QItemSelectionModel, QModelIndex, Qt
from qgis.PyQt.QtGui import QStandardItem
from qgis.utils import iface

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.models import (
    BoundingBox,
    Collection,
    DiscoveryResult,
    DownloadedLayer,
    PreparedLayer,
)
from ogcapiclient.gui.ogc_api_client_dialog import OgcApiClientDialog
from ogcapiclient.tests.mocks import DummyTask
from ogcapiclient.tests.utils import (
    create_collection,
    create_downloaded_layer,
    create_prepared_layer,
)


def select_collection(
    dialog,
    collection,
    collection_type=CollectionType.FEATURES,
):
    row = dialog.model.rowCount()

    title_item = QStandardItem(collection.title)
    title_item.setData(
        (collection, collection_type),
        Qt.ItemDataRole.UserRole,
    )

    dialog.model.appendRow(
        [
            title_item,
            QStandardItem(collection.id),
            QStandardItem("type"),
            QStandardItem(collection.description),
        ]
    )

    index = dialog.model.index(row, 0)

    selection_model = dialog.collections_tree.selectionModel()

    selection_model.select(
        index,
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )

    selection_model.setCurrentIndex(
        index,
        QItemSelectionModel.SelectionFlag.Current,
    )

    return index


class TestOgcApiClientDialog(unittest.TestCase):
    def setUp(self):
        self.iface = iface
        self.dialog = OgcApiClientDialog(self.iface)

    def tearDown(self):
        self.dialog.close()

    def test_initial_state(self):
        self.assertIs(self.dialog.iface, self.iface)
        self.assertIsNone(self.dialog.discovery_result)
        self.assertIsNone(self.dialog.task)
        self.assertEqual(self.dialog.available_crs, {})

        self.assertTrue(self.dialog.progress_bar.isHidden())
        self.assertTrue(self.dialog.button_cancel.isHidden())

        self.assertEqual(self.dialog.model.columnCount(), 4)

        self.assertEqual(
            self.dialog.model.horizontalHeaderItem(0).text(),
            "Title",
        )
        self.assertEqual(
            self.dialog.model.horizontalHeaderItem(1).text(),
            "Name",
        )
        self.assertEqual(
            self.dialog.model.horizontalHeaderItem(2).text(),
            "Type",
        )
        self.assertEqual(
            self.dialog.model.horizontalHeaderItem(3).text(),
            "Abstract",
        )

        self.assertEqual(self.dialog.button_add.text(), "Add")
        self.assertFalse(self.dialog.button_add.isEnabled())

        self.assertTrue(self.dialog.button_online.isChecked())

    def test_init_extent_selector_output_crs(self):
        self.assertEqual(
            self.dialog.group_extent.outputCrs().authid(),
            "EPSG:4326",
        )

    def test_toggle_offline_mode_online(self):
        self.dialog.toggle_offline_mode(True)

        self.assertTrue(self.dialog.label_cache_path.isHidden())
        self.assertTrue(self.dialog.widget_cache_path.isHidden())
        self.assertEqual(self.dialog.button_add.text(), "Add")

    def test_toggle_offline_mode_offline(self):
        self.dialog.toggle_offline_mode(False)

        self.assertFalse(self.dialog.label_cache_path.isHidden())
        self.assertFalse(self.dialog.widget_cache_path.isHidden())
        self.assertEqual(self.dialog.button_add.text(), "Download")

    def test_toggle_offline_mode_twice(self):
        self.dialog.toggle_offline_mode(False)

        self.assertFalse(self.dialog.label_cache_path.isHidden())
        self.assertEqual(self.dialog.button_add.text(), "Download")

        self.dialog.toggle_offline_mode(True)

        self.assertTrue(self.dialog.label_cache_path.isHidden())
        self.assertEqual(self.dialog.button_add.text(), "Add")

    def test_collections_tree_uses_dialog_model(self):
        self.assertIs(
            self.dialog.collections_tree.model(),
            self.dialog.model,
        )

    def test_current_row_changed_enables_add_button(self):
        self.dialog.task = None

        model = self.dialog.model
        model.appendRow([])
        index = model.index(0, 0)

        self.dialog.button_add.setEnabled(False)

        self.dialog.current_row_changed(index, QModelIndex())

        self.assertTrue(self.dialog.button_add.isEnabled())

    def test_current_row_changed_ignored_when_task_running(self):
        self.dialog.task = MagicMock()

        index = self.dialog.model.index(0, 0)
        self.dialog.button_add.setEnabled(False)

        self.dialog.current_row_changed(index, QModelIndex())

        self.assertFalse(self.dialog.button_add.isEnabled())

    def test_current_row_changed_invalid_index(self):
        self.dialog.task = None
        self.dialog.button_add.setEnabled(False)

        self.dialog.current_row_changed(QModelIndex(), QModelIndex())

        self.assertFalse(self.dialog.button_add.isEnabled())

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.warning")
    def test_connect_to_server_empty_url(self, warning):
        self.dialog.edit_server_url.setText("")

        self.dialog.task_manager = MagicMock()

        self.dialog.connect_to_server()

        warning.assert_called_once()
        self.dialog.task_manager.addTask.assert_not_called()

    def test_connect_to_server_creates_task(self):
        self.dialog.edit_server_url.setText("https://example.com")

        dummy_task = DummyTask()
        self.dialog.task_manager = MagicMock()

        with patch(
            "ogcapiclient.gui.ogc_api_client_dialog.OgcDiscoveryTask",
            return_value=dummy_task,
        ):
            self.dialog.connect_to_server()

            self.dialog.task_manager.addTask.assert_called_once_with(dummy_task)

            self.assertEqual(self.dialog.task, dummy_task)
            self.assertFalse(self.dialog.progress_bar.isHidden())
            self.assertFalse(self.dialog.button_cancel.isHidden())
            self.assertFalse(self.dialog.button_connect.isEnabled())

    def test_connect_to_server_clears_model(self):
        self.dialog.model.appendRow([])

        self.dialog.edit_server_url.setText("https://example.com")

        self.dialog.task_manager = MagicMock()

        with patch(
            "ogcapiclient.gui.ogc_api_client_dialog.OgcDiscoveryTask",
            return_value=DummyTask(),
        ):
            self.dialog.connect_to_server()

            self.assertEqual(self.dialog.model.rowCount(), 0)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.information")
    def test_discovery_finished_canceled(self, info):
        task = DummyTask()
        task._canceled = True
        task.exception = None

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.discovery_finished()

        info.assert_called_once()
        self.assertIsNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.critical")
    def test_discovery_finished_exception(self, critical):
        task = DummyTask()
        task._canceled = False
        task.exception = Exception()

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.discovery_finished()

        critical.assert_called_once()
        self.assertIsNone(self.dialog.task)

    def test_discovery_finished_normal(self):
        task = DummyTask()
        task._canceled = False
        task.exception = None

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.discovery_finished()

        self.assertIsNone(self.dialog.task)

    def test_discovery_finished_ignores_other_task(self):
        self.dialog.task = DummyTask()

        other_task = MagicMock()

        with patch.object(self.dialog, "sender", return_value=other_task):
            self.dialog.discovery_finished()

        self.assertIsNotNone(self.dialog.task)

    def test_update_collections_populates_model(self):
        col = create_collection()

        task = DummyTask()
        task.data = DiscoveryResult("http://example.com", "Test server", [], [col])

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        self.assertEqual(self.dialog.model.rowCount(), 1)
        self.assertEqual(len(self.dialog.available_crs), 1)

    def test_update_collections_skips_unsupported_collections(self):
        col1 = create_collection("a")
        col2 = create_collection("b")
        col2.capabilities = {CollectionType.UNKNOWN: "x"}

        task = DummyTask()

        task.data = DiscoveryResult(
            "http://example.com", "Test server", [], [col1, col2]
        )

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        self.assertEqual(self.dialog.model.rowCount(), 1)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.information")
    def test_update_collections_no_layers(self, information):
        col = create_collection()
        col.capabilities = {CollectionType.UNKNOWN: "x"}

        task = DummyTask()

        task.data = DiscoveryResult("http://example.com", "Test server", [], [col])

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        information.assert_called_once()
        self.assertEqual(self.dialog.model.rowCount(), 0)

    def test_update_collections_crs_mapping(self):
        col = create_collection("lakes")

        task = DummyTask()
        task.data = DiscoveryResult("http://example.com", "Test server", [], [col])

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        crs = self.dialog.available_crs["lakes"]

        self.assertTrue(any("EPSG:4326" in c or "EPSG:3857" in c for c in crs))

    def test_update_collections_storage_crs_used_first(self):
        col = create_collection(
            "rivers", storage_crs="EPSG:9999", supported_crs=["EPSG:4326"]
        )

        task = DummyTask()
        task.data = DiscoveryResult("http://example.com", "Test server", [], [col])

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        crs_list = self.dialog.available_crs["rivers"]

        self.assertTrue(len(crs_list) > 0)

    def test_update_collections_ignores_other_task(self):
        self.dialog.task = DummyTask()

        task = DummyTask()

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.update_collections()

        self.assertEqual(self.dialog.model.rowCount(), 0)

    def test_selected_items_features_use_first_available_crs(self):
        col = create_collection()

        select_collection(self.dialog, col)

        self.dialog.available_crs[col.id] = ["EPSG:3857", "EPSG:4326"]

        crs_map, items = self.dialog._selected_items()

        self.assertEqual(crs_map[col.id], "EPSG:3857")
        self.assertEqual(items, [(col, CollectionType.FEATURES)])

    def test_selected_items_tiles_use_3857(self):
        col = create_collection()

        select_collection(self.dialog, col, CollectionType.TILES_RASTER)

        self.dialog.available_crs[col.id] = ["EPSG:4326"]

        crs_map, items = self.dialog._selected_items()

        self.assertEqual(crs_map[col.id], "EPSG:3857")
        self.assertEqual(items, [(col, CollectionType.TILES_RASTER)])

    def test_selected_items_default_crs(self):
        col = create_collection()

        select_collection(self.dialog, col)

        crs_map, items = self.dialog._selected_items()

        self.assertEqual(crs_map[col.id], "EPSG:4326")

    def test_selected_items_ignore_rows_without_data(self):
        self.dialog.model.appendRow([QStandardItem("dummy")])

        index = self.dialog.model.index(0, 0)

        self.dialog.collections_tree.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )

        crs_map, items = self.dialog._selected_items()

        self.assertEqual(crs_map, {})
        self.assertEqual(items, [])

    @patch.object(OgcApiClientDialog, "online_mode")
    @patch.object(OgcApiClientDialog, "offline_mode")
    def test_prepare_layers_invalid_index(
        self,
        offline_mode,
        online_mode,
    ):
        self.dialog.prepare_layers()

        online_mode.assert_not_called()
        offline_mode.assert_not_called()

    @patch.object(OgcApiClientDialog, "online_mode")
    def test_prepare_layers_task_running(self, online_mode):
        col = create_collection()

        select_collection(self.dialog, col)

        self.dialog.task = DummyTask()

        self.dialog.prepare_layers()

        online_mode.assert_not_called()

    @patch.object(OgcApiClientDialog, "online_mode")
    def test_prepare_layers_online(self, online_mode):
        col = create_collection()

        select_collection(self.dialog, col)

        self.dialog.button_online.setChecked(True)

        self.dialog.prepare_layers()

        online_mode.assert_called_once()

    @patch.object(OgcApiClientDialog, "offline_mode")
    def test_prepare_layers_offline(self, offline_mode):
        col = create_collection()

        select_collection(self.dialog, col)

        self.dialog.button_offline.setChecked(True)

        self.dialog.prepare_layers()

        offline_mode.assert_called_once()

    def test_online_mode_no_items(self):
        self.dialog.discovery_result = DiscoveryResult("url", "server", [], [])

        self.dialog.online_mode()

        self.assertIsNone(self.dialog.task)

    def test_online_mode_creates_task(self):
        col = create_collection()

        select_collection(self.dialog, col)

        self.dialog.available_crs[col.id] = ["EPSG:4326"]

        self.dialog.discovery_result = DiscoveryResult(
            "http://example.com", "server", [], [col]
        )

        self.dialog.task_manager = MagicMock()

        dummy_task = DummyTask()

        with patch(
            "ogcapiclient.gui.ogc_api_client_dialog.LayerPreparationTask",
            return_value=dummy_task,
        ):
            self.dialog.online_mode()

        self.assertFalse(self.dialog.button_add.isEnabled())
        self.assertIs(self.dialog.task, dummy_task)

        self.dialog.task_manager.addTask.assert_called_once_with(dummy_task)

    def test_layer_preparation_finished_success(self):
        task = DummyTask()

        self.dialog.task = task
        self.dialog.button_add.setEnabled(False)

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.layer_preparation_finished()

        self.assertTrue(self.dialog.button_add.isEnabled())
        self.assertIsNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.information")
    def test_layer_preparation_finished_canceled(self, information):
        task = DummyTask(canceled=True)

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.layer_preparation_finished()

        information.assert_called_once()
        self.assertIsNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.critical")
    def test_layer_preparation_finished_exception(self, critical):
        task = DummyTask(exception=Exception())

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.layer_preparation_finished()

        critical.assert_called_once()
        self.assertIsNone(self.dialog.task)

    def test_layer_preparation_finished_ignores_other_task(self):
        self.dialog.task = DummyTask()

        foreign_task = DummyTask()

        with patch.object(self.dialog, "sender", return_value=foreign_task):
            self.dialog.layer_preparation_finished()

        self.assertIsNotNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.LayerManager.add_online_layer")
    def test_add_online_layers_not_run_if_other_task(self, add_online_layer):
        self.dialog.task = DummyTask()

        foreign_task = DummyTask(data=[create_prepared_layer()])

        with patch.object(self.dialog, "sender", return_value=foreign_task):
            self.dialog.add_online_layers()

        add_online_layer.assert_not_called()

    @patch("ogcapiclient.gui.ogc_api_client_dialog.LayerManager.add_online_layer")
    def test_add_online_layers(self, add_online_layer):
        layer = create_prepared_layer()

        task = DummyTask(data=[layer])

        self.dialog.task = task

        with (
            patch.object(self.dialog, "sender", return_value=task),
            patch.object(self.dialog, "layer_preparation_finished"),
        ):
            self.dialog.add_online_layers()

        add_online_layer.assert_called_once()

    @patch("ogcapiclient.gui.ogc_api_client_dialog.LayerManager.add_online_layer")
    def test_add_online_layers_multiple(self, add_online_layer):
        layers = [
            create_prepared_layer("roads"),
            create_prepared_layer("lakes"),
        ]

        task = DummyTask(data=layers)

        self.dialog.task = task

        with (
            patch.object(self.dialog, "sender", return_value=task),
            patch.object(self.dialog, "layer_preparation_finished"),
        ):
            self.dialog.add_online_layers()

        self.assertEqual(add_online_layer.call_count, 2)

    def test_download_finished_success(self):
        task = DummyTask()

        self.dialog.task = task
        self.dialog.button_add.setEnabled(False)

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.download_finished()

        self.assertTrue(self.dialog.button_add.isEnabled())
        self.assertIsNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.information")
    def test_download_finished_canceled(self, information):
        task = DummyTask(canceled=True)

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.download_finished()

        information.assert_called_once()

    @patch("ogcapiclient.gui.ogc_api_client_dialog.QMessageBox.critical")
    def test_download_finished_exception(self, critical):
        task = DummyTask(exception=Exception())

        self.dialog.task = task

        with patch.object(self.dialog, "sender", return_value=task):
            self.dialog.download_finished()

        critical.assert_called_once()

    def test_download_finished_other_task(self):
        self.dialog.task = DummyTask()

        foreign_task = DummyTask()

        with patch.object(self.dialog, "sender", return_value=foreign_task):
            self.dialog.download_finished()

        self.assertIsNotNone(self.dialog.task)

    @patch("ogcapiclient.gui.ogc_api_client_dialog.LayerManager.add_offline_layer")
    def test_add_offline_layers_do_not_run_if_other_task(self, add_offline_layer):
        self.dialog.task = DummyTask()

        foreign_task = DummyTask(data=[create_downloaded_layer()])

        with patch.object(self.dialog, "sender", return_value=foreign_task):
            self.dialog.add_offline_layers()

        add_offline_layer.assert_not_called()

    @patch("ogcapiclient.gui.ogc_api_client_dialog.LayerManager.add_offline_layer")
    def test_add_offline_layers(self, add_offline_layer):
        layers = [
            create_downloaded_layer("roads"),
            create_downloaded_layer("lakes"),
        ]

        task = DummyTask(data=layers)

        self.dialog.task = task

        with (
            patch.object(self.dialog, "sender", return_value=task),
            patch.object(self.dialog, "download_finished"),
        ):
            self.dialog.add_offline_layers()

        self.assertEqual(add_offline_layer.call_count, 2)


if __name__ == "__main__":
    unittest.main()
