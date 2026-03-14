"""Nexus Home — Smart Home AI Server entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.websocket_manager import ws_manager

from app.devices.router import router as devices_router
from app.automation.router import router as automation_router
from app.ai.router import router as ai_router
from app.voice.router import router as voice_router
from app.storage.router import router as storage_router
from app.notifications.router import router as notifications_router
from app.energy.router import router as energy_router
from app.calendar.router import router as calendar_router
from app.mail.router import router as mail_router
from app.telephony.router import router as telephony_router
from app.camera.router import router as camera_router
from app.backup.service import router as backup_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.server.log_level.upper()))
    logger = logging.getLogger("nexus")
    logger.info("Starting Nexus Home server...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start MQTT client
    from app.devices.mqtt_client import mqtt_manager
    await mqtt_manager.start()
    logger.info("MQTT client started")

    # Start automation scheduler
    from app.automation.scheduler import scheduler_manager
    await scheduler_manager.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down Nexus Home...")
    await mqtt_manager.stop()
    await scheduler_manager.stop()

    # Stop camera streams
    from app.camera.manager import camera_manager
    await camera_manager.stop_all()


app = FastAPI(
    title="Nexus Home",
    description="Smart Home AI Server",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(devices_router, prefix="/api/devices", tags=["Devices"])
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(voice_router, prefix="/api/voice", tags=["Voice"])
app.include_router(storage_router, prefix="/api/storage", tags=["Storage"])
app.include_router(notifications_router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(energy_router, prefix="/api/energy", tags=["Energy"])
app.include_router(calendar_router, prefix="/api/calendar", tags=["Calendar"])
app.include_router(mail_router, prefix="/api/mail", tags=["Mail"])
app.include_router(telephony_router, prefix="/api/telephony", tags=["Telephony"])
app.include_router(camera_router, prefix="/api/cameras", tags=["Cameras"])
app.include_router(backup_router, prefix="/api/backup", tags=["Backup"])

# Static dashboard
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    api_key = websocket.query_params.get("api_key")
    settings = get_settings()
    if api_key not in settings.server.api_keys:
        await websocket.close(code=4003, reason="Invalid API key")
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
