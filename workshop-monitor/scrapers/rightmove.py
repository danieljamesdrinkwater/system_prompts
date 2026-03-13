"""Rightmove Commercial scraper for workshop/industrial unit listings."""

import logging
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)


class RightmoveScraper(BaseScraper):
    """Scrape Rightmove commercial property-to-let listings."""

    SOURCE = "Rightmove"

    def fetch_listings(self) -> list[Listing]:
        scraper_config = self.config.get("scrapers", {}).get("rightmove", {})
        if not scraper_config.get("enabled", True):
            return []

        search_urls = scraper_config.get("search_urls", [])
        all_listings = []

        for url in search_urls:
            try:
                listings = self._scrape_search_page(url)
                all_listings.extend(listings)
                time.sleep(5)  # Rightmove is stricter - longer delay
            except Exception as e:
                logger.error(f"Rightmove scrape failed for {url}: {e}")

        return self.filter_listings(all_listings)

    def _scrape_search_page(self, url: str) -> list[Listing]:
        """Scrape a Rightmove commercial search results page."""
        logger.info(f"Scraping Rightmove: {url}")
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = []

        # Rightmove commercial uses propertyCard elements
        result_cards = (
            soup.select(".propertyCard")
            or soup.select('[data-test="propertyCard"]')
            or soup.select(".l-searchResult")
        )

        for card in result_cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse Rightmove card: {e}")

        logger.info(f"Found {len(listings)} Rightmove listings")
        return listings

    def _parse_card(self, card) -> Listing | None:
        """Parse a single Rightmove property card into a Listing."""
        # Title / address
        title_el = (
            card.select_one(".propertyCard-address")
            or card.select_one('[data-test="address"]')
            or card.select_one("h2")
        )
        title = title_el.get_text(strip=True) if title_el else ""

        # Property type / description from title area
        type_el = card.select_one(".propertyCard-title")
        type_text = type_el.get_text(strip=True) if type_el else ""

        # URL
        link_el = card.select_one("a.propertyCard-link") or card.select_one("a[href*='/properties/']")
        href = ""
        if link_el:
            href = link_el.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.rightmove.co.uk{href}"
        if not href:
            return None

        # Price
        price_el = (
            card.select_one(".propertyCard-priceValue")
            or card.select_one('[data-test="price"]')
            or card.select_one(".price")
        )
        price = price_el.get_text(strip=True) if price_el else "Price not listed"

        # Description
        desc_el = card.select_one(".propertyCard-description") or card.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Location (often same as title for Rightmove)
        location = title

        # Combine type and title for a more descriptive title
        full_title = f"{type_text} - {title}" if type_text else title

        return Listing(
            title=full_title,
            price=price,
            location=location,
            url=href,
            description=description,
            source=self.SOURCE,
        )
