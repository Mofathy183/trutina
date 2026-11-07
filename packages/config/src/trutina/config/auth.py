"""Authentication configuration shape.

Describes the session lifetimes, re-authentication window, trusted proxy
list, password-hashing cost parameters and login-throttle limits the
authentication milestones read. This module only declares fields and shape
constraints: it performs no I/O, sets no upper bound on any lifetime, does
not relate an idle lifetime to its absolute lifetime, and does not judge
whether the hashing parameters are strong enough for production. Those
judgments belong to the code that reads the values, not to the settings.
"""

import ipaddress
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator


class AuthSettings(BaseModel):
    """Session, proxy, password-hashing and login-throttle settings.

    A plain ``BaseModel`` nested in ``Settings``, like every other
    settings group; only the root models own env-prefix and dotenv
    configuration.

    Attributes:
        session_api_idle_hours: Hours an ``api`` session may sit unused
            before it expires.
        session_api_absolute_days: Days an ``api`` session lives from
            creation, however active it is.
        session_cli_idle_days: Days a ``cli`` session may sit unused
            before it expires.
        session_cli_absolute_days: Days a ``cli`` session lives from
            creation, however active it is.
        session_touch_interval_seconds: Minimum seconds between recorded
            uses of one session, so reads do not each cause a write.
        reauth_window_minutes: Minutes after a session's last password
            check during which it counts as recently authenticated.
        trusted_proxies: Proxy addresses or CIDR networks whose forwarded
            client address may be trusted. Empty means no proxy is trusted.
        password_time_cost: Argon2id iterations.
        password_memory_cost_kib: Argon2id memory per hash, in KiB.
        password_parallelism: Argon2id lanes (threads) per hash.
        password_hash_concurrency: Maximum hashes running at once in one
            process. Peak hashing memory is roughly this value times
            ``password_memory_cost_kib``.
        login_max_failures: Failed logins allowed per client IP and email
            within the window before further attempts are throttled.
        login_window_seconds: Length of the failed-login window in
            seconds. Also the retry delay reported when throttled.

    The lifetime fields are validated only as positive integers. An idle
    lifetime longer than its absolute lifetime is accepted, because a
    session's idle expiry is capped by its absolute expiry when it is
    created or touched.

    The hashing fields are validated only for what Argon2 itself
    requires (positive values, and at least 8 KiB of memory per lane).
    Whether they are strong enough is not decided here.
    """

    session_api_idle_hours: int = Field(
        default=24,
        ge=1,
        description="Hours an api session may sit unused before it expires.",
    )
    session_api_absolute_days: int = Field(
        default=7,
        ge=1,
        description="Days an api session lives from creation.",
    )
    session_cli_idle_days: int = Field(
        default=14,
        ge=1,
        description="Days a cli session may sit unused before it expires.",
    )
    session_cli_absolute_days: int = Field(
        default=30,
        ge=1,
        description="Days a cli session lives from creation.",
    )
    session_touch_interval_seconds: int = Field(
        default=300,
        ge=1,
        description="Minimum seconds between recorded uses of one session.",
    )
    reauth_window_minutes: int = Field(
        default=30,
        ge=1,
        description="Minutes after the last password check a session counts as recent.",
    )
    trusted_proxies: list[str] = Field(
        default_factory=list,
        description="IP addresses or CIDR networks whose forwarded client address is trusted.",
    )
    password_time_cost: int = Field(
        default=3,
        ge=1,
        description="Argon2id iterations.",
    )
    password_memory_cost_kib: int = Field(
        default=65536,
        ge=8,
        description="Argon2id memory per hash, in KiB (65536 = 64 MiB).",
    )
    password_parallelism: int = Field(
        default=1,
        ge=1,
        description="Argon2id lanes per hash.",
    )
    password_hash_concurrency: int = Field(
        default=4,
        ge=1,
        description="Maximum concurrent password hashes per process.",
    )

    login_max_failures: int = Field(
        default=5,
        ge=1,
        description="Failed logins per IP and email, within the window, before throttling.",
    )
    login_window_seconds: int = Field(
        default=900,
        ge=1,
        description="Failed-login window in seconds; also the retry delay when throttled.",
    )

    @field_validator("trusted_proxies", mode="after")
    @classmethod
    def _check_trusted_proxies(cls, value: list[str]) -> list[str]:
        """Keep entries that are an IP address or CIDR network, trimmed.

        Shape only: a typo fails at construction instead of silently
        leaving a proxy untrusted. The entry is not echoed in the error.
        """
        cleaned = [entry.strip() for entry in value]
        for entry in cleaned:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                raise ValueError(
                    "trusted_proxies entries must be IP addresses or CIDR networks"
                ) from None
        return cleaned

    @model_validator(mode="after")
    def _check_memory_per_lane(self) -> Self:
        """Reject a combination Argon2 itself would refuse at hash time."""
        if self.password_memory_cost_kib < 8 * self.password_parallelism:
            raise ValueError(
                "password_memory_cost_kib must be at least 8 * password_parallelism"
            )
        return self
