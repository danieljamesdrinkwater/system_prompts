"""Unified calendar operations."""

import uuid
from datetime import datetime

from app.database import get_db
from app.calendar.caldav_client import caldav_client
from app.calendar.google_client import google_calendar_client


async def sync_all() -> dict:
    """Sync from all configured calendar sources."""
    caldav_count = await caldav_client.sync_events()
    google_count = await google_calendar_client.sync_events()
    return {"caldav": caldav_count, "google": google_count}


async def list_events(
    days_ahead: int = 30,
    source: str | None = None,
) -> list[dict]:
    """List upcoming events."""
    async with get_db() as db:
        query = "SELECT * FROM calendar_events WHERE start_time >= datetime('now')"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        query += f" AND start_time <= datetime('now', '+{days_ahead} days')"
        query += " ORDER BY start_time"

        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]


async def create_event(
    title: str,
    start_time: datetime,
    end_time: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
    all_day: bool = False,
    source: str = "local",
) -> dict:
    """Create a local calendar event."""
    event_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO calendar_events (id, source, title, description, start_time, end_time, location, all_day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, source, title, description, start_time.isoformat(),
             end_time.isoformat() if end_time else None, location, int(all_day)),
        )
        await db.commit()
    return {"id": event_id, "title": title}


async def delete_event(event_id: str) -> bool:
    """Delete a calendar event."""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        await db.commit()
        return cursor.rowcount > 0
