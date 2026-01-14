"""
Configuration management for backend service.
Loads settings from .env file using pydantic-settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 37801

    # Data Directories
    data_dir: Path = Path("../../data")
    config_dir: Path = Path("../../config")

    # Cache Configuration
    avatar_cache_dir: Path = Path("./avatar_cache")
    avatar_fail_cache_ttl: int = 3600  # 1 hour in seconds
    cache_ttl_seconds: int = 300        # 5 minutes for JSON cache

    # HTTP Client Configuration
    http_timeout: float = 5.0

    # CORS Configuration
    cors_origins: str = "*"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def aminer_scholars_dir(self) -> Path:
        """Get AMiner scholars data directory."""
        return self.data_dir / "aminer" / "scholars"

    @property
    def aminer_papers_dir(self) -> Path:
        """Get AMiner papers data directory."""
        return self.data_dir / "aminer" / "papers"

    @property
    def enriched_scholars_dir(self) -> Path:
        """Get enriched scholars data directory."""
        return self.data_dir / "enriched" / "scholars"

    @property
    def labels_config_path(self) -> Path:
        """Get labels configuration file path."""
        return self.config_dir / "labels.json"


# Global settings instance
settings = Settings()

# Ensure cache directory exists
settings.avatar_cache_dir.mkdir(parents=True, exist_ok=True)
