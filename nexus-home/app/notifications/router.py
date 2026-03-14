"""Notification API endpoints."""

from fastapi import APIRouter, Depends

from app.auth import verify_api_key
from app.database import get_db
from app.notifications.schemas import NotificationRequest
from app.notifications import service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/send")
async def send_notification(req: NotificationRequest):
    """Send a notification."""
    success = await service.notify(req.channel, req.recipient, req.subject, req.body)
    return {"sent": success}


@router.get("/")
async def list_notifications(limit: int = 50):
    """List recent notifications."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM notifications ORDER BY sent_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
