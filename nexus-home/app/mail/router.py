"""Mail API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.auth import verify_api_key
from app.mail import service
from app.mail.schemas import ComposeRequest

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/inbox")
async def list_inbox(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List inbox messages."""
    return await service.list_messages("INBOX", limit, offset)


@router.get("/unread")
async def unread_count():
    """Get unread message count."""
    count = await service.get_unread_count()
    return {"unread": count}


@router.post("/sync")
async def sync_inbox():
    """Sync inbox from IMAP server."""
    count = await service.sync_inbox()
    return {"synced": count}


@router.post("/read/{uid}")
async def mark_read(uid: str):
    """Mark a message as read."""
    success = await service.mark_read(uid)
    return {"marked": success}


@router.get("/search")
async def search(q: str = Query(..., min_length=1)):
    """Search messages."""
    return await service.search_messages(q)


@router.post("/send")
async def send_mail(req: ComposeRequest):
    """Send an email."""
    success = await service.compose(req.to, req.subject, req.body)
    return {"sent": success}
