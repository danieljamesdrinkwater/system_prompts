"""Calendar module schemas."""

from datetime import datetime
from pydantic import BaseModel


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    all_day: bool = False
    source: str = "local"


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    all_day: bool | None = None
