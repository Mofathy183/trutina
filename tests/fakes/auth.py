"""In-memory fakes for the trutina-authentication contracts.

Each fake satisfies its contract with the least machinery needed for unit
tests and exposes lightweight hooks for assertions. None performs I/O.
Contracts marked provisional in ``trutina.authentication`` (tokens,
refresh tokens, login attempts) may change with them.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import SecretStr
from trutina.authentication import (
    AccessState,
    AccessToken,
    AuthEvent,
    AuthEventSink,
    Clock,
    Identity,
    LoginAttemptRepo,
    PasswordHasher,
    RefreshTokenHasher,
    RefreshTokenRecord,
    RefreshTokenRepo,
    RotationOutcome,
    RotationResult,
    TokenIssuer,
    TokenVerifier,
    User,
    UserRepo,
    UserStatusChecker,
)

_TOKEN_PREFIX = "fake-access-"


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


class FakeRefreshTokenHasher(RefreshTokenHasher):
    """Deterministic hasher: ``sha:<token>``."""

    def hash(self, token: SecretStr) -> str:
        return f"sha:{token.get_secret_value()}"


class FakeTokenIssuer(TokenIssuer):
    """Issues ``fake-access-<subject_id>`` tokens expiring ``ttl`` after the clock."""

    def __init__(self, clock: Clock, ttl: timedelta = timedelta(minutes=15)) -> None:
        self._clock = clock
        self._ttl = ttl

    def issue_access_token(self, identity: Identity) -> AccessToken:
        return AccessToken(
            value=SecretStr(f"{_TOKEN_PREFIX}{identity.subject_id}"),
            expires_at=self._clock.now() + self._ttl,
        )


class FakeTokenVerifier(TokenVerifier):
    """Accepts exactly the tokens ``FakeTokenIssuer`` produces; ignores expiry."""

    def verify_access_token(self, token: SecretStr) -> Identity | None:
        value = token.get_secret_value()
        if not value.startswith(_TOKEN_PREFIX):
            return None
        try:
            return Identity(subject_id=UUID(value[len(_TOKEN_PREFIX) :]))
        except ValueError:
            return None


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

    ``create()`` does not reject a duplicate email: the service
    pre-checks, and the storage unique index is the real backstop.

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
        key = email.casefold()
        for user in self._users.values():
            if user.email.casefold() == key:
                return user
        return None

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        user = self._users[user_id]
        self._users[user_id] = user.model_copy(update={"password_hash": password_hash})


class FakeLoginAttemptRepo(LoginAttemptRepo):
    """In-memory failure log keyed on (ip, casefolded email)."""

    def __init__(self) -> None:
        self._rows: list[tuple[str, str, datetime]] = []

    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        self._rows.append((ip, email.casefold(), at))

    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        key = email.casefold()
        return sum(1 for i, e, at in self._rows if (i, e) == (ip, key) and at >= since)

    async def clear(self, *, ip: str, email: str) -> None:
        key = email.casefold()
        self._rows = [r for r in self._rows if (r[0], r[1]) != (ip, key)]

    async def purge_before(self, cutoff: datetime) -> int:
        kept = [r for r in self._rows if r[2] >= cutoff]
        removed = len(self._rows) - len(kept)
        self._rows = kept
        return removed


class FakeRefreshTokenRepo(RefreshTokenRepo):
    """In-memory RefreshTokenRepo.

    ``rotate`` has no ``await`` between its check and its write, so on a
    single event loop it is atomic: of two concurrent calls with the same
    hash exactly one rotates. It does not simulate a database's behavior
    under real concurrency.
    """

    def __init__(self) -> None:
        self._records: dict[str, RefreshTokenRecord] = {}

    def get(self, token_hash: str) -> RefreshTokenRecord | None:
        """Inspect a stored record (test hook, not part of the contract)."""
        return self._records.get(token_hash)

    async def add(self, record: RefreshTokenRecord) -> None:
        self._records[record.token_hash] = record

    async def rotate(
        self,
        *,
        presented_hash: str,
        replacement: RefreshTokenRecord,
        now: datetime,
    ) -> RotationResult:
        record = self._records.get(presented_hash)
        if record is None or record.expires_at <= now:
            return RotationResult(RotationOutcome.INVALID)
        if record.used_at is not None or record.revoked_at is not None:
            return RotationResult(RotationOutcome.REUSED, record)
        self._records[presented_hash] = replace(record, used_at=now)
        self._records[replacement.token_hash] = replacement
        return RotationResult(RotationOutcome.ROTATED, record)

    async def revoke_family(self, family_id: UUID, *, now: datetime) -> None:
        for key, record in self._records.items():
            if record.family_id == family_id and record.revoked_at is None:
                self._records[key] = replace(record, revoked_at=now)

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        for key, record in self._records.items():
            if record.user_id == user_id and record.revoked_at is None:
                self._records[key] = replace(record, revoked_at=now)

    async def purge_expired(self, *, now: datetime) -> int:
        expired = [k for k, r in self._records.items() if r.expires_at <= now]
        for key in expired:
            del self._records[key]
        return len(expired)
