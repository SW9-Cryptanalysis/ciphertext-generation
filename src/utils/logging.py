import logging
from easy_logging import EasyFormatter
import tqdm


class TqdmLoggingHandler(logging.Handler):
    """Custom logging handler routing logs through tqdm."""

    def emit(self, record: logging.LogRecord) -> None:
        """Format the log record and output it safely above the progress bars."""
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """Create logger using the EasyFormatter and return it."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(EasyFormatter())
        logger.addHandler(handler)

    return logger


def get_logger_tqdm(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """Initialize and return a logger with a custom formatter and tqdm handler.

    Args:
        name (str): The name of the logger.
        level (int, optional): The logging level. Defaults to logging.DEBUG.


    Returns:
        logging.Logger: The fully configured logger.

    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        tqdm_handler = TqdmLoggingHandler()

        tqdm_handler.setFormatter(EasyFormatter())

        logger.addHandler(tqdm_handler)

        logger.propagate = False

    return logger
