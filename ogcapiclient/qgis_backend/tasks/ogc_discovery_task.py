from qgis.core import QgsTask

from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.ogc_api_client import OgcApiClient
from ogcapiclient.qgis_backend.feedback import QgisFeedback
from ogcapiclient.qgis_backend.loader import QgisLoader
from ogcapiclient.qgis_backend.logger import QgisLogger


class OgcDiscoveryTask(QgsTask):
    """Task to discover OGC API collections available on the server."""

    def __init__(self, url: str, auth_cfg: str = "") -> None:
        """Initializes the discovery task.

        :param url: Target server URL.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        """

        super().__init__(
            "Discover OGC API",
            QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt,
        )
        self.url = url
        self.auth_cfg = auth_cfg
        self.feedback = None
        self.data = None
        self.exception = None

    def run(self) -> bool:
        """Executes the discovery.

        :returns: Whether the discovery was succesfull.
        :rtype: bool
        """

        self.feedback = QgisFeedback(self)
        loader = QgisLoader(self.feedback)
        logger = QgisLogger()

        client = OgcApiClient(loader, logger, self.feedback, self.auth_cfg)
        try:
            self.data = client.connect(self.url)
            return True
        except OgcApiClientError as e:
            self.exception = e
            return False

    def cancel(self) -> None:
        """Triggered when the user cancels the task."""
        if self.feedback:
            self.feedback.cancel()
        super().cancel()
