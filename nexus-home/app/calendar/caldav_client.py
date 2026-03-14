"""CalDAV client for syncing with self-hosted calendar servers."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


class CalDAVClient:
    """Sync events from a CalDAV server (Nextcloud, Radicale, Baikal)."""

    def __init__(self) -> None:
        self._client = None

    async def _get_client(self):
        """Lazily initialize CalDAV client."""
        if self._client is not None:
            return self._client
        try:
            import caldav
            settings = get_settings()
            cfg = settings.calendar.caldav
            if not cfg.url:
                return None
            self._client = caldav.DAVClient(
                url=cfg.url,
                username=cfg.username,
                password=cfg.password,
            )
            return self._client
        except ImportError:
            logger.warning("caldav library not installed")
            return None

    async def sync_events(self, days_ahead: int = 30) -> int:
        """Sync events from CalDAV to local database."""
        client = await self._get_client()
        if not client:
            return 0

        try:
            principal = client.principal()
            calendars = principal.calendars()
            count = 0
            now = datetime.now()
            end = now + timedelta(days=days_ahead)

            async with get_db() as db:
                for cal in calendars:
                    events = cal.date_search(start=now, end=end, expand=True)
                    for event in events:
                        vevent = event.vobject_instance.vevent
                        event_id = str(vevent.uid.value)
                        title = str(vevent.summary.value) if hasattr(vevent, "summary") else "Untitled"
                        start = vevent.dtstart.value
                        end_time = vevent.dtend.value if hasattr(vevent, "dtend") else None
                        description = str(vevent.description.value) if hasattr(vevent, "description") else None
                        location = str(vevent.location.value) if hasattr(vevent, "location") else None

                        # Handle date vs datetime
                        if not isinstance(start, datetime):
                            start = datetime.combine(start, datetime.min.time())
                            all_day = 1
                        else:
                            all_day = 0

                        if end_time and not isinstance(end_time, datetime):
                            end_time = datetime.combine(end_time, datetime.min.time())

                        await db.execute(
                            """INSERT OR REPLACE INTO calendar_events
                            (id, source, title, description, start_time, end_time, location, all_day)
                            VALUES (?, 'caldav', ?, ?, ?, ?, ?, ?)""",
                            (event_id, title, description, start.isoformat(),
                             end_time.isoformat() if end_time else None, location, all_day),
                        )
                        count += 1
                await db.commit()
            logger.info("Synced %d CalDAV events", count)
            return count
        except Exception as e:
            logger.error("CalDAV sync failed: %s", e)
            return 0


caldav_client = CalDAVClient()
