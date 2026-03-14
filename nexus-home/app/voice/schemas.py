"""Pydantic schemas for Voice API requests and responses."""

from pydantic import BaseModel


class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


class SpeakRequest(BaseModel):
    text: str


class VoiceCommandResponse(BaseModel):
    transcription: str
    ai_response: str
    executed: bool
    audio_url: str | None = None
