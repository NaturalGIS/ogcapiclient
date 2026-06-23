from qgis.core import QgsFeedback, QgsTask

from ogcapiclient.core.enums import LogLevel


class MockLogger:
    """Mocks the logger and stores messages for assertion."""

    def __init__(self):
        self.messages: list[tuple[LogLevel, str]] = []

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        self.messages.append((level, message))


class MockLoader:
    """Mocks the HTTP backend, returning predefined JSON or raising exceptions."""

    def __init__(self, responses: dict[str, dict | Exception] = None):
        self.responses = responses or {}
        self.calls = []

    def get_json(self, url: str, auth_cfg: str | None) -> dict:
        self.calls.append((url, auth_cfg))

        if url not in self.responses:
            raise OgcApiClientError(
                ClientError.NETWORK_ERROR, f"Mocked 404: {url} not found."
            )

        response = self.responses[url]
        if isinstance(response, Exception):
            raise response

        return response


class DummyTask(QgsTask):
    def __init__(self, data=None, exception=None, canceled=False):
        super().__init__(
            "Dummy task", QgsTask.Flag.CanCancel | QgsTask.Flag.CancelWithoutPrompt
        )
        self.feedback: QgisFeedback | None = None
        self.started = False
        self.data = data
        self.exception = exception
        self._canceled = canceled

    def run(self) -> bool:
        self.started = True
        return True

    def finished(self, result: bool) -> None:
        pass

    def cancel(self):
        self._canceled = True

    def isCanceled(self):
        return self._canceled
