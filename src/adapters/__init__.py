"""
Data source adapters for fetching events from various sources.

Each adapter implements the DataSourceAdapter interface to provide
a consistent way to fetch, validate, and process event data.
"""

from src.adapters.base import DataSourceAdapter, SourceMetadata
from src.adapters.gdelt import GDELTAdapter

__all__ = ["DataSourceAdapter", "SourceMetadata", "GDELTAdapter"]
