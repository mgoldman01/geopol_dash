"""
Database connection and query management.

Provides a Database class that handles connection lifecycle,
query execution, and data conversion between SQLite and Pydantic models.
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.db.schema import init_schema
from src.models.event import Event, EventFilter
from src.models.relationship import Relationship
from src.models.trend import Trend, TrendType

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database interface for geopolitical event data.

    Handles connection management, schema initialization, and provides
    methods for CRUD operations on events, relationships, and trends.

    Attributes:
        db_path: Path to SQLite database file
        connection: Active database connection (None until connect() called)

    Example:
        >>> db = Database("data/geopol.db")
        >>> db.connect()
        >>> events = db.query_events(EventFilter(start_date=date(2024, 1, 1)))
        >>> db.close()
    """

    def __init__(self, db_path: str = "data/geopol.db"):
        """
        Initialize database instance.

        Args:
            db_path: Path to SQLite database file. Parent directory
                    will be created if it doesn't exist.
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """
        Establish database connection and initialize schema.

        Creates the database file and parent directories if needed.
        Initializes schema tables on first connection.

        Raises:
            sqlite3.Error: If connection fails
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self.connection.row_factory = sqlite3.Row
        init_schema(self.connection)
        logger.info(f"Connected to database: {self.db_path}")

    def close(self) -> None:
        """Close database connection if open."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # -------------------------------------------------------------------------
    # Event Operations
    # -------------------------------------------------------------------------

    def insert_event(self, event: Event) -> None:
        """
        Insert a single event into the database.

        Args:
            event: Event object to insert

        Raises:
            sqlite3.IntegrityError: If event_id already exists
        """
        self._ensure_connected()
        self.connection.execute(
            """
            INSERT INTO events (
                event_id, source, event_date, event_type, actors,
                location_country, location_region, cameo_code,
                goldstein_score, tone, source_url, headline, excerpt, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.source,
                event.event_date.isoformat(),
                event.event_type,
                json.dumps(event.actors),
                event.location_country,
                event.location_region,
                event.cameo_code,
                event.goldstein_score,
                event.tone,
                event.source_url,
                event.headline,
                event.excerpt,
                json.dumps(event.metadata or {}),
            )
        )
        self.connection.commit()

    def insert_events_batch(self, events: list[Event]) -> int:
        """
        Insert multiple events in a single transaction.

        Skips events that already exist (uses INSERT OR IGNORE).

        Args:
            events: List of Event objects to insert

        Returns:
            Number of events actually inserted

        Example:
            >>> inserted = db.insert_events_batch(events)
            >>> print(f"Inserted {inserted} new events")
        """
        self._ensure_connected()
        cursor = self.connection.cursor()
        inserted = 0

        for event in events:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO events (
                        event_id, source, event_date, event_type, actors,
                        location_country, location_region, cameo_code,
                        goldstein_score, tone, source_url, headline, excerpt, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.source,
                        event.event_date.isoformat(),
                        event.event_type,
                        json.dumps(event.actors),
                        event.location_country,
                        event.location_region,
                        event.cameo_code,
                        event.goldstein_score,
                        event.tone,
                        event.source_url,
                        event.headline,
                        event.excerpt,
                        json.dumps(event.metadata or {}),
                    )
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert event {event.event_id}: {e}")

        self.connection.commit()
        logger.info(f"Inserted {inserted}/{len(events)} events")
        return inserted

    def query_events(self, filter: EventFilter) -> list[Event]:
        """
        Query events with filtering.

        Builds dynamic SQL based on provided filter parameters.

        Args:
            filter: EventFilter with query parameters

        Returns:
            List of matching Event objects

        Example:
            >>> events = db.query_events(EventFilter(
            ...     start_date=date(2024, 1, 1),
            ...     actors=["USA", "CHN"],
            ...     limit=50
            ... ))
        """
        self._ensure_connected()

        conditions = []
        params = []

        if filter.start_date:
            conditions.append("event_date >= ?")
            params.append(filter.start_date.isoformat())

        if filter.end_date:
            conditions.append("event_date <= ?")
            params.append(filter.end_date.isoformat())

        if filter.sources:
            placeholders = ",".join("?" * len(filter.sources))
            conditions.append(f"source IN ({placeholders})")
            params.extend(filter.sources)

        if filter.countries:
            placeholders = ",".join("?" * len(filter.countries))
            conditions.append(f"location_country IN ({placeholders})")
            params.extend(filter.countries)

        if filter.event_types:
            placeholders = ",".join("?" * len(filter.event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(filter.event_types)

        if filter.min_goldstein is not None:
            conditions.append("goldstein_score >= ?")
            params.append(filter.min_goldstein)

        if filter.max_goldstein is not None:
            conditions.append("goldstein_score <= ?")
            params.append(filter.max_goldstein)

        # Actor filter uses JSON contains check
        if filter.actors:
            actor_conditions = []
            for actor in filter.actors:
                actor_conditions.append("actors LIKE ?")
                params.append(f'%"{actor}"%')
            conditions.append(f"({' OR '.join(actor_conditions)})")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM events
            WHERE {where_clause}
            ORDER BY event_date DESC
            LIMIT ? OFFSET ?
        """
        params.extend([filter.limit, filter.offset])

        cursor = self.connection.execute(query, params)
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_event(self, event_id: str) -> Optional[Event]:
        """
        Retrieve a single event by ID.

        Args:
            event_id: Unique event identifier

        Returns:
            Event object or None if not found
        """
        self._ensure_connected()
        cursor = self.connection.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event_id,)
        )
        row = cursor.fetchone()
        return self._row_to_event(row) if row else None

    def get_distinct_actors(self) -> list[str]:
        """
        Get list of all unique actors in the database.

        Returns:
            Sorted list of actor names

        Note:
            This scans all events and extracts actors from JSON.
            May be slow on large databases - consider caching.
        """
        self._ensure_connected()
        cursor = self.connection.execute("SELECT DISTINCT actors FROM events")
        actors = set()
        for row in cursor.fetchall():
            actors.update(json.loads(row[0]))
        return sorted(actors)

    def get_distinct_event_types(self) -> list[str]:
        """Get list of all unique event types."""
        self._ensure_connected()
        cursor = self.connection.execute("SELECT DISTINCT event_type FROM events")
        return sorted([row[0] for row in cursor.fetchall()])

    def get_distinct_countries(self) -> list[str]:
        """Get list of all unique country codes."""
        self._ensure_connected()
        cursor = self.connection.execute(
            "SELECT DISTINCT location_country FROM events WHERE location_country IS NOT NULL"
        )
        return sorted([row[0] for row in cursor.fetchall()])

    def get_event_count(self) -> int:
        """Get total number of events in database."""
        self._ensure_connected()
        cursor = self.connection.execute("SELECT COUNT(*) FROM events")
        return cursor.fetchone()[0]

    # -------------------------------------------------------------------------
    # Sync Status Operations
    # -------------------------------------------------------------------------

    def update_sync_status(
        self,
        source: str,
        status: str,
        event_count: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update sync status for a data source adapter.

        Args:
            source: Adapter name (gdelt, acled, etc.)
            status: Current status (idle, syncing, error)
            event_count: Number of events in last sync
            error: Error message if status is 'error'
        """
        self._ensure_connected()
        self.connection.execute(
            """
            INSERT OR REPLACE INTO sync_status
            (source, last_sync_time, last_sync_count, last_error, status)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            (source, event_count, error, status)
        )
        self.connection.commit()

    def get_sync_status(self, source: str) -> Optional[dict]:
        """
        Get sync status for a data source.

        Args:
            source: Adapter name

        Returns:
            Dict with status info or None if never synced
        """
        self._ensure_connected()
        cursor = self.connection.execute(
            "SELECT * FROM sync_status WHERE source = ?",
            (source,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_all_sync_status(self) -> list[dict]:
        """Get sync status for all sources."""
        self._ensure_connected()
        cursor = self.connection.execute("SELECT * FROM sync_status")
        return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        """Ensure database connection is active."""
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """Convert database row to Event model."""
        return Event(
            event_id=row["event_id"],
            source=row["source"],
            event_date=date.fromisoformat(row["event_date"]) if isinstance(row["event_date"], str) else row["event_date"],
            event_type=row["event_type"],
            actors=json.loads(row["actors"]),
            location_country=row["location_country"],
            location_region=row["location_region"],
            cameo_code=row["cameo_code"],
            goldstein_score=row["goldstein_score"],
            tone=row["tone"],
            source_url=row["source_url"],
            headline=row["headline"],
            excerpt=row["excerpt"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
