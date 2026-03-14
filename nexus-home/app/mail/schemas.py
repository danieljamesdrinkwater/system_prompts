"""Mail module schemas."""

from pydantic import BaseModel


class ComposeRequest(BaseModel):
    to: str
    subject: str
    body: str


class MailMessage(BaseModel):
    uid: str
    folder: str = "INBOX"
    from_addr: str | None = None
    to_addr: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    is_read: bool = False
    received_at: str | None = None
