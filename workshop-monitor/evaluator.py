"""AI-powered listing evaluator using OpenRouter free models."""

import logging
import time

import requests

from scrapers.base import Listing

logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You evaluate commercial property listings for suitability as an audio equipment workshop.

The user needs a space for:
- Repairing audio equipment (PA systems, speakers, amplifiers)
- Running an audio hire business (storing and dispatching gear)
- Storage of audio equipment

Good matches: workshops, industrial units, light industrial, commercial units, lock-ups with power, double garages (non-residential), maker spaces, warehouse units.

Bad matches: residential properties, office-only spaces with no practical/workshop use, virtual offices, serviced desks, mail forwarding, parking only, containers without power, purely retail shops.

Reply with ONLY one word: YES or NO."""

USER_TEMPLATE = """Is this listing suitable as an audio workshop?

Title: {title}
Price: {price}
Location: {location}
Description: {description}"""


class AIEvaluator:
    """Evaluates listings using an AI model via OpenRouter."""

    def __init__(self, config: dict):
        ai_config = config.get("ai", {})
        self.api_key = ai_config.get("openrouter_api_key", "")
        self.model = ai_config.get("model", "meta-llama/llama-3.3-70b-instruct:free")

        if not self.api_key or not ai_config.get("enabled", False):
            logger.info("AI evaluator disabled")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"AI evaluator enabled (model: {self.model})")

    def is_relevant(self, listing: Listing) -> bool:
        """Return True if AI thinks this listing is suitable for an audio workshop."""
        if not self.enabled:
            return True  # Pass everything through if AI is off

        prompt = USER_TEMPLATE.format(
            title=listing.title,
            price=listing.price,
            location=listing.location,
            description=listing.description[:500],
        )

        try:
            resp = requests.post(
                OPENROUTER_API,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 5,
                    "temperature": 0,
                },
                timeout=15,
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
            is_yes = answer.startswith("YES")
            logger.debug(f"AI eval: '{listing.title}' -> {answer}")
            return is_yes
        except Exception as e:
            logger.warning(f"AI eval failed for '{listing.title}': {e}")
            return True  # Include listing if AI fails (fail open)

    def filter_listings(self, listings: list[Listing]) -> list[Listing]:
        """Filter a list of listings through AI evaluation."""
        if not self.enabled:
            return listings

        passed = []
        for i, listing in enumerate(listings):
            if i > 0:
                time.sleep(4)  # Rate limit: free tier allows ~20 req/min
            if self.is_relevant(listing):
                passed.append(listing)
            else:
                logger.info(f"AI rejected: {listing.title} ({listing.price})")
        logger.info(f"AI filter: {len(passed)}/{len(listings)} listings passed")
        return passed
