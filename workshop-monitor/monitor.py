#!/usr/bin/env python3
"""
Workshop Listing Monitor
Automatically checks UK property sites for affordable workshop/unit listings
and sends Telegram notifications for new finds.

Usage:
    python monitor.py              # Run a single check
    python monitor.py --loop       # Run continuously on schedule
    python monitor.py --test       # Dry run - print results, no notifications
    python monitor.py --test-notify    # Send a test message to all configured channels
    python monitor.py --recent     # Show listings found in the last 7 days
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from scrapers import GumtreeScraper, RightmoveScraper, ZooplaScraper
from storage import ListingStorage
from notifier import Notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("monitor")


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def get_scrapers(config: dict) -> list:
    """Instantiate all enabled scrapers."""
    scraper_classes = [GumtreeScraper, RightmoveScraper, ZooplaScraper]
    scrapers = []
    for cls in scraper_classes:
        try:
            scraper = cls(config)
            scrapers.append(scraper)
        except Exception as e:
            logger.error(f"Failed to init {cls.__name__}: {e}")
    return scrapers


def run_check(config: dict, storage: ListingStorage, notifier: Notifier, dry_run: bool = False):
    """Run a single check across all scrapers."""
    scrapers = get_scrapers(config)
    total_found = 0
    new_count = 0

    for scraper in scrapers:
        try:
            listings = scraper.fetch_listings()
            total_found += len(listings)

            for listing in listings:
                if storage.is_new(listing.id):
                    new_count += 1
                    if dry_run:
                        print(f"\n{'='*60}")
                        print(f"[NEW] {listing.source}")
                        print(f"Title: {listing.title}")
                        print(f"Price: {listing.price}")
                        print(f"Location: {listing.location}")
                        print(f"URL: {listing.url}")
                        print(f"Description: {listing.description[:150]}...")
                    else:
                        notifier.send_listing(listing)
                    storage.mark_seen(listing)
        except Exception as e:
            logger.error(f"Error running {scraper.__class__.__name__}: {e}")

    logger.info(f"Check complete: {total_found} total listings, {new_count} new")

    if not dry_run:
        notifier.send_summary(new_count, total_found)

    # Periodically clean up old entries
    storage.purge_old(days=90)

    return new_count


def show_recent(storage: ListingStorage, days: int = 7):
    """Display recently found listings."""
    listings = storage.get_recent(days=days)
    if not listings:
        print(f"No listings found in the last {days} days.")
        return

    print(f"\nListings found in the last {days} days ({len(listings)} total):\n")
    for item in listings:
        print(f"  [{item['source']}] {item['title']}")
        print(f"    Price: {item['price']} | Location: {item['location']}")
        print(f"    URL: {item['url']}")
        print(f"    Found: {item['found_at']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Listing Monitor")
    parser.add_argument("--loop", action="store_true", help="Run continuously on schedule")
    parser.add_argument("--test", action="store_true", help="Dry run - print results only")
    parser.add_argument("--test-notify", action="store_true", help="Send test message to all configured channels")
    parser.add_argument("--recent", action="store_true", help="Show recently found listings")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    storage = ListingStorage()
    notifier = Notifier(config)

    if args.test_notify:
        success = notifier.send_test()
        print("Test message sent!" if success else "Failed to send test message.")
        return

    if args.recent:
        show_recent(storage)
        return

    if args.loop:
        schedule = config.get("schedule", {})
        interval = schedule.get("interval_minutes", 180)
        quiet_start = schedule.get("quiet_start", 23)
        quiet_end = schedule.get("quiet_end", 7)
        logger.info(f"Starting continuous monitor (every {interval} minutes, quiet {quiet_start}:00-{quiet_end}:00)")
        logger.info(f"Searching within {config['search']['radius_miles']} miles of {config['search']['postcode']}")
        logger.info(f"Price range: £{config['search']['min_price']}-£{config['search']['max_price']}/month")

        while True:
            hour = datetime.now().hour
            if quiet_start > quiet_end:
                is_quiet = hour >= quiet_start or hour < quiet_end
            else:
                is_quiet = quiet_start <= hour < quiet_end

            if is_quiet:
                logger.info(f"Quiet hours ({quiet_start}:00-{quiet_end}:00) - skipping check")
            else:
                try:
                    run_check(config, storage, notifier)
                except Exception as e:
                    logger.error(f"Check failed: {e}")
            logger.info(f"Next check in {interval} minutes...")
            time.sleep(interval * 60)
    else:
        # Single run
        new = run_check(config, storage, notifier, dry_run=args.test)
        if args.test:
            print(f"\n{'='*60}")
            print(f"Dry run complete. {new} new listing(s) found.")
            total = storage.count_all()
            print(f"Total listings tracked: {total}")


if __name__ == "__main__":
    main()
