"""Implementation of the Loader protocol with QGIS network classes."""

import contextlib
import json

from qgis.core import QgsBlockingNetworkRequest, QgsFeedback
from qgis.PyQt.QtCore import QCoreApplication, Qt, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

from ogcapiclient.core.enums import ClientError, LogLevel
from ogcapiclient.core.exceptions import OgcApiClientError
from ogcapiclient.core.interfaces import Feedback, Logger


class QgisLoader:
    """Implementation of the Loader protocol using QgsBlockingNetworkRequest."""

    # Maps QgsBlockingNetworkRequest error codes to plugin-level ClientError values.
    _ERROR_MAP = {
        QgsBlockingNetworkRequest.ErrorCode.NoError: None,
        QgsBlockingNetworkRequest.ErrorCode.NetworkError: ClientError.NETWORK_ERROR,
        QgsBlockingNetworkRequest.ErrorCode.TimeoutError: ClientError.TIMEOUT_ERROR,
        QgsBlockingNetworkRequest.ErrorCode.ServerExceptionError: ClientError.SERVER_ERROR,
    }

    def __init__(self, logger: Logger = None, feedback: Feedback = None) -> None:
        self.logger = logger
        self.feedback = feedback

    def get_json(self, url: str, auth_cfg: str | None = None) -> dict:
        """Performs a blocking HTTP GET for URL and returns the body as a dictionary.

        :param url: Fully-qualified URL to request.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        :returns: Response body parsed as a Python dictionary.
        :rtype: dict
        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """

        data = self._get(url, auth_cfg, {b"Accept": b"application/json"})

        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError as e:
            self._log(
                self.tr("Failed to decode reply as UTF-8: {error}").format(error=str(e))
            )
            raise OgcApiClientError(
                ClientError.DECODE_ERROR, self.tr("Failed to decode reply as UTF-8")
            )

        try:
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            snippet = decoded[:100] + "…" if len(decoded) > 100 else decoded
            self._log(
                self.tr("Failed to parse JSON: {error}\nSnippet: {snippet}").format(
                    error=str(e), snippet=snippet
                )
            )
            raise OgcApiClientError(
                ClientError.PARSE_ERROR, self.tr("Failed to parse JSON.")
            )

    def get_data(self, url: str, auth_cfg: str = "") -> bytes:
        """Performs a blocking HTTP GET for URL and returns the body as a bytes.

        :param url: Fully-qualified URL to request.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        :returns: Response body.
        :rtype: bytes
        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """
        return self._get(url, auth_cfg)

    def _get(
        self, url: str, auth_cfg: str = "", headers: dict[bytes, bytes] | None = None
    ) -> bytes:
        """Performs a blocking HTTP GET for URL and returns the body as a bytes.

        :param url: Fully-qualified URL to request.
        :type url: str
        :param auth_cfg: QGIS authentication configuration ID.
        :type auth_cfg: str
        :returns: Response body.
        :rtype: bytes

        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """
        data = b""
        network_request = QNetworkRequest(QUrl(url))
        if headers:
            for k, v in headers.items():
                network_request.setRawHeader(k, v)

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

        flags = (
            blocking_request.flags()
            | QgsBlockingNetworkRequest.RequestFlag.EmptyResponseIsValid
        )

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

            http_code = (
                reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if reply
                else None
            )

            if result != QgsBlockingNetworkRequest.ErrorCode.NoError:
                error_type = self._ERROR_MAP.get(result, ClientError.NETWORK_ERROR)
                display_code = http_code if http_code is not None else "N/A"
                self._log(
                    self.tr(
                        "HTTP request failed for {url}: [{code}] - {message}."
                    ).format(
                        url=url,
                        code=display_code,
                        message=blocking_request.errorMessage(),
                    )
                )
                raise OgcApiClientError(
                    error_type,
                    self.tr("HTTP request failed for {url}.").format(url=url),
                )

            if http_code and http_code >= 400:
                self._log(
                    self.tr(
                        "Server returned error {code} for {url}.\n{message}"
                    ).format(
                        code=http_code, url=url, message=blocking_request.errorMessage()
                    )
                )
                raise OgcApiClientError(
                    ClientError.SERVER_ERROR,
                    self.tr("Server returned error {code} for {url}").format(
                        code=http_code, url=url
                    ),
                )

            data = reply.content().data()
            if not data:
                raise OgcApiClientError(
                    ClientError.EMPTY_RESPONSE,
                    self.tr("Server returned an empty response."),
                )
            return data
        finally:
            if self.feedback:
                with contextlib.suppress(TypeError):
                    self.feedback.canceled.disconnect(request_feedback.cancel)

    def _log(self, message: str, level: LogLevel = LogLevel.INFO):
        """Helper to log messages.

        :param message: Text to log.
        :type message: str
        :param level: Severity level.
        :type level: LogLevel
        """
        if self.logger:
            self.logger.log(message, level)

    def tr(self, string: str) -> str:
        """Returns the translation of string.

        :param string: String to translate.
        :type string: str
        :returns: Translated string, or original string if no translation exists.
        :rtype: str
        """
        return QCoreApplication.translate(self.__class__.__name__, string)
