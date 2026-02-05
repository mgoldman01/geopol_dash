"""
Configuration management for the geopolitical intelligence platform.

Loads configuration from YAML file with environment variable substitution
and provides validated access to configuration values throughout the app.

Usage:
    from src.config import get_config, Config

    config = get_config()
    print(config.database.path)
    print(config.regions["middle_east"].countries)
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default config file path
DEFAULT_CONFIG_PATH = Path("config.yaml")
LOCAL_CONFIG_PATH = Path("config.local.yaml")


@dataclass
class GDELTConfig:
    """GDELT adapter configuration."""
    timeout_seconds: int = 30
    max_events_per_day: int = 10000


@dataclass
class ACLEDConfig:
    """ACLED adapter configuration."""
    api_key: Optional[str] = None
    api_url: str = "https://api.acleddata.com/acled/read"


@dataclass
class SIPRIConfig:
    """SIPRI adapter configuration."""
    data_directory: str = "data/sipri"


@dataclass
class NewsConfig:
    """News scraper configuration."""
    anthropic_api_key: Optional[str] = None
    rss_feeds: list[str] = field(default_factory=list)
    fetch_interval_minutes: int = 60


@dataclass
class DataSourcesConfig:
    """Data sources configuration."""
    enabled: list[str] = field(default_factory=lambda: ["gdelt"])
    gdelt: GDELTConfig = field(default_factory=GDELTConfig)
    acled: ACLEDConfig = field(default_factory=ACLEDConfig)
    sipri: SIPRIConfig = field(default_factory=SIPRIConfig)
    news: NewsConfig = field(default_factory=NewsConfig)


@dataclass
class RegionDefinition:
    """Definition of a geographic region."""
    name: str
    countries: list[str]


@dataclass
class GoldsteinConfig:
    """Goldstein score analysis configuration."""
    weight_by_mentions: bool = True
    min_mentions: int = 2


@dataclass
class TemporalClusteringConfig:
    """Temporal clustering configuration."""
    max_gap_days: int = 3
    min_cluster_size: int = 3


@dataclass
class AnalysisConfig:
    """Analysis parameters configuration."""
    moving_average_window_days: int = 30
    baseline_period_days: int = 90
    anomaly_threshold_std: float = 2.0
    min_events_for_trend: int = 5
    goldstein: GoldsteinConfig = field(default_factory=GoldsteinConfig)
    temporal_clustering: TemporalClusteringConfig = field(default_factory=TemporalClusteringConfig)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "data/geopol.db"
    wal_mode: bool = True


@dataclass
class DashboardConfig:
    """Dashboard settings."""
    default_date_range_days: int = 30
    max_display_events: int = 500
    status_refresh_seconds: int = 60
    default_region: str = "middle_east"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = "logs/geopol.log"
    max_file_size_mb: int = 10
    backup_count: int = 5


@dataclass
class Config:
    """
    Main configuration container.

    Holds all configuration sections with validated defaults.
    Access configuration values via attributes:

        config = get_config()
        config.database.path
        config.regions["middle_east"].countries
        config.analysis.moving_average_window_days

    Attributes:
        data_sources: Data source adapter settings
        regions: Geographic region definitions
        analysis: Analysis algorithm parameters
        api_keys: API keys for external services
        database: Database connection settings
        dashboard: Dashboard display settings
        logging: Logging configuration
    """
    data_sources: DataSourcesConfig = field(default_factory=DataSourcesConfig)
    regions: dict[str, RegionDefinition] = field(default_factory=dict)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    api_keys: dict[str, Optional[str]] = field(default_factory=dict)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def get_region_countries(self, region_key: str) -> list[str]:
        """
        Get list of country codes for a region.

        Args:
            region_key: Region identifier (e.g., "middle_east")

        Returns:
            List of ISO 3166-1 alpha-3 country codes

        Raises:
            KeyError: If region not found
        """
        if region_key not in self.regions:
            raise KeyError(f"Unknown region: {region_key}. Available: {list(self.regions.keys())}")
        return self.regions[region_key].countries

    def is_source_enabled(self, source_name: str) -> bool:
        """Check if a data source is enabled."""
        return source_name in self.data_sources.enabled


# Global config instance (singleton pattern)
_config: Optional[Config] = None


def get_config(reload: bool = False) -> Config:
    """
    Get the global configuration instance.

    Loads configuration on first call, returns cached instance thereafter.
    Use reload=True to force re-reading the config file.

    Args:
        reload: If True, reload configuration from file

    Returns:
        Config instance

    Example:
        >>> config = get_config()
        >>> print(config.database.path)
        data/geopol.db
    """
    global _config
    if _config is None or reload:
        _config = load_config()
    return _config


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from YAML file.

    Attempts to load config.local.yaml first (for local overrides),
    then falls back to config.yaml.

    Environment variables in the format ${VAR_NAME} are substituted.

    Args:
        config_path: Optional specific config file path

    Returns:
        Populated Config instance

    Raises:
        FileNotFoundError: If no config file found
        yaml.YAMLError: If config file is invalid YAML
    """
    # Determine which config file to load
    if config_path:
        paths_to_try = [Path(config_path)]
    else:
        paths_to_try = [LOCAL_CONFIG_PATH, DEFAULT_CONFIG_PATH]

    config_file = None
    for path in paths_to_try:
        if path.exists():
            config_file = path
            break

    if config_file is None:
        logger.warning(f"No config file found at {paths_to_try}, using defaults")
        return Config()

    logger.info(f"Loading configuration from {config_file}")

    with open(config_file, "r") as f:
        raw_content = f.read()

    # Substitute environment variables
    content = _substitute_env_vars(raw_content)

    # Parse YAML
    data = yaml.safe_load(content) or {}

    # Build config object
    return _parse_config(data)


def _substitute_env_vars(content: str) -> str:
    """
    Substitute ${VAR_NAME} patterns with environment variable values.

    Args:
        content: String containing ${VAR_NAME} patterns

    Returns:
        String with environment variables substituted

    Example:
        >>> os.environ["MY_KEY"] = "secret123"
        >>> _substitute_env_vars("api_key: ${MY_KEY}")
        'api_key: secret123'
    """
    pattern = r'\$\{([^}]+)\}'

    def replace(match):
        var_name = match.group(1)
        value = os.environ.get(var_name, "")
        if not value:
            logger.debug(f"Environment variable {var_name} not set")
        return value

    return re.sub(pattern, replace, content)


def _parse_config(data: dict) -> Config:
    """
    Parse raw config dict into Config dataclass.

    Args:
        data: Dictionary from YAML parsing

    Returns:
        Populated Config instance
    """
    config = Config()

    # Parse data sources
    if "data_sources" in data:
        ds = data["data_sources"]
        config.data_sources.enabled = ds.get("enabled", ["gdelt"])

        if "gdelt" in ds:
            config.data_sources.gdelt = GDELTConfig(**ds["gdelt"])
        if "acled" in ds:
            config.data_sources.acled = ACLEDConfig(**ds["acled"])
        if "sipri" in ds:
            config.data_sources.sipri = SIPRIConfig(**ds["sipri"])
        if "news" in ds:
            config.data_sources.news = NewsConfig(**ds["news"])

    # Parse regions
    if "regions" in data:
        for key, region_data in data["regions"].items():
            config.regions[key] = RegionDefinition(
                name=region_data.get("name", key),
                countries=region_data.get("countries", [])
            )

    # Parse analysis
    if "analysis" in data:
        a = data["analysis"]
        config.analysis.moving_average_window_days = a.get("moving_average_window_days", 30)
        config.analysis.baseline_period_days = a.get("baseline_period_days", 90)
        config.analysis.anomaly_threshold_std = a.get("anomaly_threshold_std", 2.0)
        config.analysis.min_events_for_trend = a.get("min_events_for_trend", 5)

        if "goldstein" in a:
            config.analysis.goldstein = GoldsteinConfig(**a["goldstein"])
        if "temporal_clustering" in a:
            config.analysis.temporal_clustering = TemporalClusteringConfig(**a["temporal_clustering"])

    # Parse API keys
    if "api_keys" in data:
        config.api_keys = data["api_keys"]

    # Parse database
    if "database" in data:
        config.database = DatabaseConfig(**data["database"])

    # Parse dashboard
    if "dashboard" in data:
        config.dashboard = DashboardConfig(**data["dashboard"])

    # Parse logging
    if "logging" in data:
        config.logging = LoggingConfig(**data["logging"])

    return config


def setup_logging(config: Optional[Config] = None) -> None:
    """
    Configure logging based on config settings.

    Sets up console and optional file logging with rotation.

    Args:
        config: Config instance, or None to use global config
    """
    if config is None:
        config = get_config()

    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if config.logging.file:
        from logging.handlers import RotatingFileHandler

        log_path = Path(config.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=config.logging.max_file_size_mb * 1024 * 1024,
            backupCount=config.logging.backup_count
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(console_format)
        root_logger.addHandler(file_handler)

    logger.info(f"Logging configured: level={config.logging.level}, file={config.logging.file}")
