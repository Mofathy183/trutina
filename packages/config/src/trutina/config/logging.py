"""Logging configuration settings.

Defines LoggingSettings, the typed configuration surface consumed by
trutina-observability's configure_logging(). This module only
describes shape (level, output format, sink, per-logger overrides); it
performs no logging setup itself -- trutina-config has no I/O beyond
dotenv reads and no awareness of what consumes the settings it
produces, per this package's own CONTEXT.md.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

# Starting point for logger_levels: silences noisy third-party output
# without hiding first-party logs. uvicorn.access is deliberately
# absent -- app wiring (Phase 3) disables that logger outright rather
# than merely quieting it, since it's fully replaced by our own
# structured request line.
_DEFAULT_LOGGER_LEVELS: dict[str, str] = {
    "sqlalchemy.engine": "WARNING",
    "sqlalchemy.pool": "WARNING",
    "uvicorn.error": "INFO",
    "pymongo": "WARNING",
    "asyncio": "WARNING",
    "httpx": "WARNING",
    "httpcore": "WARNING",
}


def _normalize_level(value: str) -> str:
    """Case-fold a level string and reject anything not a real logging level."""
    upper = value.strip().upper()
    if upper not in _VALID_LEVELS:
        raise ValueError(
            f"'{value}' is not a valid logging level; expected one of "
            f"{sorted(_VALID_LEVELS)}"
        )
    return upper


class LoggingSettings(BaseModel):
    """Typed configuration for the application's logging pipeline.

    A plain BaseModel, not a BaseSettings subclass, nested inside
    Settings/TestSettings the same way MongoSettings, PostgresSettings,
    and ApiSettings already are. This model has no logging behavior of
    its own -- trutina-observability's configure_logging() is the only
    consumer.

    Attributes:
        level: The root logger's minimum level. Case-insensitive on
            input; always normalized to upper-case.
        format: "json" for structured output, "console" for a
            human-readable format, or "auto" to let configure_logging()
            choose based on the app it's given.
        sink: Where log records are written. "auto" resolves per app
            (stdout for the API, a rotating file for the CLI);
            "stdout"/"stderr"/"file" force a specific destination.
        file_path: Destination path when sink resolves to a file. None
            lets configure_logging() choose a platform log directory
            (via platformdirs).
        file_max_bytes: Rotation threshold in bytes for the file sink.
            Must be positive -- a non-positive value can never trigger
            a rollover, which silently defeats rotation.
        file_backup_count: Number of rotated backups retained. Zero is
            valid (no backups kept, only the active file); negative is
            not.
        logger_levels: Per-logger level overrides, keyed by logger
            name. Overriding this from the environment replaces the
            whole mapping, not just the named keys -- there is no
            per-key merge with the defaults.
    """

    level: str = Field(default="INFO")
    format: Literal["auto", "json", "console"] = Field(default="auto")
    sink: Literal["auto", "stdout", "stderr", "file"] = Field(default="auto")
    file_path: str | None = Field(default=None)
    file_max_bytes: int = Field(default=5_000_000, gt=0)
    file_backup_count: int = Field(default=3, ge=0)
    logger_levels: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_LOGGER_LEVELS)
    )

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        return _normalize_level(value)

    @field_validator("logger_levels")
    @classmethod
    def _validate_logger_levels(cls, value: dict[str, str]) -> dict[str, str]:
        return {name: _normalize_level(lvl) for name, lvl in value.items()}
