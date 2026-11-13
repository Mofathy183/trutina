"""Session service use case.

Creates, validates, ends and re-authenticates the opaque, database-backed
sessions of ADR 0001 and ADR 0002. All session policy lives here: lifetimes
per client kind, when a use is recorded, the step-up window and the
retention of dead rows. The repository holds none of it. Depends only on
the session, user, authenticator, token-hasher, clock and event-sink
contracts, so it has no storage, web or CLI knowledge. No route or command
uses it yet.
"""

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import SecretStr
from trutina.authentication.credentials.login import Authenticator
from trutina.authentication.credentials.users import UserRepo
from trutina.authentication.shared import (
    AuthEvent,
    AuthEventSink,
    Clock,
    NoOpAuthEventSink,
)
from trutina.shared.errors import AppError, ErrorCode

from .hasher import SessionTokenHasher
from .session import ClientKind, SessionRecord, SessionRepo, ValidSession

MAX_SESSION_TOKEN_LENGTH = 128
"""Longest presented token, in characters, that is looked up at all.

A real token is 43 characters. Anything longer cannot be one, so it is
rejected before hashing or storage is touched.
"""

_TOKEN_BYTES = 32  # 256 bits, as ADR 0001 requires

_CREATED_EVENT = "auth.session_created"
_REVOKED_EVENT = "auth.session_revoked"
_REAUTHENTICATED_EVENT = "auth.session_reauthenticated"
_ALL_KINDS = "all"


def _new_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


@dataclass(frozen=True, slots=True)
class SessionLifetime:
    """How long a session of one client kind lives.

    Attributes:
        idle: How long it may sit unused before it expires.
        absolute: How long it lives from creation, however active it is.
            An idle value above this one is accepted: idle expiry is
            capped at the absolute expiry.
    """

    idle: timedelta
    absolute: timedelta

    def __post_init__(self) -> None:
        if self.idle <= timedelta(0) or self.absolute <= timedelta(0):
            raise ValueError("session lifetimes must be positive")


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """What a successful login returns to its caller.

    This is the only place the raw token ever exists after login; the
    store keeps its hash. ``SecretStr`` keeps it out of ``repr``.

    Attributes:
        token: The raw session token. Show it to the client once.
        subject_id: The authenticated user.
        client_kind: The kind of client the session was issued to.
        absolute_expires_at: When the session ends regardless of use.
    """

    token: SecretStr
    subject_id: UUID
    client_kind: ClientKind
    absolute_expires_at: datetime


class SessionService:
    """Issues, validates, re-authenticates and ends sessions.

    Every presented-token failure (blank, oversized, unknown, revoked,
    expired, issued to the other client kind, or owned by a disabled user)
    raises the same ``AUTH_TOKEN_INVALID`` with an empty context, so a
    caller cannot tell which it was. A session is valid only for the
    client kind it was issued for.

    The service holds no connection while it works: every repository call
    is its own short borrow, and password verification (slow hashing)
    never runs while one is held (ADR 0002). A use is recorded with a
    separate ``touch`` only when the touch interval has passed.

    Step-up is a fixed window counted from ``authenticated_at``, which only
    login and re-authentication set. Ordinary use never extends it.
    """

    def __init__(
        self,
        *,
        sessions: SessionRepo,
        users: UserRepo,
        authenticator: Authenticator,
        hasher: SessionTokenHasher,
        clock: Clock,
        lifetimes: Mapping[ClientKind, SessionLifetime],
        touch_interval: timedelta,
        reauth_window: timedelta,
        purge_retention: timedelta,
        events: AuthEventSink | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        """Wire the service to its collaborators and policy.

        Policy arrives as plain values because this package does not import
        ``trutina-config``; the composition root maps ``AuthSettings`` onto
        them.

        Args:
            sessions: Where sessions are stored.
            users: Where the session's own user is read for re-authentication.
            authenticator: Checks a password. The composition root passes
                ``ThrottledAuthenticator``, so login and re-authentication
                are both throttled.
            hasher: Hashes tokens for storage and lookup.
            clock: Supplies timezone-aware UTC times.
            lifetimes: Lifetime for every ``ClientKind``.
            touch_interval: Minimum time between recorded uses.
            reauth_window: How long after a password check a session counts
                as recently authenticated.
            purge_retention: How long a dead session is kept before login
                deletes it.
            events: Receives session events. Defaults to a sink that
                discards every event.
            token_factory: Produces a new raw token. Defaults to 256 bits
                from a CSPRNG; replace it only in tests.

        Raises:
            ValueError: If a kind has no lifetime, or an interval, window
                or retention is not positive.
        """
        missing = [kind.value for kind in ClientKind if kind not in lifetimes]
        if missing:
            raise ValueError(f"missing session lifetime for: {', '.join(missing)}")
        for value in (touch_interval, reauth_window, purge_retention):
            if value <= timedelta(0):
                raise ValueError("intervals and windows must be positive")
        self._sessions = sessions
        self._users = users
        self._authenticator = authenticator
        self._hasher = hasher
        self._clock = clock
        self._lifetimes = dict(lifetimes)
        self._touch_interval = touch_interval
        self._reauth_window = reauth_window
        self._purge_retention = purge_retention
        self._events = events if events is not None else NoOpAuthEventSink()
        self._new_token = token_factory if token_factory is not None else _new_token

    async def login(
        self,
        *,
        email: str,
        password: SecretStr,
        client_ip: str | None,
        client_kind: ClientKind,
    ) -> IssuedSession:
        """Authenticate and open a new session.

        A session is created only after the authenticator succeeds. Dead
        sessions older than the retention window are then deleted (one
        unbounded call, made before the insert so a failed purge leaves no
        orphan row) and the new session is stored with ``authenticated_at``
        and ``last_used_at`` at now and ``idle_expires_at`` capped at the
        absolute expiry.

        Args:
            email: The login email, as typed.
            password: The plaintext password, as typed.
            client_ip: Resolved client address, or ``None`` if unknown.
            client_kind: The kind of client logging in.

        Returns:
            The issued session, carrying the raw token once.

        Raises:
            AppError: Whatever the authenticator raises, unchanged:
                AUTH_INVALID_CREDENTIALS or AUTH_THROTTLED. No session is
                created and no event is emitted. STORAGE_UNAVAILABLE or
                STORAGE_TIMEOUT from the session store, and UNKNOWN_ERROR
                if the store rejects the insert, propagate unchanged.
        """
        identity = await self._authenticator.authenticate(
            email=email, password=password, client_ip=client_ip
        )
        now = self._clock.now()
        lifetime = self._lifetimes[client_kind]
        absolute = now + lifetime.absolute
        token = SecretStr(self._new_token())

        await self._sessions.purge_before(now - self._purge_retention)
        await self._sessions.create(
            SessionRecord(
                token_hash=self._hasher.hash(token),
                user_id=identity.subject_id,
                client_kind=client_kind,
                created_at=now,
                last_used_at=now,
                authenticated_at=now,
                idle_expires_at=min(now + lifetime.idle, absolute),
                absolute_expires_at=absolute,
            )
        )
        self._emit(_CREATED_EVENT, identity.subject_id, client_kind.value)
        return IssuedSession(
            token=token,
            subject_id=identity.subject_id,
            client_kind=client_kind,
            absolute_expires_at=absolute,
        )

    async def validate(
        self, token: SecretStr, *, client_kind: ClientKind
    ) -> ValidSession:
        """Resolve a presented token to a live session.

        Records a use when the touch interval has passed. The returned
        session is the one read, before that touch.

        Args:
            token: The presented raw token.
            client_kind: The kind of client presenting it.

        Returns:
            The session and its user's access state.

        Raises:
            AppError: AUTH_TOKEN_INVALID, with an empty context, for any
                token that is not valid right now for this client kind.
                Storage errors propagate unchanged.
        """
        _, valid = await self._require(token, client_kind)
        return valid

    def require_recent_auth(self, session: ValidSession) -> None:
        """Insist that the user proved their password recently.

        The window is exclusive: a session whose last password check is
        exactly the window old is no longer recent. Applies to the ``api``
        kind only; the CLI never calls it (ADR 0002).

        Args:
            session: A session returned by ``validate``.

        Raises:
            AppError: AUTH_REAUTH_REQUIRED, with an empty context.
        """
        age = self._clock.now() - session.session.authenticated_at
        if age >= self._reauth_window:
            raise _reauth_required()

    async def reauthenticate(
        self,
        token: SecretStr,
        *,
        client_kind: ClientKind,
        password: SecretStr,
        client_ip: str | None,
    ) -> None:
        """Refresh a session's password check without rotating its token.

        The identity comes from the session, never from the caller: the
        password is checked against the session's own user, through the
        authenticator and so through the throttle. The user is read and
        the connection released before the password is verified, and a
        second short borrow writes ``authenticated_at``. A wrong password
        leaves the session valid and unchanged.

        Args:
            token: The presented raw token.
            client_kind: The kind of client presenting it.
            password: The plaintext password, as typed.
            client_ip: Resolved client address, or ``None`` if unknown.

        Raises:
            AppError: AUTH_TOKEN_INVALID for a token that is not valid
                (the password is not checked). AUTH_INVALID_CREDENTIALS or
                AUTH_THROTTLED from the authenticator, unchanged.
        """
        token_hash, valid = await self._require(token, client_kind)
        user = await self._users.get_by_id(valid.session.user_id)
        if user is None:
            raise _token_invalid()
        await self._authenticator.authenticate(
            email=user.email, password=password, client_ip=client_ip
        )
        await self._sessions.mark_reauthenticated(token_hash, now=self._clock.now())
        self._emit(_REAUTHENTICATED_EVENT, user.id, client_kind.value)

    async def logout(self, token: SecretStr, *, client_kind: ClientKind) -> None:
        """End the session a token belongs to.

        Idempotent: a token that is unknown, already revoked, expired or
        issued to the other client kind is a silent no-op with no event, so
        a repeated logout never fails.

        Args:
            token: The presented raw token.
            client_kind: The kind of client logging out.
        """
        found = await self._find(token, client_kind)
        if found is None:
            return
        token_hash, valid = found
        await self._sessions.revoke(token_hash, now=self._clock.now())
        self._emit(_REVOKED_EVENT, valid.session.user_id, client_kind.value)

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """End every session a user holds, of both client kinds.

        For password change and deactivation. Nothing calls it yet: no
        change-password route exists and deactivation does not go through
        a service.

        Args:
            user_id: The user whose sessions end.
        """
        await self._sessions.revoke_all_for_user(user_id, now=self._clock.now())
        self._emit(_REVOKED_EVENT, user_id, _ALL_KINDS)

    async def _find(
        self, token: SecretStr, client_kind: ClientKind
    ) -> tuple[str, ValidSession] | None:
        raw = token.get_secret_value()
        if not raw or len(raw) > MAX_SESSION_TOKEN_LENGTH:
            return None
        token_hash = self._hasher.hash(token)
        valid = await self._sessions.get_valid(
            token_hash, client_kind=client_kind, now=self._clock.now()
        )
        return None if valid is None else (token_hash, valid)

    async def _require(
        self, token: SecretStr, client_kind: ClientKind
    ) -> tuple[str, ValidSession]:
        found = await self._find(token, client_kind)
        if found is None:
            raise _token_invalid()
        token_hash, valid = found
        await self._touch_if_due(token_hash, valid.session)
        return token_hash, valid

    async def _touch_if_due(self, token_hash: str, record: SessionRecord) -> None:
        now = self._clock.now()
        if now - record.last_used_at < self._touch_interval:
            return
        lifetime = self._lifetimes[record.client_kind]
        await self._sessions.touch(
            token_hash,
            now=now,
            idle_expires_at=min(now + lifetime.idle, record.absolute_expires_at),
        )

    def _emit(self, name: str, subject_id: UUID, client_kind: str) -> None:
        self._events.emit(
            AuthEvent(
                name=name,
                context={"subject_id": str(subject_id), "client_kind": client_kind},
            )
        )


def _token_invalid() -> AppError:
    """Build the single failure every bad token reports.

    The context stays empty so the response cannot reveal why the token
    failed.
    """
    return AppError(code=ErrorCode.AUTH_TOKEN_INVALID)


def _reauth_required() -> AppError:
    """Build the failure for a valid session whose password check is stale."""
    return AppError(code=ErrorCode.AUTH_REAUTH_REQUIRED)
