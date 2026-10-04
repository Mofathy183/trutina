"""Refresh-token contracts.

``RefreshTokenHasher`` is settled (decision P4). The record, rotation
types and ``RefreshTokenRepo`` are provisional until the M3 ADR settles
decision D1; their shape may change with it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class RefreshTokenRecord:
    """A stored refresh token, keyed by its hash.

    Attributes:
        token_hash: Output of ``RefreshTokenHasher``; excluded from ``repr``.
        user_id: Owner of the token.
        family_id: Rotation chain this token belongs to.
        family_created_at: When the chain began; anchors the absolute cap.
        issued_at: When this token was issued.
        expires_at: When this token stops being valid.
        used_at: Set when the token has been rotated.
        revoked_at: Set when the token or its family was revoked.
    """

    token_hash: str = field(repr=False)
    user_id: UUID
    family_id: UUID
    family_created_at: datetime
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


class RotationOutcome(StrEnum):
    """Result of presenting a refresh token for rotation."""

    ROTATED = "rotated"
    REUSED = "reused"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RotationResult:
    """Outcome of ``RefreshTokenRepo.rotate``.

    Attributes:
        outcome: What happened.
        previous: The presented token's record as it was before this call,
            when one exists (``ROTATED`` and ``REUSED``); ``None`` for
            ``INVALID``.
    """

    outcome: RotationOutcome
    previous: RefreshTokenRecord | None = None


class RefreshTokenRepo(ABC):
    """Persistence contract for refresh tokens.

    Adapters must stay async, hold no policy (grace windows, expiry
    arithmetic) and translate storage failures to ``AppError``.
    """

    @abstractmethod
    async def add(self, record: RefreshTokenRecord) -> None:
        """Store a newly issued token (the first of a family).

        Args:
            record: The token to store.
        """

    @abstractmethod
    async def rotate(
        self,
        *,
        presented_hash: str,
        replacement: RefreshTokenRecord,
        now: datetime,
    ) -> RotationResult:
        """Atomically consume a token and store its replacement.

        Exactly one of any number of concurrent calls with the same
        ``presented_hash`` may return ``ROTATED``; the rest return
        ``REUSED``. A token that is already used or revoked is ``REUSED``;
        one that is unknown or expired is ``INVALID``. Nothing is stored
        unless the outcome is ``ROTATED``.

        Args:
            presented_hash: Hash of the token the client presented.
            replacement: The token to store if rotation succeeds, built by
                the caller (same family, caller-computed expiry).
            now: The current time, from ``Clock``.

        Returns:
            The outcome and the presented token's prior record.
        """

    @abstractmethod
    async def revoke_family(self, family_id: UUID, *, now: datetime) -> None:
        """Revoke every token in a family.

        Args:
            family_id: The rotation chain to revoke.
            now: Revocation time.
        """

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        """Revoke every refresh token a user holds.

        Args:
            user_id: The user whose sessions end.
            now: Revocation time.
        """

    @abstractmethod
    async def purge_expired(self, *, now: datetime) -> int:
        """Delete tokens that have expired.

        Args:
            now: The current time.

        Returns:
            The number of rows removed.
        """


class RefreshTokenHasher(ABC):
    """Deterministic hash used to store and look up refresh tokens.

    Refresh tokens are 256-bit random values, so a fast unsalted hash is
    sufficient and lookup needs determinism. Never use ``PasswordHasher``
    for this.
    """

    @abstractmethod
    def hash(self, token: SecretStr) -> str:
        """Hash a refresh token.

        Args:
            token: The plaintext refresh token.

        Returns:
            The same string for the same token, every time.
        """
