"""Wake-on-LAN support for network devices."""

import logging

from wakeonlan import send_magic_packet

logger = logging.getLogger(__name__)


async def wake_device(
    mac_address: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> dict:
    """Send a Wake-on-LAN magic packet to the given MAC address."""
    send_magic_packet(mac_address, ip_address=broadcast, port=port)
    logger.info("WoL packet sent to %s (broadcast=%s, port=%d)", mac_address, broadcast, port)
    return {"status": "sent", "mac_address": mac_address}
