import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Send application logs to stdout with a consistent, greppable format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()

    # Avoid adding duplicate handlers when uvicorn reloads the process.
    if not root.handlers:
        root.addHandler(handler)

    root.setLevel(level.upper())
