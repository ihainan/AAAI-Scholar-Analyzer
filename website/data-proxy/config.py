"""
Configuration management for data-proxy service.
Loads settings from .env file using pydantic-settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 37803

    # Cache Configuration
    cache_dir: Path = Path("./cache")
    aminer_cache_ttl: int = 1296000  # 15 days in seconds
    avatar_cache_ttl: int = 31536000  # 365 days in seconds (effectively permanent)

    # Firecrawl Configuration
    firecrawl_api_url: str = "https://firecrawl.ihainan.me/v1"
    firecrawl_timeout: float = 180.0  # Firecrawl can be slow, allow 3 minutes

    # HTTP Client Configuration
    # Note: Use integer in .env.prod (e.g., 30) to avoid uv parsing issues
    http_timeout: float = 30.0

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
    def aminer_cache_dir(self) -> Path:
        """Get AMiner cache directory path."""
        return self.cache_dir / "aminer"

    @property
    def avatar_cache_dir(self) -> Path:
        """Get avatar cache directory path."""
        return self.cache_dir / "avatars"


# Global settings instance
settings = Settings()

# Ensure cache directories exist
settings.aminer_cache_dir.mkdir(parents=True, exist_ok=True)
settings.avatar_cache_dir.mkdir(parents=True, exist_ok=True)
