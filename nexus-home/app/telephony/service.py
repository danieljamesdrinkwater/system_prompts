"""Call management and history."""

from app.database import get_db
from app.telephony.sip_client import sip_client


async def dial(number: str) -> dict:
    """Initiate a call."""
    return await sip_client.dial(number)


async def hangup() -> dict:
    """Hang up current call."""
    return await sip_client.hangup()


async def get_call_history(limit: int = 50) -> list[dict]:
    """Get recent call history."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM call_history ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_voicemails() -> list[dict]:
    """Get voicemail messages."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM call_history WHERE voicemail = 1 ORDER BY started_at DESC"
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_status() -> dict:
    """Get telephony status."""
    return {
        "registered": sip_client.is_registered,
    }
