"""Google Calendar API integration."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Sync events from Google Calendar."""

    def __init__(self) -> None:
        self._service = None

    async def _get_service(self):
        """Lazily initialize Google Calendar service."""
        if self._service is not None:
            return self._service
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            settings = get_settings()
            creds_file = settings.calendar.google.credentials_file
            if not creds_file:
                return None

            creds = service_account.Credentials.from_service_account_file(
                creds_file,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except (ImportError, Exception) as e:
            logger.warning("Google Calendar setup failed: %s", e)
            return None

    async def sync_events(self, days_ahead: int = 30) -> int:
        """Sync events from Google Calendar to local database."""
        service = await self._get_service()
        if not service:
            return 0

        try:
            settings = get_settings()
            now = datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

            result = service.events().list(
                calendarId=settings.calendar.google.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = result.get("items", [])
            count = 0

            async with get_db() as db:
                for event in events:
                    event_id = event["id"]
                    title = event.get("summary", "Untitled")
                    description = event.get("description")
                    location = event.get("location")

                    start = event["start"].get("dateTime") or event["start"].get("date")
                    end = event["end"].get("dateTime") or event["end"].get("date")
                    all_day = 1 if "date" in event["start"] else 0

                    await db.execute(
                        """INSERT OR REPLACE INTO calendar_events
                        (id, source, title, description, start_time, end_time, location, all_day)
                        VALUES (?, 'google', ?, ?, ?, ?, ?, ?)""",
                        (event_id, title, description, start, end, location, all_day),
                    )
                    count += 1
                await db.commit()

            logger.info("Synced %d Google Calendar events", count)
            return count
        except Exception as e:
            logger.error("Google Calendar sync failed: %s", e)
            return 0


google_calendar_client = GoogleCalendarClient()
