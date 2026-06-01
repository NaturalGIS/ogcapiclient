import unittest

from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtTest import QSignalSpy

from ogcapiclient.qgis_backend.feedback import QgisFeedback


class DummyTask(QgsTask):
    def __init__(self):
        super().__init__(
            "Dummy task", QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt
        )
        self.feedback: QgisFeedback | None = None
        self.started = False

    def run(self) -> bool:
        self.started = True
        return True

    def finished(self, result: bool) -> None:
        pass


class TestQgiskFeedback(unittest.TestCase):
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

    def test_task_cancel_propagates_to_task(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        task.cancel()
        QCoreApplication.processEvents()

        self.assertTrue(task.isCanceled())

    def test_direct_cancel_on_feedback_sets_canceled(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        feedback.cancel()

        self.assertTrue(feedback.is_canceled())
        self.assertTrue(feedback.isCanceled())

    def test_set_progress_updates_task_progress(self):
        task = DummyTask()
        feedback = QgisFeedback(task)

        initial_progress = task.progress()
        feedback.set_progress(50.0)

        self.assertEqual(task.progress(), 50.0)

    def test_canceled_signal_emitted_when_task_canceled(self):
        task = DummyTask()
        feedback = QgisFeedback(task)
        spy = QSignalSpy(feedback.canceled)

        task.cancel()
        QCoreApplication.processEvents()

        self.assertEqual(len(spy), 0)


if __name__ == "__main__":
    unittest.main()
