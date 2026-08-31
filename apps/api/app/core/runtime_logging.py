"""Runtime log normalization for expected transport events."""

import logging

from websockets.exceptions import ConnectionClosedError


class _ExpectedWebSocketDisconnectFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        exc_info = record.exc_info
        if (
            record.getMessage() == "connection handler failed"
            and exc_info
            and isinstance(exc_info[1], ConnectionClosedError)
        ):
            record.levelno = logging.INFO
            record.levelname = "INFO"
            record.event = "websocket_client_disconnect"
        return True


_EXPECTED_WEBSOCKET_DISCONNECT_FILTER = _ExpectedWebSocketDisconnectFilter()


def configure_runtime_logging() -> None:
    """Normalize known client disconnect noise without hiding other errors."""
    logger = logging.getLogger("uvicorn.error")
    if _EXPECTED_WEBSOCKET_DISCONNECT_FILTER not in logger.filters:
        logger.addFilter(_EXPECTED_WEBSOCKET_DISCONNECT_FILTER)
