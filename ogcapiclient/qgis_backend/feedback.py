"""Progress reporter implementation."""

from qgis.core import QgsFeedback, QgsTask


class QgisFeedback(QgsFeedback):
    """Adapter that bridges the Feedback protocol to QgsTask."""

    def __init__(self, task: QgsTask) -> None:
        """Initialise the adapter with a QgsTask instance.

        :param task: The QgsTask whose setProgress() and isCanceled() methods
        will be delegated to.
        :type task: QgsTask
        """
        super().__init__()
        self.task = task

    def set_progress(self, progress: float) -> None:
        """Forwards completion progress to the object.

        :param progress: Completion percentage in the range [0, 100].
        :type progress: float
        """
        self.task.setProgress(progress)

    def is_canceled(self) -> bool:
        """Tells whether the operation should be terminated.

        :returns:  Whether the operation should be terminated.
        :rtype: bool
        """
        return super().isCanceled() or self.task.isCanceled()

    def cancel(self) -> None:
        """Cancels the current operation."""
        super().cancel()
        if self.task and not self.task.isCanceled():
            self.task.cancel()
