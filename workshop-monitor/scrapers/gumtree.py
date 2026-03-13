"""Gumtree scraper - uses HTML parsing to find workshop/unit listings."""

import logging
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)


class GumtreeScraper(BaseScraper):
    """Scrape Gumtree commercial property listings."""

    SOURCE = "Gumtree"

    def fetch_listings(self) -> list[Listing]:
        scraper_config = self.config.get("scrapers", {}).get("gumtree", {})
        if not scraper_config.get("enabled", True):
            return []

        search_urls = scraper_config.get("search_urls", [])
        all_listings = []

        for url in search_urls:
            try:
                listings = self._scrape_search_page(url)
                all_listings.extend(listings)
                time.sleep(3)  # Polite delay between requests
            except Exception as e:
                logger.error(f"Gumtree scrape failed for {url}: {e}")

        return self.filter_listings(all_listings)

    def _scrape_search_page(self, url: str) -> list[Listing]:
        """Scrape a Gumtree search results page."""
        logger.info(f"Scraping Gumtree: {url}")
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = []

        # Gumtree uses article elements or listing-link classes for results
        # Try multiple selectors as Gumtree changes their HTML periodically
        result_cards = (
            soup.select("article.listing-maxi")
            or soup.select("div.listing-maxi")
            or soup.select('[data-q="search-result"]')
            or soup.select("a.listing-link")
        )

        for card in result_cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse Gumtree card: {e}")

        logger.info(f"Found {len(listings)} Gumtree listings")
        return listings

    def _parse_card(self, card) -> Listing | None:
        """Parse a single Gumtree result card into a Listing."""
        # Title
        title_el = (
            card.select_one("h2")
            or card.select_one(".listing-title")
            or card.select_one('[data-q="tile-title"]')
        )
        title = title_el.get_text(strip=True) if title_el else ""

        # URL
        link_el = card.select_one("a[href]") if card.name != "a" else card
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = f"https://www.gumtree.com{href}"
        if not href:
            return None

        # Price
        price_el = (
            card.select_one(".listing-price")
            or card.select_one('[data-q="tile-price"]')
            or card.select_one(".ad-price")
        )
        price = price_el.get_text(strip=True) if price_el else "Price not listed"

        # Location
        loc_el = (
            card.select_one(".listing-location")
            or card.select_one('[data-q="tile-location"]')
            or card.select_one(".ad-location")
        )
        location = loc_el.get_text(strip=True) if loc_el else "Location not specified"

        # Description snippet
        desc_el = (
            card.select_one(".listing-description")
            or card.select_one('[data-q="tile-description"]')
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
