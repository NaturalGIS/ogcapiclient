from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ogcapiclient.core.enums import CollectionType
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.ogc_api_client import OgcApiClient
from ogcapiclient.qgis_backend.feedback import QgisFeedback
from ogcapiclient.qgis_backend.loader import QgisLoader
from ogcapiclient.qgis_backend.logger import QgisLogger


class LayerPreparationTask(QgsTask):
    """Task to fetch necessary details and prepare layers."""

    def __init__(
        self,
        landing_page: str,
        collections: list[tuple[Collection, CollectionType]],
        auth_cfg: str = "",
    ) -> None:
        """Initializes the layer preparation task.

        :param landing_page: The landing page URL.
        :type landing_page: str
        :param collections: A list of tuples containing the Collection and type.
        :type collections: list[tuple[Collection, CollectionType]]
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        """

        super().__init__(
            "Prepare layers",
            QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt,
        )
        self.landing_page = landing_page
        self.collections = collections
        self.auth_cfg = auth_cfg
        self.feedback = None
        self.data = None
        self.exception = None

    def run(self) -> bool:
        """Executes the layer preparation.

        :returns: Whether the layer preparation was succesfull.
        :rtype: bool
        """

        self.feedback = QgisFeedback(self)
        loader = QgisLoader(self.feedback)
        logger = QgisLogger()

        client = OgcApiClient(loader, logger, self.feedback, self.auth_cfg)
        try:
            self.data = client.prepare_layers(self.landing_page, self.collections)
            return True
        except OgcApiClientError as e:
            self.exception = e
            return False

    def cancel(self) -> None:
        """Triggered when the user cancels the task."""
        if self.feedback:
            self.feedback.cancel()
        super().cancel()
