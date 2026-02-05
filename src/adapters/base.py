"""
Abstract base class for data source adapters.

All data source adapters must implement this interface to ensure
consistent behavior across different event data sources.

The adapter pattern allows:
- Adding new data sources without modifying existing code
- Consistent event format regardless of source
- Independent testing of each adapter
- Easy source comparison and validation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.models.event import Event


@dataclass
class SourceMetadata:
    """
    Metadata about a data source.

    Provides information about the source for display in the
    dashboard and for making decisions about data freshness.

    Attributes:
        name: Human-readable source name
        short_name: Abbreviated name for display
        description: Brief description of what this source provides
        update_frequency: How often source data updates (e.g., "15 minutes", "daily")
        coverage_start: Earliest date with available data
        geographic_coverage: Description of geographic scope
        event_types: Types of events this source provides
        documentation_url: Link to source documentation
        requires_api_key: Whether API key is needed
    """

    name: str
    short_name: str
    description: str
    update_frequency: str
    coverage_start: Optional[date] = None
    geographic_coverage: str = "Global"
    event_types: list[str] = None
    documentation_url: Optional[str] = None
    requires_api_key: bool = False

    def __post_init__(self):
        if self.event_types is None:
            self.event_types = []


class DataSourceAdapter(ABC):
    """
    Abstract base class for data source adapters.

    Each adapter is responsible for:
    1. Fetching raw data from its source
    2. Converting to standardized Event format
    3. Validating data quality
    4. Reporting connection/sync status

    Implementers must override all abstract methods.

    Example implementation structure:
        class MySourceAdapter(DataSourceAdapter):
            def fetch_events(self, date_range, region, filters):
                # 1. Build API request
                # 2. Fetch data
                # 3. Parse response
                # 4. Convert to Event objects
                # 5. Return list of Events
    """

    @abstractmethod
    def fetch_events(
        self,
        date_range: tuple[date, date],
        region: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> list[Event]:
        """
        Fetch events from source, return standardized Event objects.

        This is the primary data retrieval method. Implementations should:
        - Handle pagination if the source requires it
        - Convert source-specific formats to Event model
        - Apply any source-specific filtering
        - Log fetch progress for debugging

        Args:
            date_range: Tuple of (start_date, end_date) inclusive
            region: Optional region code to filter by (uses config region definitions)
            filters: Optional dict of source-specific filters

        Returns:
            List of Event objects normalized from source data

        Raises:
            ConnectionError: If source is unreachable
            ValueError: If date_range is invalid

        Example:
            >>> adapter = GDELTAdapter()
            >>> events = adapter.fetch_events(
            ...     date_range=(date(2024, 1, 1), date(2024, 1, 7)),
            ...     region="middle_east"
            ... )
            >>> print(f"Fetched {len(events)} events")
        """
        pass

    @abstractmethod
    def get_source_metadata(self) -> SourceMetadata:
        """
        Return information about this data source.

        Used by the dashboard to display source information
        and by the system to understand source capabilities.

        Returns:
            SourceMetadata object with source details

        Example:
            >>> metadata = adapter.get_source_metadata()
            >>> print(f"Source: {metadata.name}")
            >>> print(f"Updates: {metadata.update_frequency}")
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Test if the data source is accessible.

        Used by the Source Status dashboard to show connectivity.
        Implementations should make a minimal API call to verify
        the source is reachable and responding.

        Returns:
            True if source is accessible, False otherwise

        Note:
            This should be a lightweight check, not a full data fetch.
            Timeout should be short (5-10 seconds max).
        """
        pass

    def get_cameo_category(self, cameo_code: str) -> str:
        """
        Map CAMEO code to high-level event category.

        CAMEO codes are hierarchical:
        - First 2 digits: Main category (01-20)
        - Additional digits: Specificity

        This method maps to human-readable categories used
        in the Event Browser filter.

        Args:
            cameo_code: CAMEO event code (e.g., "010", "190")

        Returns:
            Human-readable event category

        Reference:
            CAMEO codebook: https://parusanalytics.com/eventdata/cameo.dir/CAMEO.Manual.1.1b3.pdf
        """
        if not cameo_code:
            return "unknown"

        # Extract main category (first 2 digits)
        main_code = cameo_code[:2] if len(cameo_code) >= 2 else cameo_code

        categories = {
            "01": "public_statement",
            "02": "appeal",
            "03": "express_intent_cooperate",
            "04": "consult",
            "05": "diplomatic_cooperation",
            "06": "material_cooperation",
            "07": "provide_aid",
            "08": "yield",
            "09": "investigate",
            "10": "demand",
            "11": "disapprove",
            "12": "reject",
            "13": "threaten",
            "14": "protest",
            "15": "exhibit_force",
            "16": "reduce_relations",
            "17": "coerce",
            "18": "assault",
            "19": "fight",
            "20": "mass_violence",
        }

        return categories.get(main_code, "other")

    def get_goldstein_scale_description(self, score: float) -> str:
        """
        Get human-readable description of Goldstein score.

        The Goldstein scale ranges from -10 (most conflictual)
        to +10 (most cooperative).

        Args:
            score: Goldstein score (-10 to +10)

        Returns:
            Description of the score's meaning

        Reference:
            Goldstein, J.S. (1992). "A Conflict-Cooperation Scale for
            WEIS Events Data." Journal of Conflict Resolution.
        """
        if score is None:
            return "unknown"
        if score >= 7:
            return "highly_cooperative"
        if score >= 3:
            return "cooperative"
        if score >= -1:
            return "neutral"
        if score >= -5:
            return "conflictual"
        return "highly_conflictual"
