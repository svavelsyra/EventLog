"""Logging handler that forwards warning text into the main-window status bar."""

from __future__ import annotations

from collections.abc import Callable
import logging


class StatusBarHandler(logging.Handler):
    """Push warning-level log messages into a GUI-owned status callback."""

    def __init__(
        self,
        status_callback: Callable[[str], None],
        *,
        level: int = logging.WARNING,
    ) -> None:
        super().__init__(level=level)
        self._status_callback = status_callback

    def emit(self, record: logging.LogRecord) -> None:
        """Forward one formatted log record to the GUI status callback."""
        try:
            message = self.format(record) or record.getMessage()
            self._status_callback(f"Last log: {message}")
        except Exception:
            self.handleError(record)


__all__ = ["StatusBarHandler"]
