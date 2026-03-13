"""Notification senders for new workshop listings (Telegram + WhatsApp via CallMeBot)."""

import logging
import urllib.parse

import requests

from scrapers.base import Listing

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
CALLMEBOT_API = "https://api.callmebot.com/whatsapp.php"


class TelegramNotifier:
    """Send listing notifications via Telegram Bot API."""

    def __init__(self, config: dict):
        tg_config = config.get("telegram", {})
        self.bot_token = tg_config.get("bot_token", "")
        self.chat_id = tg_config.get("chat_id", "")

        if not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.warning("Telegram bot token not configured - Telegram disabled")
            self.enabled = False
        elif not self.chat_id or self.chat_id == "YOUR_CHAT_ID_HERE":
            logger.warning("Telegram chat ID not configured - Telegram disabled")
            self.enabled = False
        else:
            self.enabled = True

    def send_listing(self, listing: Listing) -> bool:
        if not self.enabled:
            return False
        return self._send_message(listing.format_telegram())

    def send_summary(self, new_count: int, total_checked: int):
        if not self.enabled or new_count == 0:
            return
        self._send_message(
            f"Scan complete: {new_count} new listing(s) found "
            f"out of {total_checked} checked."
        )

    def send_test(self) -> bool:
        if not self.enabled:
            print("Telegram not configured. Add bot_token and chat_id to config.yaml")
            return False
        return self._send_message(
            "Workshop Monitor test message - Telegram notifications working!"
        )

    def _send_message(self, text: str) -> bool:
        url = TELEGRAM_API.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram notification sent")
            return True
        except requests.RequestException as e:
            logger.error(f"Telegram send failed: {e}")
            return False


class WhatsAppNotifier:
    """Send listing notifications via WhatsApp using CallMeBot free API."""

    def __init__(self, config: dict):
        wa_config = config.get("whatsapp", {})
        self.phone = wa_config.get("phone", "")
        self.api_key = wa_config.get("callmebot_api_key", "")

        if not self.phone or self.phone == "YOUR_PHONE_HERE":
            logger.warning("WhatsApp phone not configured - WhatsApp disabled")
            self.enabled = False
        elif not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("CallMeBot API key not configured - WhatsApp disabled")
            self.enabled = False
        else:
            self.enabled = True

    def send_listing(self, listing: Listing) -> bool:
        if not self.enabled:
            return False
        return self._send_message(listing.format_telegram())

    def send_summary(self, new_count: int, total_checked: int):
        if not self.enabled or new_count == 0:
            return
        self._send_message(
            f"Scan complete: {new_count} new listing(s) found "
            f"out of {total_checked} checked."
        )

    def send_test(self) -> bool:
        if not self.enabled:
            print("WhatsApp not configured. Add phone and callmebot_api_key to config.yaml")
            return False
        return self._send_message(
            "Workshop Monitor test message - WhatsApp notifications working!"
        )

    def _send_message(self, text: str) -> bool:
        params = {
            "phone": self.phone,
            "text": text,
            "apikey": self.api_key,
        }
        try:
            resp = requests.get(
                CALLMEBOT_API,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("WhatsApp notification sent")
            return True
        except requests.RequestException as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False


class Notifier:
    """Dispatches notifications to all configured channels."""

    def __init__(self, config: dict):
        self.channels = []

        telegram = TelegramNotifier(config)
        if telegram.enabled:
            self.channels.append(telegram)

        whatsapp = WhatsAppNotifier(config)
        if whatsapp.enabled:
            self.channels.append(whatsapp)

        if not self.channels:
            logger.warning("No notification channels configured - running in dry-run mode")

    def send_listing(self, listing: Listing):
        if not self.channels:
            logger.info(f"[DRY RUN] Would notify: {listing.title} - {listing.price}")
            return
        for channel in self.channels:
            channel.send_listing(listing)

    def send_summary(self, new_count: int, total_checked: int):
        for channel in self.channels:
            channel.send_summary(new_count, total_checked)

    def send_test(self) -> bool:
        if not self.channels:
            print("No notification channels configured.")
            print("Set up Telegram and/or WhatsApp in config.yaml")
            return False
        success = False
        for channel in self.channels:
            if channel.send_test():
                success = True
        return success
