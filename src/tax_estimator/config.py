"""
Application configuration for the Tax Estimator API.

Configuration is loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TAX_ESTIMATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API Settings
    app_name: str = "TaxEstimate API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging
    log_level: str = "INFO"

    # Rules Settings
    rules_dir: Path | None = None  # None = use default

    # Supported tax years (for validation)
    min_tax_year: int = 2020
    max_tax_year: int = 2030

    # CORS Settings
    # Default to restrictive settings - must be explicitly configured for production
    cors_origins: list[str] = []  # Empty by default, must be configured
    cors_allow_credentials: bool = False  # Disabled by default for security
    cors_allow_methods: list[str] = ["GET", "POST", "OPTIONS"]
    cors_allow_headers: list[str] = ["Content-Type", "Authorization", "X-Request-Id"]

    # Security Headers
    security_headers_enabled: bool = True
    csp_policy: str | None = None  # None = use default policy
    hsts_max_age: int = 31536000  # 1 year

    # Request Size Limit
    max_request_body_bytes: int = 1_048_576  # 1 MB

    # Rate Limiting Settings
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_trust_proxy: bool = False  # Must be explicitly enabled
    rate_limit_trusted_proxy_ips: list[str] = []  # IPs allowed to set X-Forwarded-For
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings instance with values from environment.
    """
    return Settings()
