# geopol_trend_tracking
Platform for tracking geopolitical news and analyzing trends to understand large-scale changes.
# Geopolitical Intelligence Analysis Platform

A web-based platform that aggregates event data from multiple sources, detects emergent patterns, and provides verifiable synthesis through an interactive dashboard.

## Features

- **Event Browser**: Search and filter geopolitical events by date, region, actors, and event type
- **Multi-Source Integration**: Unified interface for GDELT, ACLED, SIPRI, and custom news sources
- **CAMEO Coding**: Standardized event classification using established political science frameworks
- **Goldstein Scores**: Conflict-cooperation intensity metrics (-10 to +10 scale)
- **Source Verification**: All events link to original source documents

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd geopol_dash

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

### First-Time Setup

1. Open the dashboard
2. Navigate to **Source Status**
3. Click **Test** next to GDELT to verify connectivity
4. Set region and date range, then click **Sync GDELT Data**
5. Navigate to **Event Browser** to explore events

## Configuration

### Basic Configuration

Copy `config.yaml` to `config.local.yaml` for local customization:

```bash
cp config.yaml config.local.yaml
```

Edit `config.local.yaml` to:
- Enable/disable data sources
- Define custom regions
- Adjust analysis parameters
- Set API keys

### Environment Variables

API keys should be set as environment variables:

```bash
export ANTHROPIC_API_KEY="your-key-here"
export ACLED_API_KEY="your-key-here"
```

Or create a `.env` file (add to `.gitignore`):

```
ANTHROPIC_API_KEY=your-key-here
ACLED_API_KEY=your-key-here
```

### Region Definitions

Regions map names to lists of ISO 3166-1 alpha-3 country codes:

```yaml
regions:
  middle_east:
    name: "Middle East"
    countries:
      - SYR  # Syria
      - IRQ  # Iraq
      - IRN  # Iran
      # ...
```

## Usage Guide

### Event Browser

1. **Set Date Range**: Select start and end dates
2. **Choose Region**: Filter by geographic region (or "All Regions")
3. **Filter Actors**: Optionally filter to events involving specific actors
4. **Select Event Types**: Filter by CAMEO category
5. **Adjust Goldstein Range**: Focus on cooperative or conflictual events

Results display in a table with:
- Date, Actors, Type, Location, Goldstein Score, Headline
- Click "View" to open original source

### Source Status

Shows connectivity and sync status for each data source:
- **Enabled/Disabled**: Whether source is active in config
- **Status**: Last sync result (OK, Error, Never synced)
- **Test**: Verify source connectivity
- **Sync**: Fetch new events from source

### Understanding Event Data

#### CAMEO Event Types

| Code | Category | Description |
|------|----------|-------------|
| 01 | public_statement | Make public statement |
| 02 | appeal | Appeal for cooperation |
| 03-08 | cooperation | Various cooperative actions |
| 09 | investigate | Investigate |
| 10-12 | verbal_conflict | Demand, disapprove, reject |
| 13-15 | threat/protest | Threaten, protest, exhibit force |
| 16-20 | material_conflict | Coerce, assault, fight |

#### Goldstein Scale

| Score | Interpretation |
|-------|---------------|
| +7 to +10 | Highly cooperative |
| +3 to +7 | Cooperative |
| -1 to +3 | Neutral |
| -5 to -1 | Conflictual |
| -10 to -5 | Highly conflictual |

## Data Sources

### GDELT (Active)

- **Description**: Real-time database of global events from news media
- **Update Frequency**: Every 15 minutes
- **Coverage**: Global, 1979-present
- **API Key Required**: No
- **Documentation**: https://www.gdeltproject.org/

### ACLED (Planned)

- **Description**: Armed conflict and protest events
- **Update Frequency**: Weekly
- **Coverage**: Global conflict regions
- **API Key Required**: Yes (free for researchers)
- **Documentation**: https://acleddata.com/

### SIPRI (Planned)

- **Description**: Arms transfers, military expenditure
- **Update Frequency**: Annual
- **Coverage**: Global
- **API Key Required**: No (manual data import)
- **Documentation**: https://www.sipri.org/databases

### News Scraper (Planned)

- **Description**: Custom event extraction from RSS feeds via LLM
- **Update Frequency**: Configurable
- **Coverage**: Depends on configured feeds
- **API Key Required**: Yes (Anthropic API)

## Project Structure

```
geopol_dash/
├── app.py                 # Streamlit dashboard
├── config.yaml            # Default configuration
├── requirements.txt       # Python dependencies
├── ARCHITECTURE.md        # Technical documentation
├── README.md             # This file
│
├── src/
│   ├── config.py         # Configuration loader
│   ├── adapters/         # Data source adapters
│   │   ├── base.py       # Abstract interface
│   │   ├── gdelt.py      # GDELT implementation
│   │   ├── acled.py      # ACLED (stub)
│   │   ├── sipri.py      # SIPRI (stub)
│   │   └── news_scraper.py  # News (stub)
│   ├── db/               # Database layer
│   │   ├── database.py   # Connection/queries
│   │   └── schema.py     # SQLite schema
│   └── models/           # Data models
│       ├── event.py
│       ├── relationship.py
│       └── trend.py
│
├── tests/                # Test suite
└── data/                 # Database files
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ tests/ app.py
ruff check src/ tests/ app.py
```

### Adding a New Data Source

1. Create adapter in `src/adapters/my_source.py`
2. Implement `DataSourceAdapter` interface
3. Add configuration in `config.yaml`
4. Register in `app.py` Source Status page

See ARCHITECTURE.md for detailed instructions.

## Troubleshooting

### "No events found"

1. Check Source Status - ensure GDELT shows "OK"
2. Try syncing data: Source Status → Sync GDELT Data
3. Verify date range includes synced dates
4. Try "All Regions" to eliminate region filter

### GDELT sync fails

1. Check internet connectivity
2. GDELT may be temporarily unavailable - try again later
3. Check logs: `tail -f logs/geopol.log`

### Database errors

Reset the database:

```bash
rm data/geopol.db
streamlit run app.py  # Will recreate on startup
```

### Configuration not loading

1. Check YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
2. Verify environment variables are set
3. Check file permissions

## Roadmap

### Phase 1 (Current)
- [x] Database schema
- [x] GDELT adapter
- [x] Event Browser dashboard
- [x] Source Status dashboard
- [x] Configuration management

### Phase 2 (Planned)
- [ ] Trend detection algorithms
- [ ] Relationship aggregation
- [ ] ACLED adapter implementation
- [ ] Analysis dashboard

### Phase 3 (Planned)
- [ ] LLM-powered briefing generation
- [ ] News scraper implementation
- [ ] Citation verification
- [ ] Export capabilities

## References

- [GDELT Project](https://www.gdeltproject.org/)
- [CAMEO Codebook](https://parusanalytics.com/eventdata/cameo.dir/CAMEO.09b6.pdf)
- Goldstein, J.S. (1992). "A Conflict-Cooperation Scale for WEIS Events Data." *Journal of Conflict Resolution*.
- [ACLED Methodology](https://acleddata.com/resources/methodology/)
- [SIPRI Databases](https://www.sipri.org/databases)

## License

[Your chosen license]

## Contributing

[Your contribution guidelines]
