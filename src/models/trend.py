"""
Trend model for detected patterns in event data.

Trends represent significant patterns identified through statistical
analysis of event streams, such as frequency anomalies, sentiment
shifts, or unusual actor co-occurrences.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TrendType(str, Enum):
    """Classification of detected trend patterns."""

    FREQUENCY_ANOMALY = "frequency_anomaly"      # Interaction volume above baseline
    TEMPORAL_CLUSTER = "temporal_cluster"        # Multiple related events in short window
    ACTOR_COOCCURRENCE = "actor_cooccurrence"    # Unexpected actor pairings
    SENTIMENT_SHIFT = "sentiment_shift"          # Change in average tone over time
    ESCALATION = "escalation"                    # Progressive increase in conflict intensity
    DEESCALATION = "deescalation"               # Progressive decrease in conflict intensity


class Trend(BaseModel):
    """
    A detected pattern in geopolitical event data.

    Trends are the output of analysis modules. Each trend must be
    verifiable by referencing the specific events that support it.
    This ensures transparency and allows users to inspect the
    underlying data.

    Attributes:
        trend_id: Unique identifier
        trend_type: Classification of the pattern type
        description: Human-readable description of the trend
        actors: Actors involved in this trend
        regions: Geographic regions involved
        start_date: When the pattern began
        end_date: When the pattern ended (None if ongoing)
        confidence: Statistical confidence score (0-1)
        magnitude: Strength/significance of the trend
        baseline_value: Historical baseline for comparison
        observed_value: Observed value triggering detection
        supporting_event_ids: Event IDs that evidence this trend
        methodology: Description of detection method used
        created_at: When this trend was detected

    Example:
        >>> trend = Trend(
        ...     trend_id="trend_001",
        ...     trend_type=TrendType.FREQUENCY_ANOMALY,
        ...     description="UAE-Somalia diplomatic engagement 40% above baseline",
        ...     actors=["ARE", "SOM"],
        ...     start_date=date(2024, 1, 1),
        ...     confidence=0.95,
        ...     magnitude=1.4,
        ...     baseline_value=12.0,
        ...     observed_value=16.8,
        ...     supporting_event_ids=["gdelt_123", "gdelt_456", "gdelt_789"],
        ...     methodology="30-day moving average with 2 std dev threshold"
        ... )
    """

    model_config = ConfigDict(from_attributes=True)

    trend_id: str = Field(..., description="Unique identifier")
    trend_type: TrendType = Field(..., description="Pattern classification")
    description: str = Field(..., description="Human-readable description")
    actors: list[str] = Field(default_factory=list, description="Actors involved")
    regions: list[str] = Field(default_factory=list, description="Regions involved")
    start_date: date = Field(..., description="Pattern start date")
    end_date: Optional[date] = Field(None, description="Pattern end date if concluded")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Statistical confidence")
    magnitude: Optional[float] = Field(None, description="Trend strength/significance")
    baseline_value: Optional[float] = Field(None, description="Historical baseline")
    observed_value: Optional[float] = Field(None, description="Observed value")
    supporting_event_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Event IDs supporting this trend (required for verification)"
    )
    methodology: str = Field(..., description="Detection method description")
    created_at: Optional[datetime] = Field(None, description="Detection timestamp")

    def get_deviation_pct(self) -> Optional[float]:
        """
        Calculate percentage deviation from baseline.

        Returns:
            Percentage change from baseline, or None if baseline is zero/missing

        Example:
            >>> trend.baseline_value = 10.0
            >>> trend.observed_value = 14.0
            >>> trend.get_deviation_pct()
            40.0
        """
        if self.baseline_value and self.baseline_value != 0:
            return ((self.observed_value - self.baseline_value) / self.baseline_value) * 100
        return None
