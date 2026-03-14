"""Camera/CCTV API endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response

from app.auth import verify_api_key
from app.database import get_db
from app.camera.schemas import CameraCreate, CameraUpdate
from app.camera.manager import camera_manager
from app.camera.onvif_discovery import discover_onvif

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/")
async def list_cameras():
    """List all cameras."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM cameras ORDER BY created_at")
        rows = await cursor.fetchall()
        cameras = []
        for row in rows:
            cam = dict(row)
            cam["active"] = cam["id"] in camera_manager.list_active()
            cameras.append(cam)
        return cameras


@router.post("/")
async def add_camera(camera: CameraCreate):
    """Register a new camera."""
    camera_id = str(uuid.uuid4())[:8]
    async with get_db() as db:
        await db.execute(
            """INSERT INTO cameras (id, name, type, url, device_path, username, password, config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (camera_id, camera.name, camera.type, camera.url, camera.device_path,
             camera.username, camera.password, json.dumps(camera.config)),
        )
        await db.commit()
    return {"id": camera_id, "name": camera.name}


@router.put("/{camera_id}")
async def update_camera(camera_id: str, update: CameraUpdate):
    """Update camera configuration."""
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    if "config" in updates:
        updates["config"] = json.dumps(updates["config"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [camera_id]

    async with get_db() as db:
        await db.execute(f"UPDATE cameras SET {set_clause} WHERE id = ?", values)
        await db.commit()
    return {"updated": camera_id}


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str):
    """Remove a camera."""
    await camera_manager.stop_camera(camera_id)
    async with get_db() as db:
        await db.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        await db.commit()
    return {"deleted": camera_id}


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str):
    """Start camera stream and detection."""
    success = await camera_manager.start_camera(camera_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start camera")
    return {"started": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: str):
    """Stop camera stream."""
    await camera_manager.stop_camera(camera_id)
    return {"stopped": camera_id}


@router.get("/{camera_id}/snapshot")
async def get_snapshot(camera_id: str):
    """Get current frame as JPEG."""
    stream = camera_manager.get_stream(camera_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Camera not active")
    jpeg = await stream.get_snapshot()
    if not jpeg:
        raise HTTPException(status_code=500, detail="Failed to capture frame")
    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/{camera_id}/stream")
async def stream_camera(camera_id: str):
    """MJPEG live stream."""
    stream = camera_manager.get_stream(camera_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Camera not active")
    return StreamingResponse(
        stream.mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/events")
async def get_events(
    camera_id: str,
    limit: int = Query(50, ge=1, le=500),
    label: str | None = None,
):
    """Get detection events for a camera."""
    async with get_db() as db:
        query = "SELECT * FROM camera_events WHERE camera_id = ?"
        params: list = [camera_id]
        if label:
            query += " AND label = ?"
            params.append(label)
        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]


@router.get("/{camera_id}/recordings")
async def list_recordings(
    camera_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """List recordings for a camera."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM recordings WHERE camera_id = ? ORDER BY start_time DESC LIMIT ?",
            (camera_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]


@router.post("/discover")
async def discover_cameras():
    """Auto-discover ONVIF cameras on the network."""
    cameras = await discover_onvif()
    return cameras
