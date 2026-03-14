"""Notification schemas."""

from pydantic import BaseModel


class NotificationRequest(BaseModel):
    channel: str = "email"  # email, webhook, ntfy
    recipient: str | None = None
    subject: str = ""
    body: str = ""


class NotificationResponse(BaseModel):
    id: int
    channel: str
    recipient: str | None
    subject: str | None
    body: str | None
    status: str
    sent_at: str | None
