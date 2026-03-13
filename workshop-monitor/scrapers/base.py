"""Base scraper interface and shared Listing dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re


@dataclass
class Listing:
    """Standardised listing from any source."""
    title: str
    price: str
    location: str
    url: str
    description: str
    source: str
    found_at: datetime = field(default_factory=datetime.now)
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.url.encode()).hexdigest()

    def extract_price_number(self) -> float | None:
        """Try to extract a numeric monthly price from the price string."""
        price_str = self.price.lower().replace(",", "")
        # Match patterns like £300, 300 pcm, £300/month, etc.
        match = re.search(r"£?\s*(\d+(?:\.\d{2})?)", price_str)
        if match:
            value = float(match.group(1))
            # If price looks weekly (common on Gumtree), multiply by ~4.33
            if "pw" in price_str or "per week" in price_str or "/week" in price_str:
                value *= 4.33
            return value
        return None

    def matches_keywords(self, keywords: list[str]) -> bool:
        """Check if listing title or description contains any keyword."""
        text = f"{self.title} {self.description}".lower()
        return any(kw.lower() in text for kw in keywords)

    def format_telegram(self) -> str:
        """Format listing for Telegram message."""
        desc_preview = self.description[:200].strip()
        if len(self.description) > 200:
            desc_preview += "..."
        return (
            f"New Workshop Found!\n"
            f"Location: {self.location}\n"
            f"Price: {self.price}\n"
            f"Source: {self.source}\n"
            f"\n"
            f'"{desc_preview}"\n'
            f"\n"
            f"View: {self.url}"
        )


class BaseScraper(ABC):
    """Abstract base class for all listing scrapers."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    def __init__(self, config: dict):
        self.config = config
        self.search_config = config.get("search", {})
        self.max_price = self.search_config.get("max_price", 350)
        self.min_price = self.search_config.get("min_price", 0)
        self.keywords = self.search_config.get("keywords", [])

    @abstractmethod
    def fetch_listings(self) -> list[Listing]:
        """Fetch and return all matching listings from this source."""
        pass

    def filter_by_price(self, listing: Listing) -> bool:
        """Return True if listing is within the configured price range."""
        price = listing.extract_price_number()
        if price is None:
            return True  # Include if we can't parse price (manual check)
        return self.min_price <= price <= self.max_price

    def filter_listings(self, listings: list[Listing]) -> list[Listing]:
        """Apply price and keyword filters to listings."""
        filtered = []
        for listing in listings:
            if self.filter_by_price(listing):
                if listing.matches_keywords(self.keywords) or not self.keywords:
                    filtered.append(listing)
        return filtered
