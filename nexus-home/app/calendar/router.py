"""Calendar API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import verify_api_key
from app.calendar import service
from app.calendar.schemas import EventCreate

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/events")
async def list_events(
    days_ahead: int = Query(30, ge=1, le=365),
    source: str | None = None,
):
    """List upcoming calendar events."""
    return await service.list_events(days_ahead, source)


@router.post("/events")
async def create_event(event: EventCreate):
    """Create a local calendar event."""
    return await service.create_event(
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        location=event.location,
        all_day=event.all_day,
        source=event.source,
    )


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """Delete a calendar event."""
    deleted = await service.delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": event_id}


@router.post("/sync")
async def sync_calendars():
    """Trigger calendar sync from all sources."""
    result = await service.sync_all()
    return result
