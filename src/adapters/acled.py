"""
ACLED (Armed Conflict Location & Event Data Project) adapter.

TODO: Implement ACLED adapter for armed conflict event data.

ACLED provides:
- Armed conflict and protest events
- Detailed actor identification (armed groups, militias, state forces)
- Fatality estimates
- Sub-national geographic precision
- Weekly updates

Data source: https://acleddata.com/
API docs: https://acleddata.com/acleddatanew/wp-content/uploads/2021/11/ACLED_API-User-Guide.pdf

Key differences from GDELT:
- Focus on political violence and protest (not all political events)
- Human-coded (higher accuracy, but slower updates)
- Requires API key (free for researchers)
- Better sub-national location data
- Includes fatality estimates

Implementation notes:
1. Register for API key at https://acleddata.com/register/
2. Use ISO country codes for region filtering
3. Event types map to ACLED categories (battles, protests, riots, etc.)
4. Consider mapping ACLED event types to CAMEO codes for consistency
5. Fatality data should go in metadata field

Expected usage:
    >>> adapter = ACLEDAdapter(api_key="your_key_here")
    >>> events = adapter.fetch_events(
    ...     date_range=(date(2024, 1, 1), date(2024, 1, 31)),
    ...     region="middle_east"
    ... )
"""

import logging
from datetime import date
from typing import Optional

from src.adapters.base import DataSourceAdapter, SourceMetadata
from src.models.event import Event

logger = logging.getLogger(__name__)


class ACLEDAdapter(DataSourceAdapter):
    """
    Adapter for ACLED armed conflict data.

    TODO: Implement this adapter.

    ACLED provides detailed armed conflict and protest data with:
    - Sub-national location precision
    - Detailed actor categorization
    - Fatality estimates
    - Event notes/descriptions

    Requires API key (free for researchers).
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ACLED adapter.

        Args:
            api_key: ACLED API key. Register at https://acleddata.com/register/
        """
        self.api_key = api_key
        # TODO: Initialize HTTP client
        # TODO: Set up authentication

    def fetch_events(
        self,
        date_range: tuple[date, date],
        region: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> list[Event]:
        """
        Fetch events from ACLED API.

        TODO: Implement this method.

        Implementation steps:
        1. Build API request with date range and region filters
        2. Handle pagination (ACLED returns max 5000 records per request)
        3. Parse JSON response
        4. Convert ACLED event types to our event_type categories
        5. Map location data to country/region fields
        6. Store ACLED-specific fields (fatalities, notes) in metadata

        ACLED event types to map:
        - Battles -> "armed_conflict"
        - Explosions/Remote violence -> "armed_conflict"
        - Violence against civilians -> "violence"
        - Protests -> "protest"
        - Riots -> "civil_unrest"
        - Strategic developments -> "strategic"

        Args:
            date_range: (start_date, end_date) inclusive
            region: Region key from config
            filters: Optional filters (event_type, actor, etc.)

        Returns:
            List of Event objects
        """
        raise NotImplementedError(
            "ACLEDAdapter.fetch_events() not yet implemented. "
            "See module docstring for implementation guidance."
        )

    def get_source_metadata(self) -> SourceMetadata:
        """Return ACLED source metadata."""
        return SourceMetadata(
            name="Armed Conflict Location & Event Data Project",
            short_name="ACLED",
            description=(
                "Human-coded dataset of political violence and protest events. "
                "Provides detailed actor identification, sub-national location, "
                "and fatality estimates. Weekly updates."
            ),
            update_frequency="weekly",
            coverage_start=date(1997, 1, 1),
            geographic_coverage="Global (focus on conflict regions)",
            event_types=[
                "battles", "explosions_remote_violence",
                "violence_against_civilians", "protests",
                "riots", "strategic_developments"
            ],
            documentation_url="https://acleddata.com/resources/methodology/",
            requires_api_key=True
        )

    def validate_connection(self) -> bool:
        """
        Test ACLED API connectivity.

        TODO: Implement connection check.

        Should verify:
        1. API endpoint is reachable
        2. API key is valid
        3. Basic query returns expected response format
        """
        if not self.api_key:
            logger.warning("ACLED API key not configured")
            return False

        # TODO: Make test request to ACLED API
        raise NotImplementedError("ACLEDAdapter.validate_connection() not yet implemented")
