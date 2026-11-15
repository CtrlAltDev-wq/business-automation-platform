import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def trigger_lead_created(payload: dict) -> dict:
    """POST a lead.created event to the configured n8n webhook node."""
    if not settings.n8n_webhook_url:
        logger.info(
            "n8n webhook URL is not configured, event for lead %s skipped",
            payload.get("id"),
        )
        return {"dry_run": True}

    response = httpx.post(
        settings.n8n_webhook_url,
        json={"event": "lead.created", "data": payload},
        timeout=10.0,
    )
    response.raise_for_status()

    logger.info(
        "n8n workflow triggered for lead %s (status %s)",
        payload.get("id"),
        response.status_code,
    )

    return {"status_code": response.status_code}
