"""Storage API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

from app.auth import verify_api_key
from app.storage import service, mounts
from app.storage.schemas import MountRequest, UnmountRequest

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/files")
async def list_files(path: str = Query("", description="Relative path")):
    """List files in a directory."""
    try:
        return await service.list_files(path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/files/download")
async def download_file(path: str = Query(...)):
    """Download a file."""
    try:
        file_path = await service.read_file(path)
        return FileResponse(file_path, filename=file_path.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/files/upload")
async def upload_file(
    path: str = Query(..., description="Target directory"),
    file: UploadFile = File(...),
):
    """Upload a file."""
    try:
        content = await file.read()
        target = f"{path}/{file.filename}"
        saved = await service.write_file(target, content)
        return {"path": saved}
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.delete("/files")
async def delete_file(path: str = Query(...)):
    """Delete a file or empty directory."""
    try:
        await service.delete_file(path)
        return {"deleted": path}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/disks")
async def list_disks():
    """List all block devices and their mount status."""
    devices = await mounts.list_block_devices()
    # Enrich with usage info for mounted drives
    for dev in devices:
        mp = dev.get("mountpoint")
        if mp:
            usage = await mounts.get_disk_usage(mp)
            dev.update(usage)
    return devices


@router.post("/mount")
async def mount_drive(req: MountRequest):
    """Mount a drive."""
    try:
        mp = await mounts.mount_drive(req.device, req.mount_point)
        return {"mountpoint": mp}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unmount")
async def unmount_drive(req: UnmountRequest):
    """Unmount a drive."""
    try:
        await mounts.unmount_drive(req.mount_point)
        return {"unmounted": req.mount_point}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-mount")
async def auto_mount():
    """Auto-detect and mount all unmounted drives."""
    mounted = await mounts.auto_mount_all()
    return {"mounted": mounted}
