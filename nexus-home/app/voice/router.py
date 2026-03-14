"""Voice module API routes — transcription, synthesis, and voice commands."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
import io

from app.auth import verify_api_key
from app.voice.schemas import SpeakRequest, TranscribeResponse, VoiceCommandResponse
from app.voice.stt import stt_engine
from app.voice.tts import tts_engine
from app.ai.intent import intent_parser

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_devices() -> list[dict]:
    """Fetch all devices from the database as plain dicts."""
    from app.database import get_db

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, type, room, mqtt_topic, protocol FROM devices"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def _execute_device_command(device_id: str, command: dict) -> bool:
    """Publish a command to the device via MQTT."""
    import json
    from app.database import get_db

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT mqtt_topic FROM devices WHERE id = ?",
            (device_id,),
        )
        device = await cursor.fetchone()

    if device is None or not device["mqtt_topic"]:
        return False

    try:
        from app.devices.mqtt_client import mqtt_manager

        cmd_topic = f"cmnd/{device['mqtt_topic']}/Backlog"
        await mqtt_manager.publish_command(cmd_topic, command)
        return True
    except Exception as exc:
        logger.error("Failed to execute command for device %s: %s", device_id, exc)
        return False


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = None,
    _key: str = Depends(verify_api_key),
):
    """Transcribe an uploaded audio file to text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        result = await stt_engine.transcribe(audio_bytes, language=language)
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    return TranscribeResponse(
        text=result["text"],
        language=result.get("language"),
        duration=result.get("duration"),
    )


@router.post("/speak")
async def speak(
    request: SpeakRequest,
    _key: str = Depends(verify_api_key),
):
    """Synthesize text to speech and return WAV audio."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        audio_bytes = await tts_engine.synthesize(request.text)
    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )


@router.post("/command", response_model=VoiceCommandResponse)
async def voice_command(
    file: UploadFile = File(...),
    language: str | None = None,
    _key: str = Depends(verify_api_key),
):
    """Full voice pipeline: transcribe -> intent parse -> execute -> synthesize."""
    # 1. Transcribe
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        transcription = await stt_engine.transcribe(audio_bytes, language=language)
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    text = transcription["text"]
    if not text.strip():
        return VoiceCommandResponse(
            transcription="",
            ai_response="I didn't catch that. Could you try again?",
            executed=False,
        )

    # 2. Parse intent
    devices = await _get_devices()
    intent = await intent_parser.parse(text, devices)

    # 3. Execute if it's a device command
    executed = False
    if intent and intent["type"] == "device_command" and intent.get("device_id"):
        executed = await _execute_device_command(
            intent["device_id"], intent.get("command", {})
        )

    ai_response = intent.get("response", "Done.") if intent else "I couldn't understand that."

    # 4. Synthesize response audio (fire-and-forget for URL generation is not
    #    practical here, so we note the audio_url as None — callers can use
    #    the /speak endpoint separately if they want audio).
    return VoiceCommandResponse(
        transcription=text,
        ai_response=ai_response,
        executed=executed,
        audio_url=None,
    )
