import logging

from websockets.exceptions import ConnectionClosedError


class _RecordCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_expected_websocket_disconnect_is_logged_at_info() -> None:
    from app.core.runtime_logging import configure_runtime_logging

    logger = logging.getLogger("uvicorn.error")
    collector = _RecordCollector()
    original_handlers = logger.handlers[:]
    original_filters = logger.filters[:]
    original_level = logger.level
    original_propagate = logger.propagate

    try:
        logger.handlers = [collector]
        logger.filters = []
        logger.setLevel(logging.INFO)
        logger.propagate = False
        configure_runtime_logging()

        disconnect = ConnectionClosedError(None, None)
        logger.error(
            "connection handler failed",
            exc_info=(type(disconnect), disconnect, disconnect.__traceback__),
        )
        unrelated = RuntimeError("server bug")
        logger.error(
            "connection handler failed",
            exc_info=(type(unrelated), unrelated, unrelated.__traceback__),
        )

        assert len(collector.records) == 2
        assert collector.records[0].levelno == logging.INFO
        assert collector.records[0].levelname == "INFO"
        assert collector.records[0].event == "websocket_client_disconnect"
        assert collector.records[1].levelno == logging.ERROR
        assert not hasattr(collector.records[1], "event")
    finally:
        logger.handlers = original_handlers
        logger.filters = original_filters
        logger.setLevel(original_level)
        logger.propagate = original_propagate
