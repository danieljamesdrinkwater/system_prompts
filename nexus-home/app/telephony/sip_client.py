"""SIP/VoIP client wrapper."""

import logging
from datetime import datetime

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


class SIPClient:
    """VoIP SIP client using PJSIP/pjsua2.

    Note: pjsua2 requires the python3-pjsip system package.
    This wrapper provides a clean async interface and gracefully
    degrades if pjsip is not installed.
    """

    def __init__(self) -> None:
        self._registered = False
        self._lib = None
        self._account = None

    async def start(self) -> bool:
        """Initialize SIP stack and register with provider."""
        settings = get_settings()
        cfg = settings.telephony.sip
        if not cfg.server:
            logger.info("SIP not configured, telephony disabled")
            return False

        try:
            import pjsua2 as pj

            ep = pj.Endpoint()
            ep.libCreate()
            ep_cfg = pj.EpConfig()
            ep.libInit(ep_cfg)

            # Transport
            transport_cfg = pj.TransportConfig()
            transport_cfg.port = 0  # Auto-select port
            ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)
            ep.libStart()

            # Account
            acc_cfg = pj.AccountConfig()
            acc_cfg.idUri = f"sip:{cfg.username}@{cfg.server}"
            acc_cfg.regConfig.registrarUri = f"sip:{cfg.server}:{cfg.port}"
            cred = pj.AuthCredInfo("digest", cfg.realm or "*", cfg.username, 0, cfg.password)
            acc_cfg.sipConfig.authCreds.append(cred)

            self._account = pj.Account()
            self._account.create(acc_cfg)
            self._lib = ep
            self._registered = True
            logger.info("SIP registered with %s", cfg.server)
            return True
        except ImportError:
            logger.warning("pjsua2 not available — install python3-pjsip for telephony")
            return False
        except Exception as e:
            logger.error("SIP registration failed: %s", e)
            return False

    async def dial(self, number: str) -> dict:
        """Initiate an outbound call."""
        if not self._registered:
            return {"error": "SIP not registered"}

        try:
            import pjsua2 as pj
            settings = get_settings()
            call = pj.Call(self._account)
            call_prm = pj.CallOpParam(True)
            uri = f"sip:{number}@{settings.telephony.sip.server}"
            call.makeCall(uri, call_prm)

            # Log call
            async with get_db() as db:
                await db.execute(
                    "INSERT INTO call_history (direction, remote_number, status) VALUES ('outbound', ?, 'dialing')",
                    (number,),
                )
                await db.commit()

            logger.info("Dialing %s", number)
            return {"status": "dialing", "number": number}
        except Exception as e:
            logger.error("Dial failed: %s", e)
            return {"error": str(e)}

    async def hangup(self) -> dict:
        """Hang up the current call."""
        # Placeholder — actual implementation depends on tracking active call objects
        return {"status": "hung_up"}

    async def stop(self) -> None:
        """Shutdown SIP stack."""
        if self._lib:
            try:
                self._lib.libDestroy()
            except Exception:
                pass
            self._lib = None
            self._registered = False

    @property
    def is_registered(self) -> bool:
        return self._registered


sip_client = SIPClient()
