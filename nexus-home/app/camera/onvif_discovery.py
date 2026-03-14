"""ONVIF camera auto-discovery."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def discover_onvif(timeout: int = 5) -> list[dict]:
    """Discover ONVIF cameras on the network."""
    try:
        from onvif import ONVIFCamera
        from wsdiscovery.discovery import ThreadedWSDiscovery

        wsd = ThreadedWSDiscovery()
        wsd.start()
        await asyncio.sleep(timeout)

        services = wsd.searchServices()
        cameras = []

        for service in services:
            scopes = service.getScopes()
            scope_str = " ".join(str(s.getValue()) for s in scopes)

            # Filter for ONVIF devices
            if "onvif" in scope_str.lower() or "NetworkVideoTransmitter" in scope_str:
                xaddrs = service.getXAddrs()
                name = ""
                for s in scopes:
                    val = str(s.getValue())
                    if "name/" in val.lower():
                        name = val.split("/")[-1]
                        break

                cameras.append({
                    "name": name or "ONVIF Camera",
                    "xaddr": xaddrs[0] if xaddrs else "",
                    "scopes": scope_str,
                    "type": "onvif",
                })

        wsd.stop()
        logger.info("Discovered %d ONVIF cameras", len(cameras))
        return cameras
    except ImportError:
        logger.warning("onvif-zeep or wsdiscovery not installed")
        return []
    except Exception as e:
        logger.error("ONVIF discovery failed: %s", e)
        return []


async def get_stream_uri(host: str, port: int, username: str, password: str) -> str | None:
    """Get RTSP stream URI from an ONVIF camera."""
    try:
        from onvif import ONVIFCamera

        cam = ONVIFCamera(host, port, username, password)
        media_service = cam.create_media_service()
        profiles = media_service.GetProfiles()

        if not profiles:
            return None

        stream_setup = {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"},
        }
        uri = media_service.GetStreamUri({
            "StreamSetup": stream_setup,
            "ProfileToken": profiles[0].token,
        })
        return uri.Uri
    except Exception as e:
        logger.error("Failed to get stream URI: %s", e)
        return None
