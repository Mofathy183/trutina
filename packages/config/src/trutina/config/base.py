"""Application configuration models and settings loaders.

Defines the configuration surface used during application startup and
provides isolated settings models for production and test environments.
Configuration is loaded from environment variables and optional dotenv
files through Pydantic Settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .api import ApiSettings
from .auth import AuthSettings
from .logging import LoggingSettings
from .mongo import MongoSettings
from .postgres import PostgresSettings

Environment = Literal["production", "development", "test"]


class Settings(BaseSettings):
    """Root application configuration.

    Loads application settings from the environment using the
    ``TRUTINA_`` namespace and exposes strongly typed configuration
    objects to the rest of the application.

    Attributes:
        environment: Deployment environment. Defaults to ``production``
            so that forgetting to set it fails closed: development and
            test behavior (for example, public API docs) is always an
            explicit opt-in. Any other value is rejected at construction.
            ``TestSettings`` does not override this default; set
            ``TRUTINA_TEST_ENVIRONMENT=test`` to opt in.
    """

    model_config = SettingsConfigDict(
        env_prefix="TRUTINA_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Environment = Field(default="production")
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


class TestSettings(Settings):
    """Configuration isolated from production settings.

    Inherits the application configuration structure but loads values
    from a separate environment-variable namespace and dotenv file.
    This prevents test runs from unintentionally consuming production
    configuration.
    """

    model_config = SettingsConfigDict(
        env_prefix="TRUTINA_TEST_",
        env_file=".env.test",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance.

    Settings are loaded once and reused for the lifetime of the process
    so callers receive a consistent configuration view without repeatedly
    re-reading environment sources.

    Returns:
        The application settings instance.
    """
    return Settings()
