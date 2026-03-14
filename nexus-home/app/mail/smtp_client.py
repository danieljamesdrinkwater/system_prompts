"""SMTP client for sending mail."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_mail(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP."""
    settings = get_settings()
    cfg = settings.mail.smtp
    if not cfg.host:
        logger.warning("SMTP not configured")
        return False

    msg = EmailMessage()
    msg["From"] = cfg.from_address
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.username or None,
            password=cfg.password or None,
            start_tls=True,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.error("SMTP send failed: %s", e)
        return False
