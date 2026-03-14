"""Configuration backup and restore."""

import os
import tarfile
import logging
from datetime import datetime
from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])

DATA_DIR = os.environ.get("NEXUS_DATA_DIR", "./data")
BACKUP_DIR = Path(DATA_DIR) / "backups"
CONFIG_PATH = os.environ.get("NEXUS_CONFIG_PATH", "config.yaml")


@router.post("/create")
async def create_backup():
    """Create a backup of config and database."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"nexus_backup_{timestamp}.tar.gz"

    files_to_backup = []
    db_path = Path(DATA_DIR) / "nexus.db"
    if db_path.exists():
        files_to_backup.append(("nexus.db", str(db_path)))
    if Path(CONFIG_PATH).exists():
        files_to_backup.append(("config.yaml", CONFIG_PATH))

    with tarfile.open(str(backup_path), "w:gz") as tar:
        for arcname, filepath in files_to_backup:
            tar.add(filepath, arcname=arcname)

    size = backup_path.stat().st_size
    logger.info("Backup created: %s (%d bytes)", backup_path, size)
    return {"path": str(backup_path), "size": size, "timestamp": timestamp}


@router.get("/list")
async def list_backups():
    """List available backups."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for f in sorted(BACKUP_DIR.glob("nexus_backup_*.tar.gz"), reverse=True):
        backups.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return backups


@router.get("/download/{filename}")
async def download_backup(filename: str):
    """Download a backup file."""
    path = BACKUP_DIR / filename
    if not path.exists() or not str(path.resolve()).startswith(str(BACKUP_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, filename=filename, media_type="application/gzip")


@router.post("/restore/{filename}")
async def restore_backup(filename: str):
    """Restore from a backup file."""
    path = BACKUP_DIR / filename
    if not path.exists() or not str(path.resolve()).startswith(str(BACKUP_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Backup not found")

    with tarfile.open(str(path), "r:gz") as tar:
        # Only extract known safe files
        for member in tar.getmembers():
            if member.name in ("nexus.db", "config.yaml"):
                if member.name == "nexus.db":
                    tar.extract(member, path=DATA_DIR)
                elif member.name == "config.yaml":
                    tar.extract(member, path=str(Path(CONFIG_PATH).parent))

    logger.info("Backup restored from %s", filename)
    return {"restored": filename, "note": "Restart the server for changes to take effect"}
