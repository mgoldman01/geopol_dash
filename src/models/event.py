"""
Event model representing a single geopolitical event from any data source.

Events are the core unit of analysis. Each event is normalized from its
source format (GDELT, ACLED, etc.) into this standard structure.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Event(BaseModel):
    """
    A standardized geopolitical event from any data source.

    Attributes:
        event_id: Unique identifier (format: {source}_{source_id})
        source: Data source name (gdelt, acled, sipri, news)
        event_date: Date the event occurred
        event_type: High-level event category
        actors: List of actor names involved (countries, organizations, individuals)
        location_country: ISO 3166-1 alpha-3 country code
        location_region: Sub-national region if available
        cameo_code: CAMEO event code (e.g., "010" for Make Statement)
        goldstein_score: Goldstein conflict-cooperation score (-10 to +10)
        tone: Sentiment/tone score from source (-100 to +100 for GDELT)
        source_url: URL to original source article/document
        headline: Event headline or summary
        excerpt: Brief excerpt from source text
        metadata: Source-specific additional fields as JSON
        created_at: When this record was added to our database

    Example:
        >>> event = Event(
        ...     event_id="gdelt_123456",
        ...     source="gdelt",
        ...     event_date=date(2024, 1, 15),
        ...     event_type="diplomatic_cooperation",
        ...     actors=["USA", "CHN"],
        ...     location_country="CHE",
        ...     cameo_code="040",
        ...     goldstein_score=1.0,
        ...     headline="US and China hold trade talks in Geneva"
        ... )
    """

    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(..., description="Unique identifier: {source}_{source_id}")
    source: str = Field(..., description="Data source: gdelt, acled, sipri, news")
    event_date: date = Field(..., description="Date the event occurred")
    event_type: str = Field(..., description="High-level event category")
    actors: list[str] = Field(default_factory=list, description="Actors involved")
    location_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-3 code")
    location_region: Optional[str] = Field(None, description="Sub-national region")
    cameo_code: Optional[str] = Field(None, description="CAMEO event code")
    goldstein_score: Optional[float] = Field(
        None,
        ge=-10.0,
        le=10.0,
        description="Goldstein conflict-cooperation score"
    )
    tone: Optional[float] = Field(None, description="Sentiment score from source")
    source_url: Optional[str] = Field(None, description="URL to original source")
    headline: Optional[str] = Field(None, description="Event headline")
    excerpt: Optional[str] = Field(None, description="Brief excerpt from source")
    metadata: Optional[dict] = Field(default_factory=dict, description="Source-specific fields")
    created_at: Optional[datetime] = Field(None, description="Record creation time")


class EventFilter(BaseModel):
    """
    Filter parameters for querying events.

    Used by the Event Browser to filter results by date range,
    actors, event types, locations, and sources.

    Attributes:
        start_date: Beginning of date range (inclusive)
        end_date: End of date range (inclusive)
        actors: Filter to events involving any of these actors
        event_types: Filter to these event type categories
        countries: Filter to events in these countries (ISO codes)
        sources: Filter to events from these data sources
        min_goldstein: Minimum Goldstein score
        max_goldstein: Maximum Goldstein score
        limit: Maximum number of results to return
        offset: Number of results to skip (for pagination)

    Example:
        >>> filter = EventFilter(
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 1, 31),
        ...     actors=["USA", "IRN"],
        ...     countries=["IRQ", "SYR"]
        ... )
    """

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    actors: Optional[list[str]] = None
    event_types: Optional[list[str]] = None
    countries: Optional[list[str]] = None
    sources: Optional[list[str]] = None
    min_goldstein: Optional[float] = Field(None, ge=-10.0, le=10.0)
    max_goldstein: Optional[float] = Field(None, ge=-10.0, le=10.0)
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
