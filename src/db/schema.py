"""
SQLite database schema definition.

This module defines the database schema for storing events, relationships,
and trends. The schema is designed to support multiple data sources while
maintaining a consistent structure for analysis.

Schema Design Decisions:
- actors stored as JSON array (flexible for varying number of actors)
- metadata stored as JSON (source-specific fields without schema changes)
- event_ids in trends stored as JSON array (variable length references)
- Indices on commonly queried fields (date, source, actors)
"""

SCHEMA_SQL = """
-- Events table: Core event data from all sources
-- This is the primary table storing normalized event data
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,           -- Format: {source}_{source_id}
    source TEXT NOT NULL,                -- gdelt, acled, sipri, news
    event_date DATE NOT NULL,            -- Date event occurred
    event_type TEXT NOT NULL,            -- High-level category
    actors TEXT NOT NULL DEFAULT '[]',   -- JSON array of actor names
    location_country TEXT,               -- ISO 3166-1 alpha-3
    location_region TEXT,                -- Sub-national region
    cameo_code TEXT,                     -- CAMEO event code
    goldstein_score REAL,                -- -10 to +10 scale
    tone REAL,                           -- Source sentiment score
    source_url TEXT,                     -- Link to original source
    headline TEXT,                       -- Event summary
    excerpt TEXT,                        -- Brief excerpt
    metadata TEXT DEFAULT '{}',          -- JSON for source-specific fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices for common query patterns
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_country ON events(location_country);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_cameo ON events(cameo_code);

-- Relationships table: Aggregated actor-to-actor interactions
-- Pre-computed aggregations for efficient trend analysis
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id TEXT PRIMARY KEY,    -- {actor_a}_{actor_b}_{window}
    actor_a TEXT NOT NULL,               -- First actor (alphabetically sorted)
    actor_b TEXT NOT NULL,               -- Second actor
    interaction_count INTEGER NOT NULL,  -- Number of events
    avg_goldstein REAL,                  -- Mean Goldstein score
    avg_tone REAL,                       -- Mean tone score
    min_goldstein REAL,                  -- Most conflictual
    max_goldstein REAL,                  -- Most cooperative
    window_start DATE NOT NULL,          -- Aggregation window start
    window_end DATE NOT NULL,            -- Aggregation window end
    event_types TEXT DEFAULT '{}',       -- JSON: {type: count}
    source_event_ids TEXT DEFAULT '[]',  -- JSON array of event IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rel_actors ON relationships(actor_a, actor_b);
CREATE INDEX IF NOT EXISTS idx_rel_window ON relationships(window_start, window_end);

-- Trends table: Detected patterns
-- Each trend must reference supporting events for verification
CREATE TABLE IF NOT EXISTS trends (
    trend_id TEXT PRIMARY KEY,
    trend_type TEXT NOT NULL,            -- frequency_anomaly, sentiment_shift, etc.
    description TEXT NOT NULL,           -- Human-readable description
    actors TEXT DEFAULT '[]',            -- JSON array of actors involved
    regions TEXT DEFAULT '[]',           -- JSON array of regions
    start_date DATE NOT NULL,
    end_date DATE,                       -- NULL if ongoing
    confidence REAL NOT NULL,            -- 0-1 confidence score
    magnitude REAL,                      -- Trend strength
    baseline_value REAL,                 -- Historical comparison value
    observed_value REAL,                 -- Actual observed value
    supporting_event_ids TEXT NOT NULL,  -- JSON array of event IDs (required)
    methodology TEXT NOT NULL,           -- Detection method description
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trends_type ON trends(trend_type);
CREATE INDEX IF NOT EXISTS idx_trends_dates ON trends(start_date, end_date);

-- Sync status table: Track adapter sync state
-- Used by Source Status page to show last sync times
CREATE TABLE IF NOT EXISTS sync_status (
    source TEXT PRIMARY KEY,             -- Adapter name
    last_sync_time TIMESTAMP,            -- Last successful sync
    last_sync_count INTEGER,             -- Events fetched in last sync
    last_error TEXT,                     -- Last error message if any
    status TEXT DEFAULT 'idle'           -- idle, syncing, error
);

-- Schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""


def init_schema(connection) -> None:
    """
    Initialize database schema.

    Creates all tables and indices if they don't exist.
    Safe to call multiple times (uses IF NOT EXISTS).

    Args:
        connection: SQLite database connection

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect("data/geopol.db")
        >>> init_schema(conn)
        >>> conn.close()
    """
    connection.executescript(SCHEMA_SQL)
    connection.commit()
