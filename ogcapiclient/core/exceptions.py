"""Custom exception types."""

from ogcapiclient.core.enums import ClientError


class OgcApiClientError(Exception):
    """Raised by OgcApiClient and its dependencies when an operation fails.

    Carries a typed ``error_code`` and a human-readable ``message`` suitable
    for display in the plugin UI.
    """

    def __init__(self, error_code: ClientError, message: str) -> None:
        """Initializes the exception.

        :param error_code:  Enum member identifying the category of failure.
        :type error_code: ClientError
        :param message: Human-readable description of the error.
        :type message: str
        """
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        """Returns the human-readable message."""
        return self.message


class MbTilesError(Exception):
    """Raised by MbTilesWriter in case of errors."""

    pass


class CrsNormalizationError(Exception):
    """Raised when a CRS string cannot be resolved to a valid, recognised CRS."""

    pass


class InvalidLayerError(Exception):
    """Raised when an invalid layer created from the URI sring."""

    pass


class WriteDataError(Exception):
    """Raised when writing data to cache fails."""

    pass
