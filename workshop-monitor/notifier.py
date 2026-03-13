"""Telegram notification sender for new workshop listings."""

import logging

import requests

from scrapers.base import Listing

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """Send listing notifications via Telegram Bot API."""

    def __init__(self, config: dict):
        tg_config = config.get("telegram", {})
        self.bot_token = tg_config.get("bot_token", "")
        self.chat_id = tg_config.get("chat_id", "")

        if not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.warning("Telegram bot token not configured - notifications disabled")
            self.enabled = False
        elif not self.chat_id or self.chat_id == "YOUR_CHAT_ID_HERE":
            logger.warning("Telegram chat ID not configured - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True

    def send_listing(self, listing: Listing) -> bool:
        """Send a single listing notification. Returns True on success."""
        if not self.enabled:
            logger.info(f"[DRY RUN] Would notify: {listing.title} - {listing.price}")
            return False

        message = listing.format_telegram()
        return self._send_message(message)

    def send_summary(self, new_count: int, total_checked: int):
        """Send a summary of the scan run."""
        if not self.enabled:
            return
        if new_count == 0:
            return  # Don't spam with "no new listings" messages

        message = (
            f"Scan complete: {new_count} new listing(s) found "
            f"out of {total_checked} checked."
        )
        self._send_message(message)

    def send_test(self) -> bool:
        """Send a test message to verify configuration."""
        if not self.enabled:
            print("Telegram not configured. Add bot_token and chat_id to config.yaml")
            return False
        return self._send_message(
            "Workshop Monitor test message - notifications are working!"
        )

    def _send_message(self, text: str) -> bool:
        """Send a message via the Telegram Bot API."""
        url = TELEGRAM_API.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
