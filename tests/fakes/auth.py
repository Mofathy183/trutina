"""In-memory fakes for the trutina-authentication contracts.

Each fake satisfies its contract with the least machinery needed for unit
tests and exposes lightweight hooks for assertions. None performs I/O.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import SecretStr
from trutina.authentication import (
    AccessState,
    AuthEvent,
    AuthEventSink,
    ClientKind,
    Clock,
    LoginAttemptRepo,
    PasswordHasher,
    SessionRecord,
    SessionRepo,
    SessionTokenHasher,
    User,
    UserRepo,
    UserStatusChecker,
    ValidSession,
    normalize_email,
)
from trutina.shared.errors import AppError, ErrorCode


class FakeClock(Clock):
    """Settable clock; starts at 2025-01-01T00:00:00Z and never moves alone."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2025, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class FakeAuthEventSink(AuthEventSink):
    """Records every emitted event in ``events``, in order."""

    def __init__(self) -> None:
        self.events: list[AuthEvent] = []

    def emit(self, event: AuthEvent) -> None:
        self.events.append(event)


class FakePasswordHasher(PasswordHasher):
    """Deterministic, instant hasher: ``fake$<password>``.

    Not secure and not slow; it simulates neither cost nor offloading.

    Attributes:
        hash_calls: Number of ``hash`` calls.
        verify_calls: The ``password_hash`` argument of every ``verify``
            call, in order, so a test can assert the dummy-hash path ran
            for an unknown user without any timing assertion.
        stale_hashes: Hashes for which ``needs_rehash`` returns ``True``.
    """

    def __init__(self) -> None:
        self.hash_calls = 0
        self.verify_calls: list[str] = []
        self.stale_hashes: set[str] = set()

    async def hash(self, password: SecretStr) -> str:
        self.hash_calls += 1
        return f"fake${password.get_secret_value()}"

    async def verify(self, password: SecretStr, password_hash: str) -> bool:
        self.verify_calls.append(password_hash)
        return password_hash == f"fake${password.get_secret_value()}"

    def needs_rehash(self, password_hash: str) -> bool:
        return password_hash in self.stale_hashes


class FakeSessionTokenHasher(SessionTokenHasher):
    """Deterministic hasher: ``sha:<token>``."""

    def hash(self, token: SecretStr) -> str:
        return f"sha:{token.get_secret_value()}"


class FakeUserStatusChecker(UserStatusChecker):
    """Returns the state set for a user; unknown users are inactive."""

    def __init__(self, states: dict[UUID, AccessState] | None = None) -> None:
        self._states = dict(states or {})

    def set_state(self, subject_id: UUID, state: AccessState) -> None:
        self._states[subject_id] = state

    async def get_access_state(self, subject_id: UUID) -> AccessState:
        return self._states.get(subject_id, AccessState(is_active=False))


class FakeUserRepo(UserRepo):
    """In-memory UserRepo.

    ``create()`` stores the user as given, including ``created_at``
    (the real adapter ignores it and stamps its own), and does not
    reject a duplicate email: the service pre-checks, and the storage
    unique index is the real backstop.

    ``update_password_hash`` and ``set_active`` raise ``UNKNOWN_USER``
    for an unknown id, like the real adapter.

    Attributes:
        created_users: Every user passed to ``create``, in order.
    """

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self.created_users: list[User] = []

    async def create(self, user: User) -> None:
        self.created_users.append(user)
        self._users[user.id] = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        key = normalize_email(email)
        for user in self._users.values():
            if user.email == key:
                return user
        return None

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        user = self._require(user_id)
        self._users[user_id] = user.model_copy(update={"password_hash": password_hash})

    async def set_active(self, user_id: UUID, is_active: bool) -> None:
        user = self._require(user_id)
        self._users[user_id] = user.model_copy(update={"is_active": is_active})

    def _require(self, user_id: UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_USER,
                resource="user",
                identifier=str(user_id),
            )
        return user


class FakeLoginAttemptRepo(LoginAttemptRepo):
    """In-memory failure log keyed on (ip, normalized email)."""

    def __init__(self) -> None:
        self._rows: list[tuple[str, str, datetime]] = []

    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        self._rows.append((ip, normalize_email(email), at))

    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        key = normalize_email(email)
        return sum(1 for i, e, at in self._rows if (i, e) == (ip, key) and at >= since)

    async def clear(self, *, ip: str, email: str) -> None:
        key = normalize_email(email)
        self._rows = [r for r in self._rows if (r[0], r[1]) != (ip, key)]

    async def purge_before(self, cutoff: datetime) -> int:
        kept = [r for r in self._rows if r[2] >= cutoff]
        removed = len(self._rows) - len(kept)
        self._rows = kept
        return removed


def _died_at(record: SessionRecord) -> datetime:
    """The earliest moment a session stopped being usable."""
    moments = [record.idle_expires_at, record.absolute_expires_at]
    if record.revoked_at is not None:
        moments.append(record.revoked_at)
    return min(moments)


class FakeSessionRepo(SessionRepo):
    """In-memory SessionRepo.

    Evaluates validity against the ``now`` it is given and the
    ``FakeUserRepo`` it is constructed with, standing in for the join to the
    users table. No method has an ``await`` between a check and its write,
    so on one event loop each is atomic. It does not simulate a database's
    behavior under real concurrency, connection use or transactions.

    ``touch``, ``mark_reauthenticated``, ``revoke`` and ``revoke_all_for_user``
    never move a stored time backward, like the contract requires.
    """

    def __init__(self, users: FakeUserRepo) -> None:
        self._users = users
        self._records: dict[str, SessionRecord] = {}

    def get(self, token_hash: str) -> SessionRecord | None:
        """Inspect a stored record (test hook, not part of the contract)."""
        return self._records.get(token_hash)

    async def create(self, record: SessionRecord) -> None:
        self._records[record.token_hash] = record

    async def get_valid(
        self,
        token_hash: str,
        *,
        client_kind: ClientKind,
        now: datetime,
    ) -> ValidSession | None:
        record = self._records.get(token_hash)
        if record is None or record.client_kind is not client_kind:
            return None
        if record.revoked_at is not None:
            return None
        if record.idle_expires_at <= now or record.absolute_expires_at <= now:
            return None
        user = await self._users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            return None
        return ValidSession(
            session=record, access=AccessState(is_active=user.is_active)
        )

    async def touch(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
    ) -> None:
        record = self._records.get(token_hash)
        if record is None or record.revoked_at is not None:
            return
        self._records[token_hash] = replace(
            record,
            last_used_at=max(record.last_used_at, now),
            idle_expires_at=max(record.idle_expires_at, idle_expires_at),
        )

    async def mark_reauthenticated(self, token_hash: str, *, now: datetime) -> None:
        record = self._records.get(token_hash)
        if record is None or record.revoked_at is not None:
            return
        self._records[token_hash] = replace(
            record, authenticated_at=max(record.authenticated_at, now)
        )

    async def revoke(self, token_hash: str, *, now: datetime) -> None:
        record = self._records.get(token_hash)
        if record is None or record.revoked_at is not None:
            return
        self._records[token_hash] = replace(record, revoked_at=now)

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        for key, record in self._records.items():
            if record.user_id == user_id and record.revoked_at is None:
                self._records[key] = replace(record, revoked_at=now)

    async def purge_before(self, cutoff: datetime) -> int:
        dead = [k for k, r in self._records.items() if _died_at(r) < cutoff]
        for key in dead:
            del self._records[key]
        return len(dead)
