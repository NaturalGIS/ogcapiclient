"""Implementation of the Logger protocol."""

from qgis.core import Qgis, QgsMessageLog

from ogcapiclient.core.enums import LogLevel


class QgisLogger:
    """Implementation of the Logger protocol using QgsMessageLog."""

    # Maps plugin LogLevel values to the corresponding QGIS message levels.
    _LEVEL_MAP = {
        LogLevel.INFO: Qgis.MessageLevel.Info,
        LogLevel.WARNING: Qgis.MessageLevel.Warning,
        LogLevel.CRITICAL: Qgis.MessageLevel.Critical,
        LogLevel.SUCCESS: Qgis.MessageLevel.Success,
    }

    def __init__(self, tag: str = "OGC API Client") -> None:
        """Initialise the logger.

        :param tag: Category for the log messages.
        :type tag: str
        """
        self.tag = tag

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Writes message to the QGIS message log.

        :param message: Text to log.
        :type message: str
        :param level: Severity level.
        :type level: LogLevel
        """
        qgis_level = self._LEVEL_MAP.get(level, Qgis.MessageLevel.Info)
        QgsMessageLog.logMessage(message, self.tag, qgis_level)
