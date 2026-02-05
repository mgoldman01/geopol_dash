"""
Database layer for SQLite operations.

Provides connection management, schema initialization, and
query helpers for events, relationships, and trends.
"""

from src.db.database import Database
from src.db.schema import init_schema

__all__ = ["Database", "init_schema"]
