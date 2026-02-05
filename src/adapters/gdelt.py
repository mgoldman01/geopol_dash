"""
GDELT (Global Database of Events, Language, and Tone) adapter.

GDELT is a real-time database of global events, updated every 15 minutes.
This adapter fetches events from the GDELT 2.0 API and converts them
to our standardized Event format.

Data source: https://www.gdeltproject.org/
API docs: https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/

GDELT provides:
- Event records with CAMEO coding
- Goldstein scores for conflict/cooperation
- Tone/sentiment analysis
- Actor identification
- Geographic coding
- Source URLs to original articles

Rate limits: GDELT is free and has generous limits, but be respectful.
Recommended: Don't make more than 1 request per second.
"""

import logging
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Optional
from urllib.parse import urlencode

import httpx
import pandas as pd

from src.adapters.base import DataSourceAdapter, SourceMetadata
from src.models.event import Event

logger = logging.getLogger(__name__)

# GDELT 2.0 Event Database columns we care about
# Full schema: http://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf
GDELT_COLUMNS = [
    "GLOBALEVENTID",
    "SQLDATE",
    "Actor1Code",
    "Actor1Name",
    "Actor1CountryCode",
    "Actor1Type1Code",
    "Actor2Code",
    "Actor2Name",
    "Actor2CountryCode",
    "Actor2Type1Code",
    "IsRootEvent",
    "EventCode",
    "EventBaseCode",
    "EventRootCode",
    "QuadClass",
    "GoldsteinScale",
    "NumMentions",
    "NumSources",
    "NumArticles",
    "AvgTone",
    "Actor1Geo_CountryCode",
    "Actor2Geo_CountryCode",
    "ActionGeo_CountryCode",
    "ActionGeo_FullName",
    "SOURCEURL",
]


class GDELTAdapter(DataSourceAdapter):
    """
    Adapter for fetching events from GDELT 2.0.

    Uses the GDELT Analysis Service API to query historical events.
    Events are converted to our standardized format with CAMEO codes,
    Goldstein scores, and tone metrics preserved.

    Attributes:
        base_url: GDELT API endpoint
        timeout: Request timeout in seconds
        country_mapping: Maps region names to country codes

    Example:
        >>> adapter = GDELTAdapter()
        >>> if adapter.validate_connection():
        ...     events = adapter.fetch_events(
        ...         date_range=(date(2024, 1, 1), date(2024, 1, 7)),
        ...         region="middle_east"
        ...     )
        ...     print(f"Fetched {len(events)} events")
    """

    # GDELT 2.0 GKG API for event queries
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    # Alternative: Direct event file access (for bulk historical)
    EVENT_URL = "http://data.gdeltproject.org/gdeltv2"

    def __init__(
        self,
        timeout: int = 30,
        country_mapping: Optional[dict[str, list[str]]] = None
    ):
        """
        Initialize GDELT adapter.

        Args:
            timeout: HTTP request timeout in seconds
            country_mapping: Dict mapping region names to lists of ISO country codes.
                           If None, uses default Middle East definition.
        """
        self.timeout = timeout
        self.country_mapping = country_mapping or {
            "middle_east": [
                "SYR", "IRQ", "IRN", "SAU", "ARE", "YEM", "OMN", "KWT",
                "QAT", "BHR", "JOR", "LBN", "ISR", "PSE", "EGY", "TUR"
            ],
            "africa": [
                "DZA", "AGO", "BEN", "BWA", "BFA", "BDI", "CPV", "CMR",
                "CAF", "TCD", "COM", "COD", "COG", "CIV", "DJI", "EGY",
                "GNQ", "ERI", "SWZ", "ETH", "GAB", "GMB", "GHA", "GIN",
                "GNB", "KEN", "LSO", "LBR", "LBY", "MDG", "MWI", "MLI",
                "MRT", "MUS", "MAR", "MOZ", "NAM", "NER", "NGA", "RWA",
                "STP", "SEN", "SYC", "SLE", "SOM", "ZAF", "SSD", "SDN",
                "TZA", "TGO", "TUN", "UGA", "ZMB", "ZWE"
            ],
            "east_asia": [
                "CHN", "JPN", "KOR", "PRK", "MNG", "TWN", "HKG", "MAC"
            ],
            "europe": [
                "ALB", "AND", "AUT", "BLR", "BEL", "BIH", "BGR", "HRV",
                "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC",
                "HUN", "ISL", "IRL", "ITA", "LVA", "LIE", "LTU", "LUX",
                "MLT", "MDA", "MCO", "MNE", "NLD", "MKD", "NOR", "POL",
                "PRT", "ROU", "RUS", "SMR", "SRB", "SVK", "SVN", "ESP",
                "SWE", "CHE", "UKR", "GBR", "VAT"
            ],
        }
        self._client: Optional[httpx.Client] = None

    def fetch_events(
        self,
        date_range: tuple[date, date],
        region: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> list[Event]:
        """
        Fetch events from GDELT for the specified date range and region.

        Uses GDELT's doc API for event queries. For large date ranges,
        this may take some time as GDELT returns data in chunks.

        Args:
            date_range: (start_date, end_date) inclusive
            region: Region key from country_mapping (e.g., "middle_east")
            filters: Optional additional filters:
                - actor: Filter by specific actor code
                - event_type: Filter by CAMEO root code
                - min_tone: Minimum tone score
                - max_tone: Maximum tone score

        Returns:
            List of Event objects

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If date range is invalid

        Note:
            GDELT API has undocumented limits. For large queries,
            consider breaking into smaller date chunks.
        """
        start_date, end_date = date_range

        if start_date > end_date:
            raise ValueError(f"Invalid date range: {start_date} > {end_date}")

        logger.info(f"Fetching GDELT events from {start_date} to {end_date}, region={region}")

        # Get country codes for region filter
        country_codes = []
        if region and region in self.country_mapping:
            country_codes = self.country_mapping[region]

        # Build query
        events = []
        current_date = start_date

        # Fetch day by day to avoid overwhelming the API
        while current_date <= end_date:
            day_events = self._fetch_day_events(current_date, country_codes, filters)
            events.extend(day_events)
            logger.info(f"Fetched {len(day_events)} events for {current_date}")

            current_date += timedelta(days=1)
            time.sleep(0.5)  # Be nice to the API

        logger.info(f"Total events fetched: {len(events)}")
        return events

    def _fetch_day_events(
        self,
        target_date: date,
        country_codes: list[str],
        filters: Optional[dict]
    ) -> list[Event]:
        """
        Fetch events for a single day.

        Args:
            target_date: Date to fetch
            country_codes: List of country codes to filter by
            filters: Additional filters

        Returns:
            List of Event objects for that day
        """
        # Build GDELT query
        # Using the GKG doc API with event mode
        query_parts = []

        # Date filter
        date_str = target_date.strftime("%Y%m%d")
        query_parts.append(f"sourcecountry:{date_str}")

        # Country filter
        if country_codes:
            country_query = " OR ".join([f"actiongeocountry:{c}" for c in country_codes])
            query_parts.append(f"({country_query})")

        params = {
            "query": " ".join(query_parts) if query_parts else "*",
            "mode": "artlist",
            "maxrecords": 250,
            "format": "json",
            "startdatetime": f"{date_str}000000",
            "enddatetime": f"{date_str}235959",
        }

        try:
            # Use the event export files instead for more reliable data
            events = self._fetch_from_event_export(target_date, country_codes)
            return events
        except Exception as e:
            logger.warning(f"Error fetching events for {target_date}: {e}")
            return []

    def _fetch_from_event_export(
        self,
        target_date: date,
        country_codes: list[str]
    ) -> list[Event]:
        """
        Fetch events from GDELT's daily event export files.

        GDELT publishes daily event export files in CSV format.
        This is more reliable than the API for historical data.

        Args:
            target_date: Date to fetch
            country_codes: Countries to filter by

        Returns:
            List of Event objects
        """
        # GDELT export file URL pattern
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.EVENT_URL}/{date_str}.export.CSV.zip"

        # For dates > 2013, use the v2 format with timestamps
        # For simplicity, we'll use the daily summary endpoint
        # which aggregates the 15-minute updates

        # Use the events API endpoint instead
        events_url = f"http://data.gdeltproject.org/events/{date_str}.export.CSV.zip"

        try:
            client = self._get_client()

            # Try the BigQuery-exported daily files (more accessible)
            # These are available at a different endpoint
            bq_url = f"http://data.gdeltproject.org/gdeltv2/{date_str}230000.export.CSV.zip"

            response = client.get(bq_url, timeout=self.timeout)

            if response.status_code == 404:
                # Try alternative format
                alt_url = f"http://data.gdeltproject.org/events/{date_str}.export.CSV.zip"
                response = client.get(alt_url, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"GDELT export not available for {target_date}: {response.status_code}")
                return []

            # Parse the CSV data
            # GDELT files are tab-separated with no header
            import zipfile
            from io import BytesIO

            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                # Get the CSV file from the zip
                csv_name = zf.namelist()[0]
                with zf.open(csv_name) as f:
                    content = f.read().decode("utf-8", errors="ignore")

            # Parse as DataFrame
            df = pd.read_csv(
                StringIO(content),
                sep="\t",
                header=None,
                names=self._get_gdelt_column_names(),
                low_memory=False
            )

            # Filter by country if specified
            if country_codes:
                df = df[
                    df["ActionGeo_CountryCode"].isin(country_codes) |
                    df["Actor1CountryCode"].isin(country_codes) |
                    df["Actor2CountryCode"].isin(country_codes)
                ]

            # Convert to Event objects
            events = []
            for _, row in df.iterrows():
                event = self._row_to_event(row)
                if event:
                    events.append(event)

            return events

        except Exception as e:
            logger.error(f"Error fetching GDELT export: {e}")
            return []

    def _get_gdelt_column_names(self) -> list[str]:
        """
        Get GDELT 1.0 event export column names.

        Returns full list of 58 columns in the export file.

        Reference:
            http://data.gdeltproject.org/documentation/GDELT-Data_Format_Codebook.pdf
        """
        return [
            "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year", "FractionDate",
            "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
            "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
            "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
            "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
            "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
            "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code",
            "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode",
            "QuadClass", "GoldsteinScale", "NumMentions", "NumSources",
            "NumArticles", "AvgTone",
            "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode",
            "Actor1Geo_ADM1Code", "Actor1Geo_ADM2Code", "Actor1Geo_Lat",
            "Actor1Geo_Long", "Actor1Geo_FeatureID",
            "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode",
            "Actor2Geo_ADM1Code", "Actor2Geo_ADM2Code", "Actor2Geo_Lat",
            "Actor2Geo_Long", "Actor2Geo_FeatureID",
            "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode",
            "ActionGeo_ADM1Code", "ActionGeo_ADM2Code", "ActionGeo_Lat",
            "ActionGeo_Long", "ActionGeo_FeatureID",
            "DATEADDED", "SOURCEURL"
        ]

    def _row_to_event(self, row: pd.Series) -> Optional[Event]:
        """
        Convert a GDELT DataFrame row to an Event object.

        Args:
            row: Pandas Series with GDELT event data

        Returns:
            Event object or None if conversion fails
        """
        try:
            # Parse date
            sql_date = str(row.get("SQLDATE", ""))
            if len(sql_date) == 8:
                event_date = date(
                    int(sql_date[:4]),
                    int(sql_date[4:6]),
                    int(sql_date[6:8])
                )
            else:
                return None

            # Build actors list
            actors = []
            if pd.notna(row.get("Actor1Name")):
                actors.append(str(row["Actor1Name"]))
            elif pd.notna(row.get("Actor1CountryCode")):
                actors.append(str(row["Actor1CountryCode"]))

            if pd.notna(row.get("Actor2Name")):
                actors.append(str(row["Actor2Name"]))
            elif pd.notna(row.get("Actor2CountryCode")):
                actors.append(str(row["Actor2CountryCode"]))

            # Get CAMEO code
            cameo_code = str(row.get("EventCode", "")) if pd.notna(row.get("EventCode")) else None

            # Get event type from CAMEO
            event_type = self.get_cameo_category(cameo_code) if cameo_code else "unknown"

            # Get location
            location_country = None
            for col in ["ActionGeo_CountryCode", "Actor1Geo_CountryCode", "Actor2Geo_CountryCode"]:
                if pd.notna(row.get(col)):
                    location_country = str(row[col])
                    break

            # Get Goldstein score
            goldstein = None
            if pd.notna(row.get("GoldsteinScale")):
                try:
                    goldstein = float(row["GoldsteinScale"])
                except (ValueError, TypeError):
                    pass

            # Get tone
            tone = None
            if pd.notna(row.get("AvgTone")):
                try:
                    tone = float(row["AvgTone"])
                except (ValueError, TypeError):
                    pass

            # Get source URL
            source_url = str(row.get("SOURCEURL", "")) if pd.notna(row.get("SOURCEURL")) else None

            # Build event ID
            event_id = f"gdelt_{row.get('GLOBALEVENTID', '')}"

            return Event(
                event_id=event_id,
                source="gdelt",
                event_date=event_date,
                event_type=event_type,
                actors=actors,
                location_country=location_country,
                cameo_code=cameo_code,
                goldstein_score=goldstein,
                tone=tone,
                source_url=source_url,
                headline=None,  # GDELT events don't have headlines
                excerpt=None,
                metadata={
                    "quad_class": int(row["QuadClass"]) if pd.notna(row.get("QuadClass")) else None,
                    "num_mentions": int(row["NumMentions"]) if pd.notna(row.get("NumMentions")) else None,
                    "num_sources": int(row["NumSources"]) if pd.notna(row.get("NumSources")) else None,
                    "num_articles": int(row["NumArticles"]) if pd.notna(row.get("NumArticles")) else None,
                    "is_root_event": bool(row["IsRootEvent"]) if pd.notna(row.get("IsRootEvent")) else None,
                    "action_geo_fullname": str(row["ActionGeo_FullName"]) if pd.notna(row.get("ActionGeo_FullName")) else None,
                }
            )

        except Exception as e:
            logger.debug(f"Error converting GDELT row: {e}")
            return None

    def get_source_metadata(self) -> SourceMetadata:
        """
        Return GDELT source metadata.

        Returns:
            SourceMetadata with GDELT information
        """
        return SourceMetadata(
            name="Global Database of Events, Language, and Tone",
            short_name="GDELT",
            description=(
                "Real-time database of global events extracted from news media. "
                "Provides CAMEO-coded events with Goldstein scores, sentiment, "
                "and actor identification. Updated every 15 minutes."
            ),
            update_frequency="15 minutes",
            coverage_start=date(1979, 1, 1),
            geographic_coverage="Global",
            event_types=[
                "public_statement", "appeal", "diplomatic_cooperation",
                "material_cooperation", "provide_aid", "protest",
                "threaten", "reduce_relations", "assault", "fight"
            ],
            documentation_url="https://www.gdeltproject.org/data.html",
            requires_api_key=False
        )

    def validate_connection(self) -> bool:
        """
        Test if GDELT is accessible.

        Makes a minimal request to verify connectivity.

        Returns:
            True if GDELT responds successfully
        """
        try:
            client = self._get_client()
            # Try to access the GDELT project page
            response = client.head(
                "https://www.gdeltproject.org/",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"GDELT connection check failed: {e}")
            return False

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "GeopolDash/0.1 (Research Tool)"
                }
            )
        return self._client

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
