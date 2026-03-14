"""Pydantic schemas for AI API requests and responses."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    context: dict | None = None


class ChatResponse(BaseModel):
    response: str
    intent: dict | None = None


class CommandRequest(BaseModel):
    message: str


class CommandResponse(BaseModel):
    response: str
    executed: bool
    device_id: str | None = None
    command: dict | None = None
