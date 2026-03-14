"""FastAPI router for device management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import verify_api_key
from app.database import get_db
from app.devices import service
from app.devices.schemas import DeviceCreate, DeviceUpdate, DeviceCommand
from app.devices.discovery import discover_mdns, discover_network
from app.devices.wol import wake_device

router = APIRouter()


@router.get("/discover/")
async def discover_devices(
    subnet: str | None = Query(None, description="Subnet for nmap scan, e.g. 192.168.1.0/24"),
    _api_key: str = Depends(verify_api_key),
):
    """Run mDNS and network discovery to find new devices."""
    mdns_devices = await discover_mdns(timeout=5)
    network_devices = await discover_network(subnet=subnet)

    # Deduplicate by IP
    seen_ips: set[str] = set()
    combined = []
    for dev in mdns_devices + network_devices:
        if dev.ip not in seen_ips:
            seen_ips.add(dev.ip)
            combined.append(dev)

    return {"discovered": [d.model_dump() for d in combined]}


@router.get("/")
async def list_devices(
    room: str | None = Query(None),
    type: str | None = Query(None),
    _api_key: str = Depends(verify_api_key),
):
    """List all devices with optional room/type filters."""
    async with get_db() as db:
        devices = await service.list_devices(db, room=room, type=type)
    return {"devices": devices}


@router.get("/{device_id}")
async def get_device(device_id: str, _api_key: str = Depends(verify_api_key)):
    """Get a device by ID including its current state."""
    async with get_db() as db:
        device = await service.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/", status_code=201)
async def create_device(
    device: DeviceCreate,
    api_key: str = Depends(verify_api_key),
):
    """Register a new device."""
    async with get_db() as db:
        created = await service.create_device(db, device)
        await service.log_audit(
            db, "create", "device", created["id"],
            details=f"Created device '{device.name}'",
            user_key=api_key,
        )
    return created


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    updates: DeviceUpdate,
    api_key: str = Depends(verify_api_key),
):
    """Update an existing device."""
    async with get_db() as db:
        updated = await service.update_device(db, device_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail="Device not found")
        await service.log_audit(
            db, "update", "device", device_id,
            details=f"Updated fields: {list(updates.model_dump(exclude_unset=True).keys())}",
            user_key=api_key,
        )
    return updated


@router.delete("/{device_id}")
async def delete_device(device_id: str, api_key: str = Depends(verify_api_key)):
    """Delete a device."""
    async with get_db() as db:
        deleted = await service.delete_device(db, device_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Device not found")
        await service.log_audit(
            db, "delete", "device", device_id, user_key=api_key,
        )
    return {"status": "deleted", "id": device_id}


@router.post("/{device_id}/command")
async def send_command(
    device_id: str,
    body: DeviceCommand,
    api_key: str = Depends(verify_api_key),
):
    """Send a command to a device via MQTT."""
    try:
        result = await service.send_command(device_id, body.command)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    async with get_db() as db:
        await service.log_audit(
            db, "command", "device", device_id,
            details=str(body.command),
            user_key=api_key,
        )
    return result


@router.get("/{device_id}/history")
async def get_device_history(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    _api_key: str = Depends(verify_api_key),
):
    """Get state history for a device."""
    async with get_db() as db:
        device = await service.get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        history = await service.get_device_history(db, device_id, hours=hours)
    return {"device_id": device_id, "history": history}


@router.post("/{device_id}/wake")
async def wake_device_endpoint(
    device_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Send a Wake-on-LAN packet to a device."""
    async with get_db() as db:
        device = await service.get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        mac = device.get("mac_address")
        if not mac:
            raise HTTPException(
                status_code=400, detail="Device has no MAC address configured"
            )

        result = await wake_device(mac)
        await service.log_audit(
            db, "wake", "device", device_id,
            details=f"WoL sent to {mac}",
            user_key=api_key,
        )
    return result
