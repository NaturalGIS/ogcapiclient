import unittest

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtTest import QSignalSpy

from ogcapiclient.qgis_backend.feedback import QgisFeedback
from ogcapiclient.tests.mocks import DummyTask


class TestQgisFeedback(unittest.TestCase):
    def test_not_canceled_initially(self):
        task = DummyTask()
        feedback = QgisFeedback(task)
        self.assertFalse(feedback.is_canceled())
        self.assertFalse(feedback.isCanceled())

    def test_task_cancel_propagates_to_qgis_feedback(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        task.cancel()
        QCoreApplication.processEvents()

        self.assertTrue(feedback.is_canceled())

    def test_direct_cancel_on_feedback_sets_canceled(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        feedback.cancel()

        self.assertTrue(feedback.is_canceled())
        self.assertTrue(feedback.isCanceled())

    def test_set_progress_updates_task_progress(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        feedback.set_progress(50.0)

        self.assertEqual(task.progress(), 50.0)


if __name__ == "__main__":
    unittest.main()
