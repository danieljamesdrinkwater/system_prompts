"""Mail management service."""

from app.database import get_db
from app.mail.imap_client import imap_client
from app.mail.smtp_client import send_mail


async def sync_inbox(limit: int = 50) -> int:
    """Sync inbox from IMAP server."""
    return await imap_client.sync_inbox(limit)


async def list_messages(folder: str = "INBOX", limit: int = 50, offset: int = 0) -> list[dict]:
    """List cached email messages."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM mail_cache WHERE folder = ? ORDER BY received_at DESC LIMIT ? OFFSET ?",
            (folder, limit, offset),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_unread_count() -> int:
    """Get count of unread messages."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM mail_cache WHERE is_read = 0"
        )
        row = await cursor.fetchone()
        return dict(row)["count"] if row else 0


async def mark_read(uid: str) -> bool:
    """Mark a message as read."""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE mail_cache SET is_read = 1 WHERE uid = ?", (uid,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def search_messages(query: str, limit: int = 20) -> list[dict]:
    """Search messages by subject or sender."""
    async with get_db() as db:
        pattern = f"%{query}%"
        cursor = await db.execute(
            "SELECT * FROM mail_cache WHERE subject LIKE ? OR from_addr LIKE ? "
            "ORDER BY received_at DESC LIMIT ?",
            (pattern, pattern, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def compose(to: str, subject: str, body: str) -> bool:
    """Send an email."""
    return await send_mail(to, subject, body)
