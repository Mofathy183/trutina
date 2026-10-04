"""Authentication configuration shape.

Describes the signing-key material the authentication milestones will
read. This module only declares fields: it performs no I/O, never checks
that keys are present, long enough or not a placeholder, and does not
verify that ``active_kid`` names a configured key. Those checks run at
API startup (decision D6), not on the root ``Settings``, so Alembic, the
CLI and tooling can start without keys.
"""

from pydantic import BaseModel, Field, SecretStr, field_validator


class AuthSettings(BaseModel):
    """Signing-key settings for access tokens.

    A plain ``BaseModel`` nested in ``Settings``, like every other
    settings group; only the root models own env-prefix and dotenv
    configuration.

    Attributes:
        signing_keys: Key id (``kid``) to secret. No default: an empty
            mapping means "no keys configured". Set one entry per key as
            ``TRUTINA_AUTH__SIGNING_KEYS__<kid>``.
        active_kid: The ``kid`` new tokens are signed with. ``None`` until
            configured.

    Key ids are case-folded to lower case. pydantic-settings lower-cases
    the env-var-derived dict keys, so ``active_kid`` is folded the same
    way; otherwise ``ACTIVE_KID=K1`` could never match the key loaded
    from ``SIGNING_KEYS__K1``. Do not use ``__`` inside a kid.
    """

    signing_keys: dict[str, SecretStr] = Field(
        default_factory=dict,
        description="Key id to signing secret. Empty means no keys configured.",
    )
    active_kid: str | None = Field(
        default=None,
        description="Key id used to sign new tokens.",
    )

    @field_validator("signing_keys", mode="after")
    @classmethod
    def _fold_key_ids(cls, value: dict[str, SecretStr]) -> dict[str, SecretStr]:
        return {kid.casefold(): secret for kid, secret in value.items()}

    @field_validator("active_kid", mode="after")
    @classmethod
    def _fold_active_kid(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None
