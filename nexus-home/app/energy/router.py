"""Energy monitoring API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.auth import verify_api_key
from app.energy import service
from app.energy.schemas import EnergyReadingCreate

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/readings")
async def add_reading(reading: EnergyReadingCreate):
    """Record an energy reading."""
    await service.record_reading(reading.device_id, reading.watts)
    return {"recorded": True}


@router.get("/usage")
async def get_usage(
    device_id: str | None = None,
    hours: int = Query(24, ge=1, le=8760),
):
    """Get energy usage data."""
    return await service.get_usage(device_id, hours)


@router.get("/summary")
async def get_summary(hours: int = Query(24, ge=1, le=8760)):
    """Get energy usage summary."""
    return await service.get_summary(hours)
