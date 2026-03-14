"""Energy monitoring schemas."""

from pydantic import BaseModel


class EnergyReadingCreate(BaseModel):
    device_id: str
    watts: float


class EnergySummary(BaseModel):
    total_kwh: float
    device_breakdown: list[dict]
    peak_watts: float
    readings_count: int
