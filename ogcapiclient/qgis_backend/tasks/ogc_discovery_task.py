from qgis.core import QgsTask

from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.interfaces import Feedback, Loader, Logger
from ogcapiclient.core.ogc_api_client import OgcApiClient
from ogcapiclient.qgis_backend.feedback import QgisFeedback
from ogcapiclient.qgis_backend.loader import QgisLoader
from ogcapiclient.qgis_backend.logger import QgisLogger


class OgcDiscoveryTask(QgsTask):
    """Task to discover OGC API collections available on the server."""

    def __init__(
        self,
        url: str,
        auth_cfg: str = "",
        loader: Loader = None,
        logger: Logger = None,
        feedback: Feedback = None,
    ) -> None:
        """Initializes the discovery task.

        :param url: Target server URL.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        :param loader: Loader implementation.
        :type loader: Loader
        :param logger: Logger implementation.
        :type logger: Logger
        :param feedback: Feedback implementation.
        :type feedback: Feedback
        """

        super().__init__(
            "Discover OGC API",
            QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt,
        )
        self.url = url
        self.auth_cfg = auth_cfg
        self.feedback = feedback if feedback else QgisFeedback(self)
        self.logger = logger if logger else QgisLogger()
        self.loader = loader if loader else QgisLoader(self.logger, self.feedback)
        self.data = None
        self.exception = None

    def run(self) -> bool:
        """Executes the discovery.

        :returns: Whether the discovery was succesfull.
        :rtype: bool
        """
        client = OgcApiClient(self.loader, self.logger, self.feedback, self.auth_cfg)
        try:
            self.data = client.connect(self.url)
            return True
        except OgcApiClientError as e:
            self.logger.log(
                self.tr(
                    "Failed to perform discovery of the OGC API server {url}: {error}."
                ).format(url=self.url, error=str(e))
            )
            self.exception = e
            return False

    def cancel(self) -> None:
        """Triggered when the user cancels the task."""
        if self.feedback:
            self.feedback.cancel()
        super().cancel()
