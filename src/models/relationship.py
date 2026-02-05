"""
Relationship model for aggregated actor-to-actor interactions.

Relationships summarize the interactions between two actors over
a time window, enabling trend analysis and pattern detection.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Relationship(BaseModel):
    """
    Aggregated interaction data between two actors.

    Relationships are computed from events and represent the
    overall interaction pattern between an actor pair over a
    specific time window.

    Attributes:
        relationship_id: Unique identifier
        actor_a: First actor (alphabetically sorted for consistency)
        actor_b: Second actor
        interaction_count: Number of events between these actors
        avg_goldstein: Mean Goldstein score of interactions
        avg_tone: Mean tone score of interactions
        min_goldstein: Most conflictual interaction score
        max_goldstein: Most cooperative interaction score
        window_start: Beginning of aggregation window
        window_end: End of aggregation window
        event_types: Distribution of event types {type: count}
        source_event_ids: List of event IDs contributing to this relationship

    Example:
        >>> rel = Relationship(
        ...     relationship_id="usa_chn_2024_01",
        ...     actor_a="CHN",
        ...     actor_b="USA",
        ...     interaction_count=47,
        ...     avg_goldstein=-1.2,
        ...     window_start=date(2024, 1, 1),
        ...     window_end=date(2024, 1, 31)
        ... )
    """

    model_config = ConfigDict(from_attributes=True)

    relationship_id: str = Field(..., description="Unique identifier")
    actor_a: str = Field(..., description="First actor (alphabetically sorted)")
    actor_b: str = Field(..., description="Second actor")
    interaction_count: int = Field(..., ge=0, description="Number of events")
    avg_goldstein: Optional[float] = Field(None, description="Mean Goldstein score")
    avg_tone: Optional[float] = Field(None, description="Mean tone score")
    min_goldstein: Optional[float] = Field(None, description="Most conflictual score")
    max_goldstein: Optional[float] = Field(None, description="Most cooperative score")
    window_start: date = Field(..., description="Aggregation window start")
    window_end: date = Field(..., description="Aggregation window end")
    event_types: Optional[dict[str, int]] = Field(
        default_factory=dict,
        description="Event type distribution"
    )
    source_event_ids: Optional[list[str]] = Field(
        default_factory=list,
        description="Contributing event IDs for verification"
    )

    @classmethod
    def make_id(cls, actor_a: str, actor_b: str, window_start: date, window_end: date) -> str:
        """
        Generate a consistent relationship ID from components.

        Actors are sorted alphabetically to ensure the same pair
        always produces the same ID regardless of order.

        Args:
            actor_a: First actor name
            actor_b: Second actor name
            window_start: Start of time window
            window_end: End of time window

        Returns:
            Relationship ID string

        Example:
            >>> Relationship.make_id("USA", "CHN", date(2024,1,1), date(2024,1,31))
            'chn_usa_20240101_20240131'
        """
        sorted_actors = sorted([actor_a.lower(), actor_b.lower()])
        return f"{sorted_actors[0]}_{sorted_actors[1]}_{window_start:%Y%m%d}_{window_end:%Y%m%d}"
