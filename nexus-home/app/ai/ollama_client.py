"""Ollama LLM client for chat and text generation."""

import logging

import ollama

from app.config import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async wrapper around the Ollama API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.ai.ollama_url
        self._model = settings.ai.default_model

    def _get_client(self) -> ollama.AsyncClient:
        return ollama.AsyncClient(host=self._url)

    async def chat(
        self, messages: list[dict], system_prompt: str | None = None
    ) -> str:
        """Send a chat conversation to Ollama and return the assistant reply."""
        try:
            full_messages: list[dict] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            client = self._get_client()
            response = await client.chat(
                model=self._model,
                messages=full_messages,
            )
            return response["message"]["content"]
        except Exception as exc:
            logger.error("Ollama chat error: %s", exc)
            return f"Sorry, I could not reach the AI service: {exc}"

    async def generate(self, prompt: str) -> str:
        """Simple single-prompt text generation."""
        try:
            client = self._get_client()
            response = await client.generate(model=self._model, prompt=prompt)
            return response["response"]
        except Exception as exc:
            logger.error("Ollama generate error: %s", exc)
            return f"Sorry, I could not reach the AI service: {exc}"


ollama_client = OllamaClient()
