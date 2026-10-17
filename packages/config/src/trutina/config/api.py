"""Application configuration models and settings loaders.

Defines the configuration surface used during application startup and
provides isolated settings models for production and test environments.
Configuration is loaded from environment variables and optional dotenv
files through Pydantic Settings.
"""

from pydantic import BaseModel, Field


class ApiSettings(BaseModel):
    """API-layer configuration, independent of DB/domain settings."""

    title: str = Field(
        default="Trutina API",
        description="Title displayed in the OpenAPI schema.",
    )
    version: str = Field(
        default="0.1.0",
        description="Current API version.",
    )
    description: str = Field(
        default="REST API for the Trutina accounting engine.",
        description="Description displayed in the OpenAPI schema.",
    )

    host: str = Field(
        default="127.0.0.1",
        description="Host interface the API server binds to.",
    )
    port: int = Field(
        default=8000,
        description="Port the API server listens on.",
    )
    reload: bool = Field(
        default=False,
        description="Enable uvicorn's auto-reload. Intended for local development only.",
    )
