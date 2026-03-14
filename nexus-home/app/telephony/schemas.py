"""Telephony module schemas."""

from pydantic import BaseModel


class DialRequest(BaseModel):
    number: str
    auto_answer: bool = False


class CallInfo(BaseModel):
    id: int | None = None
    direction: str
    remote_number: str | None = None
    remote_name: str | None = None
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: int | None = None
    voicemail: bool = False
