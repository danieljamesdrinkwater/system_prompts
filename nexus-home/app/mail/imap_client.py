"""IMAP client for inbox synchronization."""

import logging
import email
from email.header import decode_header
from datetime import datetime

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


def _decode_header(value: str | None) -> str:
    """Decode an email header value."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body_preview(msg: email.message.Message, max_len: int = 200) -> str:
    """Extract a text preview from email body."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")[:max_len]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")[:max_len]
    return ""


class IMAPClient:
    """Sync inbox from IMAP server."""

    async def sync_inbox(self, limit: int = 50) -> int:
        """Fetch recent messages from IMAP and cache locally."""
        settings = get_settings()
        cfg = settings.mail.imap
        if not cfg.host:
            logger.warning("IMAP not configured")
            return 0

        try:
            import imaplib

            if cfg.use_ssl:
                conn = imaplib.IMAP4_SSL(cfg.host, cfg.port)
            else:
                conn = imaplib.IMAP4(cfg.host, cfg.port)

            conn.login(cfg.username, cfg.password)
            conn.select("INBOX")

            _, msg_nums = conn.search(None, "ALL")
            nums = msg_nums[0].split()
            recent = nums[-limit:] if len(nums) > limit else nums
            count = 0

            async with get_db() as db:
                for num in reversed(recent):
                    _, msg_data = conn.fetch(num, "(RFC822 FLAGS)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    uid = msg.get("Message-ID", num.decode())
                    from_addr = _decode_header(msg.get("From"))
                    to_addr = _decode_header(msg.get("To"))
                    subject = _decode_header(msg.get("Subject"))
                    date_str = msg.get("Date", "")
                    body_preview = _get_body_preview(msg)

                    # Check flags for read status
                    flags_data = msg_data[0][0].decode() if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
                    is_read = 1 if "\\Seen" in flags_data else 0

                    await db.execute(
                        """INSERT OR REPLACE INTO mail_cache
                        (uid, folder, from_addr, to_addr, subject, body_preview, is_read, received_at)
                        VALUES (?, 'INBOX', ?, ?, ?, ?, ?, ?)""",
                        (uid, from_addr, to_addr, subject, body_preview, is_read, date_str),
                    )
                    count += 1
                await db.commit()

            conn.logout()
            logger.info("Synced %d emails from IMAP", count)
            return count
        except Exception as e:
            logger.error("IMAP sync failed: %s", e)
            return 0


imap_client = IMAPClient()
