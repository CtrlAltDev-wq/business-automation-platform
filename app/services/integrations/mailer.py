import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_auto_reply(payload: dict) -> dict:
    """Send the auto-reply template to the lead.

    Without an SMTP host the message is only logged, which keeps local demos
    runnable without real credentials.
    """
    recipient = payload.get("email")

    if not recipient:
        logger.info("Lead %s has no email, auto-reply skipped", payload.get("id"))
        return {"skipped": "no_email"}

    subject = settings.auto_reply_subject
    body = settings.auto_reply_body.format(
        name=payload.get("name") or "there",
    )

    if not settings.smtp_host:
        logger.info(
            "SMTP is not configured, auto-reply for lead %s logged only",
            payload.get("id"),
        )
        return {"dry_run": True, "to": recipient, "subject": subject}

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(message)

    logger.info("Auto-reply sent to %s for lead %s", recipient, payload.get("id"))

    return {"to": recipient}
