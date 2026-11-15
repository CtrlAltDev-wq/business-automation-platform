"""Retry worker for outbound integrations.

Usage:
    python -m app.workers.integration_worker --once
    python -m app.workers.integration_worker --interval 15
"""

import argparse
import logging
import time

from app.core.config import settings
from app.core.logging import configure_logging
from app.services import integration_service

logger = logging.getLogger(__name__)


def run(once: bool, interval: int) -> None:
    """Dispatch due events forever, or only once when --once is passed."""
    while True:
        result = integration_service.run_pending_once()

        logger.info(
            "Integration dispatch: processed=%s sent=%s retrying=%s failed=%s",
            result["processed"],
            result["sent"],
            result["retrying"],
            result["failed"],
        )

        if once:
            return

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dispatch pending Google Sheets / email / n8n events.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="process due events and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="seconds between runs when running continuously (default: 15)",
    )

    args = parser.parse_args()

    configure_logging()

    logger.info(
        "Integration worker started (max attempts: %s, base delay: %ss)",
        settings.integration_max_attempts,
        settings.integration_retry_base_seconds,
    )

    try:
        run(args.once, args.interval)
    except KeyboardInterrupt:
        logger.info("Integration worker stopped")


if __name__ == "__main__":
    main()
