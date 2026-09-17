import logging
import sys


APP_LOGGER_NAME = "app"
APP_LOG_HANDLER_MARKER = "_app_logging_handler"


def configure_logging() -> None:
    """Configure application logging for console-based environments."""

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(logging.INFO)

    if not any(
        getattr(handler, APP_LOG_HANDLER_MARKER, False)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s - %(message)s"
            )
        )

        setattr(handler, APP_LOG_HANDLER_MARKER, True)
        logger.addHandler(handler)