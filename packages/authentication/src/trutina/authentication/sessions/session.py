"""Session contracts.

Defines the client kinds, the stored session record, the result of
validating a session, and the persistence contract. Frozen in M3.1 under
ADR 0001 and ADR 0002; no adapter or service exists yet. Part of
``trutina-authentication``; must not import from ``trutina.core``, storage
packages, ``trutina.config`` or presentation frameworks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from trutina.authentication.identity import AccessState


class ClientKind(StrEnum):
    """The kind of client a session was issued to.

    A session is valid only for the kind it was issued for, so a long-lived
    operator token cannot be replayed through the network API. The two
    values are the single source for any storage-level constraint.
    """

    API = "api"
    CLI = "cli"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """A stored session, keyed by the hash of its token.

    The raw token is never part of the record. All timestamps are
    timezone-aware UTC.

    Attributes:
        token_hash: Output of ``SessionTokenHasher``; excluded from ``repr``.
        user_id: Owner of the session.
        client_kind: The kind of client the session was issued to.
        created_at: When the session was created.
        last_used_at: When the session was last recorded as used.
        authenticated_at: When the user last proved their password in this
            session. Set at login and again at re-authentication.
        idle_expires_at: When the session expires if it stays unused.
        absolute_expires_at: When the session expires regardless of use.
            Fixed at creation.
        revoked_at: Set when the session was revoked.
    """

    token_hash: str = field(repr=False)
    user_id: UUID
    client_kind: ClientKind
    created_at: datetime
    last_used_at: datetime
    authenticated_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ValidSession:
    """A session that may be used right now, with its user's access state.

    Attributes:
        session: The stored session.
        access: The owning user's current access state. Because a session
            of an inactive user is never valid, ``access.is_active`` is
            always true here; the field exists so that adding a role later
            extends the same lookup.
    """

    session: SessionRecord
    access: AccessState


class SessionRepo(ABC):
    """Persistence contract for sessions.

    Adapters must stay async, hold no policy (lifetimes, when a touch is
    due, retention) and translate storage failures to ``AppError``
    (``STORAGE_UNAVAILABLE`` or ``STORAGE_TIMEOUT``) before they cross the
    boundary. No method raises a domain error: a miss returns ``None`` or is
    a no-op. Every method uses its own short database session and holds no
    connection while any other work happens (ADR 0002).

    All timestamps are timezone-aware UTC supplied by the caller from
    ``Clock``. They must never be compared with the accounting domain's
    naive posting dates; a naive datetime is a caller bug and is not
    guarded.
    """

    @abstractmethod
    async def create(self, record: SessionRecord) -> None:
        """Store a new session.

        Token hashes come from 256-bit random tokens, so a duplicate hash
        is a defect, not a domain outcome; the contract defines no behavior
        for it.

        Args:
            record: The session to store. It carries only the token's hash.
        """

    @abstractmethod
    async def get_valid(
        self,
        token_hash: str,
        *,
        client_kind: ClientKind,
        now: datetime,
    ) -> ValidSession | None:
        """Look up a session that may be used right now.

        A session is valid only when all of these hold: its hash matches,
        it was issued for ``client_kind``, it is not revoked, ``now`` is
        strictly before both its idle and absolute expiry, and its user
        exists and is active. Every other case returns the same ``None``,
        so a caller cannot tell why a token failed. This call never writes;
        recording use is a separate ``touch``.

        Args:
            token_hash: Hash of the presented token.
            client_kind: The kind of client presenting it. Required, so no
                caller can skip the check.
            now: The current time, from ``Clock``.

        Returns:
            The session and the user's access state, or ``None``.
        """

    @abstractmethod
    async def touch(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
    ) -> None:
        """Record use of a live session.

        Sets ``last_used_at`` to ``now`` and ``idle_expires_at`` to the
        given value, never moving either earlier than its stored value, so
        concurrent touches cannot shorten a session. The caller decides
        whether a touch is due and computes ``idle_expires_at``. An unknown
        hash or a revoked session is a no-op.

        Args:
            token_hash: Hash of the session's token.
            now: The current time.
            idle_expires_at: The new idle expiry, chosen by the caller.
        """

    @abstractmethod
    async def mark_reauthenticated(self, token_hash: str, *, now: datetime) -> None:
        """Record that the user just proved their password in this session.

        Sets ``authenticated_at`` to ``now``, never earlier than its stored
        value. The token is not rotated. An unknown hash or a revoked
        session is a no-op.

        Args:
            token_hash: Hash of the session's token.
            now: When the password was verified.
        """

    @abstractmethod
    async def revoke(self, token_hash: str, *, now: datetime) -> None:
        """Revoke one session.

        Idempotent: a session that is already revoked keeps its first
        ``revoked_at``, and an unknown hash is a no-op, so logout never
        fails on a repeat.

        Args:
            token_hash: Hash of the session's token.
            now: Revocation time.
        """

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        """Revoke every session a user holds that is not already revoked.

        Args:
            user_id: The user whose sessions end.
            now: Revocation time.
        """

    @abstractmethod
    async def purge_before(self, cutoff: datetime) -> int:
        """Delete sessions that died before a cutoff.

        A session dies at the earliest of its ``revoked_at`` (when set),
        ``idle_expires_at`` and ``absolute_expires_at``. A session whose
        death is strictly earlier than ``cutoff`` is removed; one that died
        exactly at the cutoff is kept, and a session still live at the
        cutoff is never removed. The caller chooses the cutoff (retention
        is policy).

        Args:
            cutoff: The retention boundary.

        Returns:
            The number of rows removed.
        """
