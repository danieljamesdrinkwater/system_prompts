"""Drive detection and mounting via lsblk."""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STORAGE_BASE = "/mnt/storage"


async def list_block_devices() -> list[dict]:
    """List all block devices using lsblk."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "lsblk", "--json", "--output",
            "NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL,UUID,TYPE",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode())
        devices = []
        for dev in data.get("blockdevices", []):
            # Include partitions, skip loop/rom devices
            if dev.get("type") in ("part", "disk"):
                devices.append(dev)
            for child in dev.get("children", []):
                if child.get("type") == "part" and child.get("fstype"):
                    devices.append(child)
        return devices
    except Exception as e:
        logger.error("Failed to list block devices: %s", e)
        return []


async def get_disk_usage(path: str) -> dict:
    """Get disk usage for a mount point."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "df", "-B1", "--output=used,avail,pcent", path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode().strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {
                "used": int(parts[0]),
                "available": int(parts[1]),
                "use_percent": parts[2].strip(),
            }
    except Exception as e:
        logger.error("Failed to get disk usage for %s: %s", path, e)
    return {}


async def mount_drive(device: str, mount_point: str | None = None) -> str:
    """Mount a drive. Returns the mount point."""
    if mount_point is None:
        # Auto-generate mount point from device name
        dev_name = Path(device).name
        mount_point = f"{STORAGE_BASE}/{dev_name}"

    Path(mount_point).mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "mount", device, mount_point,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"Mount failed: {error}")

    logger.info("Mounted %s at %s", device, mount_point)
    return mount_point


async def unmount_drive(mount_point: str) -> None:
    """Unmount a drive."""
    proc = await asyncio.create_subprocess_exec(
        "umount", mount_point,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"Unmount failed: {error}")
    logger.info("Unmounted %s", mount_point)


async def auto_mount_all() -> list[str]:
    """Auto-detect and mount all unmounted partitions."""
    mounted = []
    devices = await list_block_devices()
    for dev in devices:
        fstype = dev.get("fstype")
        mountpoint = dev.get("mountpoint")
        if fstype and fstype in ("ext4", "ext3", "ntfs", "exfat", "vfat", "xfs", "btrfs") and not mountpoint:
            name = dev.get("name", "")
            device_path = f"/dev/{name}"
            label = dev.get("label") or dev.get("uuid") or name
            target = f"{STORAGE_BASE}/{label}"
            try:
                await mount_drive(device_path, target)
                mounted.append(target)
            except RuntimeError as e:
                logger.warning("Auto-mount failed for %s: %s", device_path, e)
    return mounted
