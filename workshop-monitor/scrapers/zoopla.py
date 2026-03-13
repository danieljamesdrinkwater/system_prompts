"""Zoopla Commercial scraper for workshop/industrial unit listings."""

import logging
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)


class ZooplaScraper(BaseScraper):
    """Scrape Zoopla commercial property listings."""

    SOURCE = "Zoopla"

    def fetch_listings(self) -> list[Listing]:
        scraper_config = self.config.get("scrapers", {}).get("zoopla", {})
        if not scraper_config.get("enabled", True):
            return []

        search_urls = scraper_config.get("search_urls", [])
        all_listings = []

        for url in search_urls:
            try:
                listings = self._scrape_search_page(url)
                all_listings.extend(listings)
                time.sleep(5)
            except Exception as e:
                logger.error(f"Zoopla scrape failed for {url}: {e}")

        return self.filter_listings(all_listings)

    def _scrape_search_page(self, url: str) -> list[Listing]:
        """Scrape a Zoopla commercial search results page."""
        logger.info(f"Scraping Zoopla: {url}")
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = []

        # Zoopla uses various card structures
        result_cards = (
            soup.select('[data-testid="search-result"]')
            or soup.select(".listing-results-wrapper .srp-list--item")
            or soup.select("article")
            or soup.select('[class*="listing"]')
        )

        for card in result_cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse Zoopla card: {e}")

        logger.info(f"Found {len(listings)} Zoopla listings")
        return listings

    def _parse_card(self, card) -> Listing | None:
        """Parse a single Zoopla result card into a Listing."""
        # Title / address
        title_el = (
            card.select_one('[data-testid="listing-title"]')
            or card.select_one("h2")
            or card.select_one(".listing-results-attr")
        )
        title = title_el.get_text(strip=True) if title_el else ""

        # URL
        link_el = card.select_one("a[href*='/to-rent/']") or card.select_one("a[href]")
        href = ""
        if link_el:
            href = link_el.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.zoopla.co.uk{href}"
        if not href:
            return None

        # Price
        price_el = (
            card.select_one('[data-testid="listing-price"]')
            or card.select_one(".listing-results-price")
            or card.select_one('[class*="price"]')
        )
        price = price_el.get_text(strip=True) if price_el else "Price not listed"

        # Location
        loc_el = (
            card.select_one('[data-testid="listing-address"]')
            or card.select_one("address")
            or card.select_one(".listing-results-address")
        )
        location = loc_el.get_text(strip=True) if loc_el else title

        # Description
        desc_el = (
            card.select_one('[data-testid="listing-description"]')
            or card.select_one("p")
        )
        description = desc_el.get_text(strip=True) if desc_el else ""

        return Listing(
            title=title,
            price=price,
            location=location,
            url=href,
            description=description,
            source=self.SOURCE,
        )
