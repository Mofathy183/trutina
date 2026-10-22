"""Authentication configuration shape.

Describes the signing-key material and the password-hashing cost
parameters the authentication milestones read. This module only declares
fields and shape constraints: it performs no I/O, never checks that keys
are present, long enough or not a placeholder, does not verify that
``active_kid`` names a configured key, and does not judge whether the
hashing parameters are strong enough for production. Those checks run at
API startup (decision D6), not on the root ``Settings``, so Alembic, the
CLI and tooling can start without keys.
"""

from typing import Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class AuthSettings(BaseModel):
    """Signing-key and password-hashing settings.

    A plain ``BaseModel`` nested in ``Settings``, like every other
    settings group; only the root models own env-prefix and dotenv
    configuration.

    Attributes:
        signing_keys: Key id (``kid``) to secret. No default: an empty
            mapping means "no keys configured". Set one entry per key as
            ``TRUTINA_AUTH__SIGNING_KEYS__<kid>``.
        active_kid: The ``kid`` new tokens are signed with. ``None`` until
            configured.
        password_time_cost: Argon2id iterations.
        password_memory_cost_kib: Argon2id memory per hash, in KiB.
        password_parallelism: Argon2id lanes (threads) per hash.
        password_hash_concurrency: Maximum hashes running at once in one
            process. Peak hashing memory is roughly this value times
            ``password_memory_cost_kib``.

    Key ids are case-folded to lower case. pydantic-settings lower-cases
    the env-var-derived dict keys, so ``active_kid`` is folded the same
    way; otherwise ``ACTIVE_KID=K1`` could never match the key loaded
    from ``SIGNING_KEYS__K1``. Do not use ``__`` inside a kid.

    The hashing fields are validated only for what Argon2 itself
    requires (positive values, and at least 8 KiB of memory per lane).
    Whether they are strong enough is not decided here.
    """

    signing_keys: dict[str, SecretStr] = Field(
        default_factory=dict,
        description="Key id to signing secret. Empty means no keys configured.",
    )
    active_kid: str | None = Field(
        default=None,
        description="Key id used to sign new tokens.",
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

    @field_validator("signing_keys", mode="after")
    @classmethod
    def _fold_key_ids(cls, value: dict[str, SecretStr]) -> dict[str, SecretStr]:
        return {kid.casefold(): secret for kid, secret in value.items()}

    @field_validator("active_kid", mode="after")
    @classmethod
    def _fold_active_kid(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None

    @model_validator(mode="after")
    def _check_memory_per_lane(self) -> Self:
        """Reject a combination Argon2 itself would refuse at hash time."""
        if self.password_memory_cost_kib < 8 * self.password_parallelism:
            raise ValueError(
                "password_memory_cost_kib must be at least 8 * password_parallelism"
            )
        return self
