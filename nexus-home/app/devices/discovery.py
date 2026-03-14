"""Network device discovery via mDNS and ARP scanning."""

import asyncio
import logging
import re

from app.devices.schemas import DiscoveredDevice

logger = logging.getLogger(__name__)

MDNS_SERVICE_TYPES = [
    "_mqtt._tcp.local.",
    "_http._tcp.local.",
    "_esphomelib._tcp.local.",
]


async def discover_mdns(timeout: int = 5) -> list[DiscoveredDevice]:
    """Discover devices via mDNS/Zeroconf service browsing."""
    from zeroconf import Zeroconf, ServiceBrowser

    discovered: list[DiscoveredDevice] = []

    class Listener:
        def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
            info = zc.get_service_info(service_type, name)
            if not info:
                return
            addresses = info.parsed_addresses()
            ip = addresses[0] if addresses else "unknown"
            device_type = _service_type_to_device_type(service_type)
            properties = {
                k.decode() if isinstance(k, bytes) else k:
                v.decode() if isinstance(v, bytes) else str(v)
                for k, v in info.properties.items()
            }
            device = DiscoveredDevice(
                name=info.server or name,
                ip=ip,
                mac=None,
                type=device_type,
                service_info={
                    "service_type": service_type,
                    "port": info.port,
                    "properties": properties,
                },
            )
            discovered.append(device)

        def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
            pass

        def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
            pass

    zc = Zeroconf()
    listener = Listener()
    browsers = [
        ServiceBrowser(zc, stype, listener) for stype in MDNS_SERVICE_TYPES
    ]

    await asyncio.sleep(timeout)
    zc.close()

    logger.info("mDNS discovery found %d devices", len(discovered))
    return discovered


async def discover_network(subnet: str | None = None) -> list[DiscoveredDevice]:
    """Discover devices via ARP scan. Tries nmap first, falls back to arp -a."""
    if subnet:
        devices = await _nmap_scan(subnet)
        if devices:
            return devices

    return await _arp_scan()


async def _nmap_scan(subnet: str) -> list[DiscoveredDevice]:
    """Run nmap -sn for host discovery on a subnet."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "nmap", "-sn", subnet,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return _parse_nmap_output(stdout.decode())
    except (FileNotFoundError, asyncio.TimeoutError) as e:
        logger.warning("nmap scan failed: %s", e)
        return []


async def _arp_scan() -> list[DiscoveredDevice]:
    """Parse the system ARP table."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "arp", "-a",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return _parse_arp_output(stdout.decode())
    except (FileNotFoundError, asyncio.TimeoutError) as e:
        logger.warning("ARP scan failed: %s", e)
        return []


def _parse_nmap_output(output: str) -> list[DiscoveredDevice]:
    """Parse nmap -sn output into DiscoveredDevice list."""
    devices: list[DiscoveredDevice] = []
    ip_pattern = re.compile(r"Nmap scan report for (?:(\S+) \()?(\d+\.\d+\.\d+\.\d+)\)?")
    mac_pattern = re.compile(r"MAC Address: ([0-9A-F:]+)(?: \((.+?)\))?", re.IGNORECASE)

    current_ip = None
    current_name = None

    for line in output.splitlines():
        ip_match = ip_pattern.search(line)
        if ip_match:
            current_name = ip_match.group(1) or "unknown"
            current_ip = ip_match.group(2)
            continue

        mac_match = mac_pattern.search(line)
        if mac_match and current_ip:
            devices.append(DiscoveredDevice(
                name=current_name or current_ip,
                ip=current_ip,
                mac=mac_match.group(1),
                type="network",
                service_info={"vendor": mac_match.group(2) or "unknown"},
            ))
            current_ip = None
            current_name = None

    return devices


def _parse_arp_output(output: str) -> list[DiscoveredDevice]:
    """Parse arp -a output into DiscoveredDevice list."""
    devices: list[DiscoveredDevice] = []
    pattern = re.compile(
        r"(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]+)"
    )

    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            devices.append(DiscoveredDevice(
                name=match.group(1),
                ip=match.group(2),
                mac=match.group(3),
                type="network",
                service_info={},
            ))

    return devices


def _service_type_to_device_type(service_type: str) -> str:
    """Map mDNS service type to a friendly device type string."""
    mapping = {
        "_mqtt._tcp.local.": "mqtt",
        "_http._tcp.local.": "http",
        "_esphomelib._tcp.local.": "esphome",
    }
    return mapping.get(service_type, "unknown")
