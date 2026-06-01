"""Implementation of the Loader protocol with QGIS network classes."""

import json

from qgis.core import QgsBlockingNetworkRequest, QgsFeedback
from qgis.PyQt.QtCore import QCoreApplication, Qt, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

from ogcapiclient.core.enums import ClientError
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.interfaces import Feedback


class QgisLoader:
    """Implementation of the Loader protocol using QgsBlockingNetworkRequest."""

    # Maps QgsBlockingNetworkRequest error codes to plugin-level ClientError values.
    _ERROR_MAP = {
        QgsBlockingNetworkRequest.ErrorCode.NoError: None,
        QgsBlockingNetworkRequest.ErrorCode.NetworkError: ClientError.NETWORK_ERROR,
        QgsBlockingNetworkRequest.ErrorCode.TimeoutError: ClientError.TIMEOUT_ERROR,
        QgsBlockingNetworkRequest.ErrorCode.ServerExceptionError: ClientError.SERVER_ERROR,
    }

    def __init__(self, feedback: Feedback = None) -> None:
        self.feedback = feedback

    def get_json(self, url: str, auth_cfg: str = "") -> dict:
        """Performs a blocking HTTP GET for URL and returns the body as a dictionary.

        :param url: Fully-qualified URL to request.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str

        :returns: Response body parsed as a Python dictionary.
        :rtype: dict

        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """
        network_request = QNetworkRequest(QUrl(url))
        network_request.setRawHeader(b"Accept", b"application/json")

        blocking_request = QgsBlockingNetworkRequest()
        if auth_cfg:
            blocking_request.setAuthCfg(auth_cfg)

        request_feedback = QgsFeedback()
        if self.feedback:
            if self.feedback.is_canceled():
                raise OgcApiClientError(
                    ClientError.CANCELLED, "Operation was cancelled."
                )

            self.feedback.canceled.connect(
                request_feedback.cancel, Qt.ConnectionType.DirectConnection
            )

        flags = QgsBlockingNetworkRequest.RequestFlags()
        if hasattr(QgsBlockingNetworkRequest, "RequestFlag") and hasattr(
            QgsBlockingNetworkRequest.RequestFlag, "EmptyResponseIsValid"
        ):
            flags |= QgsBlockingNetworkRequest.RequestFlag.EmptyResponseIsValid

        try:
            result = blocking_request.get(
                network_request, True, request_feedback, flags
            )
            reply = blocking_request.reply()

            if request_feedback.isCanceled() or (
                self.feedback and self.feedback.is_canceled()
            ):
                raise OgcApiClientError(
                    ClientError.CANCELLED, "Operation was cancelled."
                )

            if result != QgsBlockingNetworkRequest.ErrorCode.NoError:
                error_type = self._ERROR_MAP.get(result, ClientError.NETWORK_ERROR)
                http_code = (
                    reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                    if reply
                    else "N/A"
                )
                raise OgcApiClientError(
                    error_type,
                    self.tr(
                        "HTTP request failed for {url}: [{code}] ({message})"
                    ).format(
                        url=url, code=http_code, message=blocking_request.errorMessage()
                    ),
                )

            http_code = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            if http_code >= 400:
                raise OgcApiClientError(
                    ClientError.SERVER_ERROR,
                    self.tr("Server returned error {code} for {url}").format(
                        code=http_code, url=url
                    ),
                )

            data = reply.content().data()
            if not data:
                raise OgcApiClientError(
                    ClientError.PARSE_ERROR,
                    self.tr("Server returned an empty response."),
                )

            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise OgcApiClientError(
                    ClientError.DECODE_ERROR,
                    self.tr("Failed to decode reply as UTF-8: {error}").format(
                        error=str(e)
                    ),
                )

            try:
                return json.loads(decoded)
            except json.JSONDecodeError as e:
                snippet = decoded[:100] + "…" if len(decoded) > 100 else decoded
                raise OgcApiClientError(
                    ClientError.PARSE_ERROR,
                    self.tr("Failed to parse JSON: {error}\nSnippet: {snippet}").format(
                        error=str(e), snippet=snippet
                    ),
                )
        finally:
            if self.feedback:
                try:
                    self.feedback.canceled.disconnect(request_feedback.cancel)
                except TypeError:
                    pass

    def tr(self, string: str) -> str:
        """Returns the translation of string.

        :param string: String to translate.
        :type string: str

        :returns: Translated string, or original string if no translation exists.
        :rtype: str
        """
        return QCoreApplication.translate(self.__class__.__name__, string)
