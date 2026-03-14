"""Notification dispatch — email, webhook, ntfy."""

import logging

import httpx
import aiosmtplib
from email.message import EmailMessage

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    settings = get_settings()
    cfg = settings.notifications
    if not cfg.smtp_host:
        logger.warning("SMTP not configured, skipping email")
        return False

    msg = EmailMessage()
    msg["From"] = cfg.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=cfg.smtp_host,
            port=cfg.smtp_port,
            username=cfg.smtp_user or None,
            password=cfg.smtp_pass or None,
            start_tls=True,
        )
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


async def send_webhook(url: str, payload: dict) -> bool:
    """Send webhook POST request."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code < 400
    except Exception as e:
        logger.error("Webhook failed for %s: %s", url, e)
        return False


async def send_ntfy(topic: str, title: str, body: str) -> bool:
    """Send push notification via ntfy.sh."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://ntfy.sh/{topic}",
                headers={"Title": title},
                content=body,
            )
            return resp.status_code < 400
    except Exception as e:
        logger.error("ntfy send failed: %s", e)
        return False


async def notify(channel: str, recipient: str | None, subject: str, body: str) -> bool:
    """Dispatch notification to the appropriate channel."""
    settings = get_settings()
    success = False

    if channel == "email" and recipient:
        success = await send_email(recipient, subject, body)
    elif channel == "webhook":
        urls = [recipient] if recipient else settings.notifications.webhook_urls
        for url in urls:
            success = await send_webhook(url, {"subject": subject, "body": body}) or success
    elif channel == "ntfy":
        topic = recipient or settings.notifications.ntfy_topic
        if topic:
            success = await send_ntfy(topic, subject, body)

    # Log to DB
    async with get_db() as db:
        await db.execute(
            "INSERT INTO notifications (channel, recipient, subject, body, status) VALUES (?, ?, ?, ?, ?)",
            (channel, recipient, subject, body, "sent" if success else "failed"),
        )
        await db.commit()

    return success
