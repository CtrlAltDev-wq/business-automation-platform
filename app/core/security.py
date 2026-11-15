import secrets

from fastapi import Header, HTTPException, status as http_status

from app.core.config import settings


def verify_webhook_secret(
    x_webhook_secret: str | None = Header(
        default=None,
        alias="X-Webhook-Secret",
    ),
) -> None:
    """Reject webhook calls whose shared secret does not match the configured value."""
    # compare_digest keeps the comparison constant-time to avoid timing leaks.
    if not x_webhook_secret or not secrets.compare_digest(
        x_webhook_secret,
        settings.webhook_secret,
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook credentials",
        )
