"""Natural-language intent parser backed by Ollama."""

import json
import logging

from app.ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a smart home assistant. Analyse the user's request and respond with a \
single JSON object (no extra text).

Available devices:
{devices_json}

Output format:
{{
  "type": "device_command" or "conversation",
  "device_id": "<device id or null>",
  "command": {{"<key>": "<value>"}} or null,
  "response": "<short natural-language reply to the user>"
}}

Rules:
- If the request maps to controlling a device, set type to "device_command" and \
fill in device_id and command.
- If the request is general conversation, set type to "conversation" with a \
helpful response.
- command should be a dict suitable for the device (e.g. {{"power": "on"}}, \
{{"brightness": 80}}).
"""


class IntentParser:
    """Extracts structured intents from natural-language text."""

    async def parse(self, text: str, devices: list[dict]) -> dict | None:
        """Parse user text into a structured intent dict.

        Returns a dict with keys: type, device_id, command, response.
        Falls back to a conversation-type response on failure.
        """
        devices_json = json.dumps(devices, indent=2, default=str)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(devices_json=devices_json)

        messages = [{"role": "user", "content": text}]
        raw = await ollama_client.chat(messages, system_prompt=system_prompt)

        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Attempt to extract a JSON intent from the model output."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            parsed = json.loads(cleaned)
            # Validate required keys
            if "type" not in parsed or "response" not in parsed:
                raise ValueError("Missing required keys in intent JSON")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Intent parse failed (%s), falling back to conversation", exc)
            return {
                "type": "conversation",
                "device_id": None,
                "command": None,
                "response": raw,
            }


intent_parser = IntentParser()
