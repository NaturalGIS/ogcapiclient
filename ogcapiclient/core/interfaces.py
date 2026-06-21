"""Interfaces for injected dependencies."""

from typing import Protocol

from ogcapiclient.core.enums import LogLevel


class Loader(Protocol):
    """Fetches remote resources and returns their content as parsed JSON."""

    def get_json(self, url: str, auth_cfg: str | None) -> dict:
        """Fetches a JSON resource from the given URL.

        :param url: The full URL to the resource.
        :type url: str
        :param auth_cfg: QGIS Authentication configuration ID.
        :type auth_cfg: str, None

        :returns: The parsed JSON response as a dictionary.
        :rtype: dict, None

        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """
        ...

    def get_data(self, url: str, auth_cfg: str | None) -> object:
        """Fetches data from the given URL.

        :param url: The full URL to the data.
        :type url: str
        :param auth_cfg: QGIS Authentication configuration ID.
        :type auth_cfg: str, None

        :returns: The reply content.
        :rtype: object

        :raises OgcApiClientError: On any network, server, decode, or parse error.
        """
        ...


class Logger(Protocol):
    """Writes diagnostic messages to an appropriate output."""

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Adds a message with the given level to the log.

        :param message: Human-readable description of the event.
        :type url: str
        :param level: The severity level of the message.
        :type level: LogLevel
        """
        ...


class Feedback(Protocol):
    """Reports progress and exposes cancellation state to long-running operations."""

    def set_progress(self, progress: float) -> None:
        """Sets the current progress for the object.

        :param progress: Completion percentage in the range [0, 100].
        :type progress: float
        """
        ...

    def is_canceled(self) -> bool:
        """Tells if cancellation was requested.

        :returns: Whether the operation has been canceled already.
        :rtype: bool
        """
        ...
