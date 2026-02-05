# Architecture Documentation

This document describes the architecture of the Geopolitical Intelligence Analysis Platform.

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Component Diagram](#component-diagram)
3. [Data Flow](#data-flow)
4. [Database Schema](#database-schema)
5. [Adapter Pattern](#adapter-pattern)
6. [Key Design Decisions](#key-design-decisions)
7. [How to Add New Data Sources](#how-to-add-new-data-sources)
8. [How to Modify Analytical Methods](#how-to-modify-analytical-methods)

---

## High-Level Overview

The platform consists of four main layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Streamlit)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Event Browser  │  │  Source Status  │  │   (Future)      │  │
│  │                 │  │                 │  │  Trend Analysis │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                         DATABASE LAYER                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    SQLite Database                       │    │
│  │  ┌──────────┐  ┌───────────────┐  ┌──────────────────┐  │    │
│  │  │  events  │  │ relationships │  │      trends      │  │    │
│  │  └──────────┘  └───────────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                     DATA SOURCE ADAPTERS                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  GDELT   │  │  ACLED   │  │  SIPRI   │  │  News Scraper    │ │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │     Adapter      │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
└───────┼─────────────┼─────────────┼─────────────────┼───────────┘
        │             │             │                 │
        ▼             ▼             ▼                 ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐    ┌─────────────┐
   │  GDELT  │   │  ACLED  │   │  SIPRI  │    │  RSS Feeds  │
   │   API   │   │   API   │   │  Files  │    │  + LLM API  │
   └─────────┘   └─────────┘   └─────────┘    └─────────────┘
```

---

## Component Diagram

### Directory Structure

```
geopol_dash/
├── app.py                 # Streamlit dashboard entry point
├── config.yaml            # Default configuration
├── config.local.yaml      # Local overrides (gitignored)
├── requirements.txt       # Python dependencies
├── ARCHITECTURE.md        # This document
├── README.md             # Setup and usage guide
│
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration loader
│   │
│   ├── adapters/         # Data source adapters
│   │   ├── __init__.py
│   │   ├── base.py       # Abstract base class
│   │   ├── gdelt.py      # GDELT implementation
│   │   ├── acled.py      # ACLED stub
│   │   ├── sipri.py      # SIPRI stub
│   │   └── news_scraper.py  # News scraper stub
│   │
│   ├── analysis/         # Analysis modules (Phase 2)
│   │   └── __init__.py
│   │
│   ├── api/              # FastAPI backend (Phase 2)
│   │   └── __init__.py
│   │
│   ├── db/               # Database layer
│   │   ├── __init__.py
│   │   ├── database.py   # Connection and query management
│   │   └── schema.py     # SQLite schema definition
│   │
│   └── models/           # Pydantic data models
│       ├── __init__.py
│       ├── event.py      # Event and EventFilter models
│       ├── relationship.py  # Relationship model
│       └── trend.py      # Trend model
│
├── tests/                # Test suite
│   └── __init__.py
│
└── data/                 # Data directory (gitignored contents)
    └── geopol.db        # SQLite database
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `app.py` | Streamlit UI, user interaction, display logic |
| `config.py` | Load and validate configuration, environment variable substitution |
| `adapters/base.py` | Define adapter interface (abstract base class) |
| `adapters/gdelt.py` | Fetch and parse GDELT event data |
| `db/database.py` | Database connection, CRUD operations, query building |
| `db/schema.py` | SQL schema definition, table creation |
| `models/*.py` | Data validation, serialization, type definitions |

---

## Data Flow

### Event Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EVENT INGESTION FLOW                          │
└─────────────────────────────────────────────────────────────────────┘

1. USER ACTION
   └── Clicks "Sync GDELT Data" in Source Status page
       └── Specifies region (e.g., "middle_east") and date range

2. ADAPTER FETCH
   └── GDELTAdapter.fetch_events(date_range, region)
       ├── Resolves region to country codes via config
       ├── For each day in range:
       │   ├── Fetches GDELT daily export file
       │   ├── Filters by country codes
       │   └── Converts rows to Event objects
       └── Returns List[Event]

3. DATABASE INSERT
   └── Database.insert_events_batch(events)
       ├── For each event:
       │   ├── Serializes actors/metadata as JSON
       │   └── Executes INSERT OR IGNORE
       └── Returns count of new events

4. STATUS UPDATE
   └── Database.update_sync_status("gdelt", "idle", event_count)

5. UI FEEDBACK
   └── Displays "Synced X new events" to user
```

### Event Query Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          EVENT QUERY FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

1. USER INPUT
   └── Sets filters in Event Browser:
       ├── Date range
       ├── Region → resolved to country codes
       ├── Actors (optional)
       ├── Event types (optional)
       └── Goldstein range

2. FILTER CONSTRUCTION
   └── EventFilter(start_date, end_date, countries, actors, ...)

3. DATABASE QUERY
   └── Database.query_events(filter)
       ├── Builds dynamic SQL WHERE clause
       ├── Handles JSON array search for actors
       └── Returns List[Event]

4. DISPLAY
   └── Renders table with:
       ├── Date, Actors, Type, Location, Goldstein, Headline
       └── Clickable source links
```

### Trend Detection (Phase 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TREND DETECTION FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

1. SCHEDULED ANALYSIS
   └── Runs periodically (e.g., daily)

2. BASELINE CALCULATION
   └── For each actor pair / region:
       ├── Query events for baseline period (e.g., 90 days)
       ├── Calculate mean event count, avg Goldstein
       └── Calculate standard deviation

3. CURRENT WINDOW
   └── For each actor pair / region:
       └── Query events for current window (e.g., 30 days)

4. ANOMALY DETECTION
   └── Compare current to baseline:
       ├── Z-score = (current - mean) / std_dev
       └── If abs(z_score) > threshold: flag as trend

5. TREND CREATION
   └── Create Trend objects with:
       ├── Description of pattern
       ├── Supporting event IDs (for verification)
       └── Methodology description

6. STORAGE
   └── Insert trends into database
```

### Briefing Generation (Phase 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     BRIEFING GENERATION FLOW                         │
└─────────────────────────────────────────────────────────────────────┘

1. USER REQUEST
   └── "Generate briefing for Middle East, past week"

2. DATA GATHERING
   ├── Query recent trends for region
   └── Query supporting events for each trend

3. SYNTHESIS PROMPT
   └── Build prompt with:
       ├── Trend descriptions
       ├── Event details
       └── Instructions for analysis:
           - Material vs symbolic significance
           - Signaling implications
           - Historical context

4. LLM CALL
   └── Anthropic API with structured output format

5. CITATION VERIFICATION
   └── Ensure all claims reference event IDs

6. OUTPUT
   └── Briefing with:
       ├── Summary section
       ├── Trend-by-trend analysis
       └── Footnote panel with event details
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                              │
└─────────────────────────────────────────────────────────────────────┘

events                          relationships
┌────────────────────────┐     ┌──────────────────────────┐
│ event_id (PK)          │     │ relationship_id (PK)     │
│ source                 │     │ actor_a                  │
│ event_date             │     │ actor_b                  │
│ event_type             │     │ interaction_count        │
│ actors (JSON)          │     │ avg_goldstein            │
│ location_country       │     │ avg_tone                 │
│ location_region        │     │ min_goldstein            │
│ cameo_code             │     │ max_goldstein            │
│ goldstein_score        │     │ window_start             │
│ tone                   │     │ window_end               │
│ source_url             │     │ event_types (JSON)       │
│ headline               │     │ source_event_ids (JSON)  │◄──┐
│ excerpt                │     │ created_at               │   │
│ metadata (JSON)        │     └──────────────────────────┘   │
│ created_at             │                                     │
└────────────────────────┘     trends                          │
         │                     ┌──────────────────────────┐    │
         │                     │ trend_id (PK)            │    │
         │                     │ trend_type               │    │
         │                     │ description              │    │
         │                     │ actors (JSON)            │    │
         │                     │ regions (JSON)           │    │
         │                     │ start_date               │    │
         │                     │ end_date                 │    │
         │                     │ confidence               │    │
         │                     │ magnitude                │    │
         │                     │ baseline_value           │    │
         │                     │ observed_value           │    │
         └─────────────────────│ supporting_event_ids (J) │────┘
                               │ methodology              │
                               │ created_at               │
                               └──────────────────────────┘
```

### Table Details

#### `events` - Core event data

| Column | Type | Description |
|--------|------|-------------|
| event_id | TEXT PK | Unique ID: `{source}_{source_id}` |
| source | TEXT | Data source: gdelt, acled, sipri, news |
| event_date | DATE | When the event occurred |
| event_type | TEXT | Category from CAMEO mapping |
| actors | TEXT (JSON) | Array of actor names |
| location_country | TEXT | ISO 3166-1 alpha-3 code |
| cameo_code | TEXT | CAMEO event code |
| goldstein_score | REAL | -10 to +10 conflict-cooperation scale |
| tone | REAL | Sentiment score from source |
| source_url | TEXT | Link to original source |
| metadata | TEXT (JSON) | Source-specific fields |

#### `relationships` - Aggregated interactions

Computed from events to enable efficient trend analysis.

| Column | Type | Description |
|--------|------|-------------|
| relationship_id | TEXT PK | `{actor_a}_{actor_b}_{window}` |
| actor_a, actor_b | TEXT | Actor pair (alphabetically sorted) |
| interaction_count | INT | Number of events |
| avg_goldstein | REAL | Mean Goldstein score |
| window_start/end | DATE | Aggregation time window |
| source_event_ids | TEXT (JSON) | Events contributing to this relationship |

#### `trends` - Detected patterns

| Column | Type | Description |
|--------|------|-------------|
| trend_id | TEXT PK | Unique identifier |
| trend_type | TEXT | frequency_anomaly, sentiment_shift, etc. |
| confidence | REAL | Statistical confidence (0-1) |
| supporting_event_ids | TEXT (JSON) | **Required** - Events proving this trend |
| methodology | TEXT | How the trend was detected |

---

## Adapter Pattern

### Why Adapters?

Different data sources provide event data in different formats:
- **GDELT**: Tab-separated CSV exports with 60+ columns
- **ACLED**: JSON API with different field names
- **SIPRI**: Excel files with annual data
- **News**: Unstructured text requiring LLM extraction

The adapter pattern provides:
1. **Uniform interface** - All sources implement the same methods
2. **Isolation** - Source-specific code is contained in its adapter
3. **Testability** - Each adapter can be tested independently
4. **Extensibility** - New sources require only a new adapter file

### Interface Definition

```python
class DataSourceAdapter(ABC):
    @abstractmethod
    def fetch_events(
        self,
        date_range: tuple[date, date],
        region: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> list[Event]:
        """Fetch events from source, return standardized Event objects"""

    @abstractmethod
    def get_source_metadata(self) -> SourceMetadata:
        """Return info about this source (name, update frequency, coverage)"""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test if source is accessible"""
```

### Implementation Notes

Each adapter is responsible for:

1. **Connecting** to its data source (API, file, etc.)
2. **Fetching** raw data for the requested date range and region
3. **Parsing** source-specific format
4. **Converting** to standardized `Event` objects
5. **Mapping** source event types to CAMEO categories
6. **Preserving** source-specific fields in `metadata`

---

## Key Design Decisions

### 1. SQLite over PostgreSQL

**Decision**: Use SQLite for data storage.

**Rationale**:
- This is a personal research tool, not a production system
- SQLite requires no server setup
- Single file is easy to backup and share
- Sufficient performance for expected data volumes (<1M events)
- Can migrate to PostgreSQL later if needed

### 2. Streamlit over React

**Decision**: Use Streamlit for the frontend.

**Rationale**:
- Rapid prototyping - get working dashboard quickly
- Python-native - same language as backend
- Built-in data visualization support
- No JavaScript/npm complexity
- Easy to iterate on during research

**Trade-off**: Less control over UI details than React would provide.

### 3. JSON Arrays in SQLite

**Decision**: Store actors and metadata as JSON strings.

**Rationale**:
- Variable number of actors per event (0 to many)
- Source-specific metadata varies by source
- SQLite has JSON functions for querying
- Avoids complex join tables for simple use case

**Trade-off**: Less efficient querying on JSON fields.

### 4. CAMEO Event Coding

**Decision**: Map all events to CAMEO categories.

**Rationale**:
- Established standard in political science
- Enables cross-source comparison
- Provides Goldstein scale for conflict-cooperation
- Well-documented codebook available

### 5. Required Event References in Trends

**Decision**: Trends must have `supporting_event_ids` (non-empty list).

**Rationale**:
- Core principle: "Verifiable Claims"
- Every analytical statement must be traceable to source data
- Users can inspect underlying events
- Prevents "black box" analysis

---

## How to Add New Data Sources

### Step 1: Create Adapter File

```python
# src/adapters/my_source.py
from src.adapters.base import DataSourceAdapter, SourceMetadata
from src.models.event import Event

class MySourceAdapter(DataSourceAdapter):
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def fetch_events(self, date_range, region=None, filters=None):
        # 1. Build request to your source
        # 2. Fetch data
        # 3. Parse response
        # 4. Convert to Event objects
        events = []
        for raw_event in raw_data:
            events.append(Event(
                event_id=f"mysource_{raw_event['id']}",
                source="mysource",
                event_date=parse_date(raw_event['date']),
                event_type=self.get_cameo_category(raw_event['type']),
                actors=[raw_event['actor1'], raw_event['actor2']],
                # ... map other fields
            ))
        return events

    def get_source_metadata(self):
        return SourceMetadata(
            name="My Data Source",
            short_name="MYSRC",
            # ... other metadata
        )

    def validate_connection(self):
        # Test API connectivity
        return True
```

### Step 2: Update Configuration

```yaml
# config.yaml
data_sources:
  enabled:
    - gdelt
    - mysource  # Add new source

  mysource:
    api_key: ${MYSOURCE_API_KEY}
```

### Step 3: Register in Dashboard

```python
# app.py - in show_source_status()
from src.adapters.my_source import MySourceAdapter

sources = [
    ("gdelt", GDELTAdapter()),
    ("mysource", MySourceAdapter()),
    # ...
]
```

### Step 4: Test

```python
# tests/test_my_source.py
def test_fetch_events():
    adapter = MySourceAdapter()
    events = adapter.fetch_events(
        date_range=(date(2024, 1, 1), date(2024, 1, 7))
    )
    assert len(events) > 0
    assert all(e.source == "mysource" for e in events)
```

---

## How to Modify Analytical Methods

### Event Type Categorization

Located in `src/adapters/base.py`:

```python
def get_cameo_category(self, cameo_code: str) -> str:
    """Map CAMEO code to category. Modify this dict to change mappings."""
    categories = {
        "01": "public_statement",
        "02": "appeal",
        # ... add or modify categories
    }
```

### Goldstein Score Interpretation

Located in `src/adapters/base.py`:

```python
def get_goldstein_scale_description(self, score: float) -> str:
    """Modify thresholds or descriptions here."""
    if score >= 7:
        return "highly_cooperative"
    # ... modify thresholds
```

### Analysis Parameters

All tunable parameters are in `config.yaml`:

```yaml
analysis:
  moving_average_window_days: 30  # Smoothing window
  baseline_period_days: 90        # Historical comparison
  anomaly_threshold_std: 2.0      # Sensitivity
  min_events_for_trend: 5         # Noise filter
```

### Adding New Trend Types

1. Add to `TrendType` enum in `src/models/trend.py`
2. Implement detection logic in `src/analysis/` (Phase 2)
3. Update dashboard to display new trend type

---

## Logging and Debugging

### Key Log Points

The application logs at these key stages:

```
Event fetch:     "Fetching GDELT events from X to Y, region=Z"
                 "Fetched N events for DATE"
                 "Total events fetched: N"

Database:        "Connected to database: PATH"
                 "Inserted N/M events"

Sync status:     "Sync complete! Inserted N new events"
                 "Sync failed: ERROR"

Configuration:   "Loading configuration from FILE"
                 "Logging configured: level=X, file=Y"
```

### Inspection Tools

1. **Event Browser**: View raw events with all fields
2. **Source Status**: Check adapter connectivity
3. **Database**: Query directly with `sqlite3 data/geopol.db`

### Debug Mode

Set in `config.yaml`:

```yaml
logging:
  level: DEBUG
```

This enables verbose logging including:
- HTTP requests/responses
- SQL queries
- Event conversion details
