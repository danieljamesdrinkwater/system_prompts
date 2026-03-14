"""Telephony API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.auth import verify_api_key
from app.telephony import service
from app.telephony.schemas import DialRequest

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/status")
async def get_status():
    """Get SIP registration status."""
    return await service.get_status()


@router.post("/dial")
async def dial(req: DialRequest):
    """Dial a phone number."""
    return await service.dial(req.number)


@router.post("/hangup")
async def hangup():
    """Hang up current call."""
    return await service.hangup()


@router.get("/history")
async def call_history(limit: int = Query(50, ge=1, le=200)):
    """Get call history."""
    return await service.get_call_history(limit)


@router.get("/voicemail")
async def voicemails():
    """Get voicemail messages."""
    return await service.get_voicemails()
