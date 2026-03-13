"""SQLite-based storage for tracking seen listings and avoiding duplicates."""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

from scrapers.base import Listing

logger = logging.getLogger(__name__)


class ListingStorage:
    """Stores seen listings in SQLite to prevent duplicate notifications."""

    def __init__(self, db_path: str = "seen_listings.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Create the database and table if they don't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_listings (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    price TEXT,
                    location TEXT,
                    url TEXT,
                    description TEXT,
                    source TEXT,
                    found_at TEXT
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def is_new(self, listing_id: str) -> bool:
        """Check if a listing has NOT been seen before."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_listings WHERE id = ?", (listing_id,)
            ).fetchone()
            return row is None

    def mark_seen(self, listing: Listing):
        """Record a listing as seen."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO seen_listings
                   (id, title, price, location, url, description, source, found_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    listing.id,
                    listing.title,
                    listing.price,
                    listing.location,
                    listing.url,
                    listing.description,
                    listing.source,
                    listing.found_at.isoformat(),
                ),
            )
        logger.debug(f"Marked as seen: {listing.id} ({listing.title})")

    def get_recent(self, days: int = 7) -> list[dict]:
        """Get listings found in the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM seen_listings WHERE found_at > ? ORDER BY found_at DESC",
                (cutoff,),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_all(self) -> int:
        """Return total number of stored listings."""
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM seen_listings").fetchone()[0]

    def purge_old(self, days: int = 90):
        """Remove listings older than N days to keep the database small."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            deleted = conn.execute(
                "DELETE FROM seen_listings WHERE found_at < ?", (cutoff,)
            ).rowcount
            if deleted:
                logger.info(f"Purged {deleted} listings older than {days} days")
