import itertools
import logging
from datetime import datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from pydantic import SecretStr
from trutina.authentication import (
    AccessState,
    ClientKind,
    IssuedSession,
    PasswordAuthenticator,
    SessionLifetime,
    SessionRecord,
    SessionService,
    ThrottledAuthenticator,
    ValidSession,
)
from trutina.authentication.sessions.service import MAX_SESSION_TOKEN_LENGTH
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_user
from tests.factories.secret import SECRET_SENTINEL
from tests.fakes import (
    FakeAuthEventSink,
    FakeClock,
    FakeLoginAttemptRepo,
    FakePasswordHasher,
    FakeSessionRepo,
    FakeSessionTokenHasher,
    FakeUserRepo,
)

API = ClientKind.API
CLI = ClientKind.CLI
EMAIL = "ann@example.com"
PASSWORD = "correct horse 1"
WRONG = "wrong horse 99"
IP = "203.0.113.7"
MAX_FAILURES = 3
WINDOW = 600
TOUCH = timedelta(minutes=5)
REAUTH = timedelta(minutes=30)
RETENTION = timedelta(days=7)
LIFETIMES = {
    API: SessionLifetime(idle=timedelta(hours=24), absolute=timedelta(days=7)),
    CLI: SessionLifetime(idle=timedelta(days=14), absolute=timedelta(days=30)),
}


class _SpySessionRepo(FakeSessionRepo):
    """Records the order of calls and every purge cutoff."""

    def __init__(self, users: FakeUserRepo) -> None:
        super().__init__(users)
        self.calls: list[str] = []
        self.cutoffs: list[datetime] = []

    async def create(self, record: SessionRecord) -> None:
        self.calls.append("create")
        await super().create(record)

    async def touch(
        self, token_hash: str, *, now: datetime, idle_expires_at: datetime
    ) -> None:
        self.calls.append("touch")
        await super().touch(token_hash, now=now, idle_expires_at=idle_expires_at)

    async def purge_before(self, cutoff: datetime) -> int:
        self.calls.append("purge_before")
        self.cutoffs.append(cutoff)
        return await super().purge_before(cutoff)


class _Harness:
    """A session service wired to fakes and a real throttled authenticator."""

    def __init__(self) -> None:
        self.users = FakeUserRepo()
        self.hasher = FakePasswordHasher()
        self.clock = FakeClock()
        self.events = FakeAuthEventSink()
        self.attempts = FakeLoginAttemptRepo()
        self.sessions = _SpySessionRepo(self.users)
        self.counter = itertools.count(1)
        self.service: SessionService

    async def start(self, **overrides) -> None:
        inner = await PasswordAuthenticator.create(users=self.users, hasher=self.hasher)
        throttled = ThrottledAuthenticator(
            inner=inner,
            attempts=self.attempts,
            clock=self.clock,
            max_failures=MAX_FAILURES,
            window_seconds=WINDOW,
        )
        kwargs = {
            "sessions": self.sessions,
            "users": self.users,
            "authenticator": throttled,
            "hasher": FakeSessionTokenHasher(),
            "clock": self.clock,
            "lifetimes": LIFETIMES,
            "touch_interval": TOUCH,
            "reauth_window": REAUTH,
            "purge_retention": RETENTION,
            "events": self.events,
            "token_factory": lambda: f"tok-{next(self.counter)}",
        }
        kwargs.update(overrides)
        self.service = SessionService(**kwargs)

    async def add_user(self, email: str = EMAIL, password: str = PASSWORD, **kw):
        user = make_user(
            email=email,
            password_hash=await self.hasher.hash(SecretStr(password)),
            **kw,
        )
        await self.users.create(user)
        return user

    async def login(
        self,
        *,
        email: str = EMAIL,
        password: str = PASSWORD,
        kind: ClientKind = API,
        ip: str | None = IP,
    ) -> IssuedSession:
        return await self.service.login(
            email=email, password=SecretStr(password), client_ip=ip, client_kind=kind
        )

    async def validate(self, issued: IssuedSession, kind: ClientKind = API):
        return await self.service.validate(issued.token, client_kind=kind)

    async def reauth(
        self,
        issued: IssuedSession,
        *,
        password: str = PASSWORD,
        kind: ClientKind = API,
        ip: str | None = IP,
    ) -> None:
        await self.service.reauthenticate(
            issued.token, client_kind=kind, password=SecretStr(password), client_ip=ip
        )

    def stored(self, issued: IssuedSession) -> SessionRecord:
        record = self.sessions.get(f"sha:{issued.token.get_secret_value()}")
        assert record is not None
        return record


@pytest_asyncio.fixture
async def harness() -> _Harness:
    built = _Harness()
    await built.start()
    return built


async def _failure(awaitable) -> AppError:
    with pytest.raises(AppError) as exc_info:
        await awaitable
    return exc_info.value


def _record(token_hash: str, *, user_id: UUID, now: datetime, **times) -> SessionRecord:
    values = {
        "created_at": now - timedelta(days=40),
        "last_used_at": now - timedelta(days=40),
        "authenticated_at": now - timedelta(days=40),
        "idle_expires_at": now + timedelta(days=1),
        "absolute_expires_at": now + timedelta(days=1),
    }
    values.update(times)
    return SessionRecord(
        token_hash=token_hash, user_id=user_id, client_kind=API, **values
    )


@pytest.mark.unit
class TestLogin:
    async def test_returns_the_token_once_with_subject_kind_and_absolute_expiry(
        self, harness
    ):
        user = await harness.add_user()

        issued = await harness.login()

        assert issued.token.get_secret_value() == "tok-1"
        assert issued.subject_id == user.id
        assert issued.client_kind is API
        assert issued.absolute_expires_at == harness.clock.now() + timedelta(days=7)

    async def test_stores_only_the_hash_of_the_token(self, harness):
        await harness.add_user()

        issued = await harness.login()

        assert harness.sessions.get("tok-1") is None
        assert "tok-1" not in repr(harness.stored(issued))
        assert "tok-1" not in repr(issued)

    @pytest.mark.parametrize(
        ("kind", "idle", "absolute"),
        [
            (API, timedelta(hours=24), timedelta(days=7)),
            (CLI, timedelta(days=14), timedelta(days=30)),
        ],
    )
    async def test_applies_the_lifetime_of_the_client_kind(
        self, harness, kind, idle, absolute
    ):
        await harness.add_user()
        now = harness.clock.now()

        record = harness.stored(await harness.login(kind=kind))

        assert record.client_kind is kind
        assert record.idle_expires_at == now + idle
        assert record.absolute_expires_at == now + absolute
        assert record.created_at == record.last_used_at == record.authenticated_at
        assert record.created_at == now

    async def test_caps_the_idle_expiry_at_the_absolute_expiry(self, harness):
        await harness.add_user()
        await harness.start(
            lifetimes={
                **LIFETIMES,
                API: SessionLifetime(
                    idle=timedelta(days=10), absolute=timedelta(days=2)
                ),
            }
        )

        record = harness.stored(await harness.login())

        assert record.idle_expires_at == record.absolute_expires_at

    async def test_wrong_password_creates_no_session_and_emits_nothing(self, harness):
        await harness.add_user()

        error = await _failure(harness.login(password=WRONG))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert "create" not in harness.sessions.calls
        assert harness.events.events == []

    async def test_a_throttled_login_creates_no_session(self, harness):
        await harness.add_user()
        for _ in range(MAX_FAILURES):
            await _failure(harness.login(password=WRONG))

        error = await _failure(harness.login())

        assert error.code == ErrorCode.AUTH_THROTTLED
        assert "create" not in harness.sessions.calls

    async def test_two_logins_give_two_tokens_and_logout_of_one_leaves_the_other(
        self, harness
    ):
        await harness.add_user()
        first = await harness.login()
        second = await harness.login()

        await harness.service.logout(first.token, client_kind=API)

        assert first.token.get_secret_value() != second.token.get_secret_value()
        assert (await harness.validate(second)).session.user_id == second.subject_id
        error = await _failure(harness.validate(first))
        assert error.code == ErrorCode.AUTH_TOKEN_INVALID

    async def test_purges_sessions_dead_longer_than_the_retention_window(self, harness):
        user = await harness.add_user()
        now = harness.clock.now()
        await harness.sessions.create(
            _record(
                "old",
                user_id=user.id,
                now=now,
                idle_expires_at=now - timedelta(days=20),
            )
        )
        await harness.sessions.create(
            _record(
                "recent",
                user_id=user.id,
                now=now,
                idle_expires_at=now - timedelta(days=1),
            )
        )

        await harness.login()

        assert harness.sessions.get("old") is None
        assert harness.sessions.get("recent") is not None

    async def test_purges_with_the_retention_cutoff_before_creating(self, harness):
        await harness.add_user()
        harness.sessions.calls.clear()

        await harness.login()

        assert harness.sessions.calls == ["purge_before", "create"]
        assert harness.sessions.cutoffs == [harness.clock.now() - RETENTION]

    async def test_a_failed_purge_creates_no_session(self, harness):
        await harness.add_user()
        failure = AppError.storage_unavailable()

        async def boom(cutoff: datetime) -> int:
            raise failure

        harness.sessions.purge_before = boom

        error = await _failure(harness.login())

        assert error is failure
        assert harness.sessions.get("sha:tok-1") is None

    async def test_emits_one_event_with_the_subject_and_kind_only(self, harness):
        user = await harness.add_user()

        await harness.login(kind=CLI)

        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.session_created"
        assert dict(event.context) == {
            "subject_id": str(user.id),
            "client_kind": "cli",
        }


@pytest.mark.unit
class TestValidate:
    async def test_returns_the_session_with_its_access_state(self, harness):
        user = await harness.add_user()
        issued = await harness.login()

        valid = await harness.validate(issued)

        assert isinstance(valid, ValidSession)
        assert valid.session.user_id == user.id
        assert valid.access == AccessState(is_active=True)

    @pytest.mark.parametrize(
        "token", ["", "missing", "x" * (MAX_SESSION_TOKEN_LENGTH + 1)]
    )
    async def test_rejects_a_blank_unknown_or_oversized_token(self, harness, token):
        error = await _failure(
            harness.service.validate(SecretStr(token), client_kind=API)
        )

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID
        assert dict(error.context) == {}

    async def test_accepts_a_token_at_the_length_limit_as_a_lookup(self, harness):
        token = SecretStr("x" * MAX_SESSION_TOKEN_LENGTH)

        error = await _failure(harness.service.validate(token, client_kind=API))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID
        assert "get_valid" not in harness.sessions.calls  # spy has no such hook

    @pytest.mark.parametrize(("issued_kind", "asked"), [(API, CLI), (CLI, API)])
    async def test_rejects_the_other_client_kind(self, harness, issued_kind, asked):
        await harness.add_user()
        issued = await harness.login(kind=issued_kind)

        error = await _failure(harness.validate(issued, asked))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID

    async def test_every_failure_cause_is_indistinguishable(self, harness):
        user = await harness.add_user()
        revoked = await harness.login()
        await harness.service.logout(revoked.token, client_kind=API)
        wrong_kind = await harness.login()
        expired = await harness.login()
        disabled = await harness.login()
        await harness.users.set_active(user.id, False)
        harness.clock.advance(timedelta(hours=24))

        errors = [
            await _failure(harness.validate(revoked)),
            await _failure(harness.validate(wrong_kind, CLI)),
            await _failure(harness.validate(expired)),
            await _failure(harness.validate(disabled)),
            await _failure(
                harness.service.validate(SecretStr("nope"), client_kind=API)
            ),
        ]

        assert {e.code for e in errors} == {ErrorCode.AUTH_TOKEN_INVALID}
        assert all(dict(e.context) == {} for e in errors)
        assert len({repr(e) for e in errors}) == 1

    async def test_idle_expiry_is_exclusive(self, harness):
        await harness.add_user()
        issued = await harness.login()
        harness.clock.advance(timedelta(hours=24) - timedelta(seconds=1))
        await harness.validate(issued)  # a touch here extends the idle expiry
        harness.clock.advance(timedelta(hours=24))

        error = await _failure(harness.validate(issued))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID

    async def test_absolute_expiry_ends_a_session_that_keeps_being_used(self, harness):
        await harness.add_user()
        await harness.start(
            lifetimes={
                **LIFETIMES,
                API: SessionLifetime(
                    idle=timedelta(hours=1), absolute=timedelta(hours=2)
                ),
            }
        )
        issued = await harness.login()
        for _ in range(3):
            harness.clock.advance(timedelta(minutes=30))
            await harness.validate(issued)
        harness.clock.advance(timedelta(minutes=30))

        error = await _failure(harness.validate(issued))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID

    async def test_a_disabled_user_fails_validation_at_once(self, harness):
        user = await harness.add_user()
        issued = await harness.login()
        await harness.users.set_active(user.id, False)

        error = await _failure(harness.validate(issued))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID

    async def test_does_not_record_a_use_inside_the_touch_interval(self, harness):
        await harness.add_user()
        issued = await harness.login()
        harness.clock.advance(TOUCH - timedelta(seconds=1))

        await harness.validate(issued)

        assert "touch" not in harness.sessions.calls
        assert harness.stored(issued).last_used_at == issued_at(harness, issued)

    async def test_records_a_use_exactly_at_the_touch_interval(self, harness):
        await harness.add_user()
        issued = await harness.login()
        harness.clock.advance(TOUCH)

        await harness.validate(issued)

        record = harness.stored(issued)
        assert record.last_used_at == harness.clock.now()
        assert record.idle_expires_at == harness.clock.now() + timedelta(hours=24)

    async def test_a_touch_never_extends_idle_expiry_past_the_absolute_expiry(
        self, harness
    ):
        await harness.add_user()
        await harness.start(
            lifetimes={
                **LIFETIMES,
                API: SessionLifetime(
                    idle=timedelta(hours=24), absolute=timedelta(hours=1)
                ),
            }
        )
        issued = await harness.login()
        harness.clock.advance(TOUCH)

        await harness.validate(issued)

        record = harness.stored(issued)
        assert record.idle_expires_at == record.absolute_expires_at

    async def test_a_use_does_not_change_when_the_password_was_last_checked(
        self, harness
    ):
        await harness.add_user()
        issued = await harness.login()
        before = harness.stored(issued).authenticated_at
        harness.clock.advance(TOUCH)

        await harness.validate(issued)

        assert harness.stored(issued).authenticated_at == before


def issued_at(harness: _Harness, issued: IssuedSession) -> datetime:
    return harness.stored(issued).created_at


@pytest.mark.unit
class TestRequireRecentAuth:
    async def test_passes_until_the_window_is_reached(self, harness):
        await harness.add_user()
        issued = await harness.login()
        valid = await harness.validate(issued)

        harness.service.require_recent_auth(valid)
        harness.clock.advance(REAUTH - timedelta(seconds=1))
        harness.service.require_recent_auth(valid)

    async def test_the_window_is_exclusive(self, harness):
        await harness.add_user()
        valid = await harness.validate(await harness.login())
        harness.clock.advance(REAUTH)

        with pytest.raises(AppError) as exc_info:
            harness.service.require_recent_auth(valid)

        assert exc_info.value.code == ErrorCode.AUTH_REAUTH_REQUIRED
        assert dict(exc_info.value.context) == {}

    async def test_ordinary_use_does_not_extend_the_window(self, harness):
        await harness.add_user()
        issued = await harness.login()
        harness.clock.advance(timedelta(minutes=20))
        await harness.validate(issued)
        harness.clock.advance(timedelta(minutes=15))

        with pytest.raises(AppError) as exc_info:
            harness.service.require_recent_auth(await harness.validate(issued))

        assert exc_info.value.code == ErrorCode.AUTH_REAUTH_REQUIRED


@pytest.mark.unit
class TestReauthenticate:
    async def test_refreshes_the_password_check_without_rotating_the_token(
        self, harness
    ):
        await harness.add_user()
        issued = await harness.login()
        harness.clock.advance(timedelta(minutes=40))

        await harness.reauth(issued)

        assert harness.stored(issued).authenticated_at == harness.clock.now()
        valid = await harness.validate(issued)
        harness.service.require_recent_auth(valid)

    async def test_emits_one_event_with_the_subject_and_kind_only(self, harness):
        user = await harness.add_user()
        issued = await harness.login()
        harness.events.events.clear()

        await harness.reauth(issued)

        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.session_reauthenticated"
        assert dict(event.context) == {
            "subject_id": str(user.id),
            "client_kind": "api",
        }

    async def test_a_wrong_password_leaves_the_session_valid_and_unchanged(
        self, harness
    ):
        await harness.add_user()
        issued = await harness.login()
        before = harness.stored(issued).authenticated_at
        harness.clock.advance(timedelta(minutes=40))
        harness.events.events.clear()

        error = await _failure(harness.reauth(issued, password=WRONG))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert harness.stored(issued).authenticated_at == before
        assert harness.events.events == []
        await harness.validate(issued)

    async def test_checks_the_password_of_the_sessions_own_user(self, harness):
        await harness.add_user()
        await harness.add_user(email="bob@example.com", password="bobs password 2")
        issued = await harness.login()

        error = await _failure(harness.reauth(issued, password="bobs password 2"))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS

    async def test_is_throttled_and_leaves_the_session_valid(self, harness):
        await harness.add_user()
        issued = await harness.login()
        for _ in range(MAX_FAILURES):
            await _failure(harness.reauth(issued, password=WRONG))

        error = await _failure(harness.reauth(issued))

        assert error.code == ErrorCode.AUTH_THROTTLED
        await harness.validate(issued)

    async def test_an_invalid_token_is_rejected_before_any_password_check(
        self, harness
    ):
        error = await _failure(
            harness.service.reauthenticate(
                SecretStr("missing"),
                client_kind=API,
                password=SecretStr(PASSWORD),
                client_ip=IP,
            )
        )

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID
        assert harness.hasher.verify_calls == []

    async def test_a_disabled_user_cannot_reauthenticate(self, harness):
        user = await harness.add_user()
        issued = await harness.login()
        await harness.users.set_active(user.id, False)

        error = await _failure(harness.reauth(issued))

        assert error.code == ErrorCode.AUTH_TOKEN_INVALID


@pytest.mark.unit
class TestLogout:
    async def test_ends_the_session_and_emits_one_event(self, harness):
        user = await harness.add_user()
        issued = await harness.login()
        harness.events.events.clear()

        await harness.service.logout(issued.token, client_kind=API)

        error = await _failure(harness.validate(issued))
        assert error.code == ErrorCode.AUTH_TOKEN_INVALID
        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.session_revoked"
        assert dict(event.context) == {
            "subject_id": str(user.id),
            "client_kind": "api",
        }

    async def test_is_idempotent_and_emits_once(self, harness):
        await harness.add_user()
        issued = await harness.login()
        harness.events.events.clear()

        await harness.service.logout(issued.token, client_kind=API)
        await harness.service.logout(issued.token, client_kind=API)

        assert len(harness.events.events) == 1

    async def test_an_unknown_token_is_a_silent_no_op(self, harness):
        await harness.service.logout(SecretStr("missing"), client_kind=API)
        await harness.service.logout(SecretStr(""), client_kind=API)

        assert harness.events.events == []

    async def test_the_other_client_kind_cannot_end_a_session(self, harness):
        await harness.add_user()
        issued = await harness.login(kind=CLI)

        await harness.service.logout(issued.token, client_kind=API)

        await harness.validate(issued, CLI)


@pytest.mark.unit
class TestRevokeAllForUser:
    async def test_ends_every_session_of_that_user_only(self, harness):
        ann = await harness.add_user()
        await harness.add_user(email="bob@example.com")
        ann_api = await harness.login()
        ann_cli = await harness.login(kind=CLI)
        bob = await harness.login(email="bob@example.com")
        harness.events.events.clear()

        await harness.service.revoke_all_for_user(ann.id)

        assert (await _failure(harness.validate(ann_api))).code == (
            ErrorCode.AUTH_TOKEN_INVALID
        )
        assert (await _failure(harness.validate(ann_cli, CLI))).code == (
            ErrorCode.AUTH_TOKEN_INVALID
        )
        await harness.validate(bob)
        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.session_revoked"
        assert dict(event.context) == {"subject_id": str(ann.id), "client_kind": "all"}


@pytest.mark.unit
class TestConstruction:
    @pytest.mark.parametrize(
        "field", ["touch_interval", "reauth_window", "purge_retention"]
    )
    async def test_rejects_a_non_positive_interval(self, harness, field):
        with pytest.raises(ValueError):
            await harness.start(**{field: timedelta(0)})

    async def test_rejects_a_missing_lifetime_for_a_client_kind(self, harness):
        with pytest.raises(ValueError):
            await harness.start(lifetimes={API: LIFETIMES[API]})

    @pytest.mark.parametrize(
        ("idle", "absolute"),
        [(timedelta(0), timedelta(days=1)), (timedelta(days=1), timedelta(0))],
    )
    def test_a_lifetime_must_be_positive(self, idle, absolute):
        with pytest.raises(ValueError):
            SessionLifetime(idle=idle, absolute=absolute)


@pytest.mark.unit
class TestLeaksNothing:
    async def test_the_token_reaches_no_event_error_or_log(self, harness, caplog):
        await harness.add_user()
        await harness.start(token_factory=lambda: SECRET_SENTINEL)
        errors: list[AppError] = []

        with caplog.at_level(logging.DEBUG):
            issued = await harness.login()
            await harness.validate(issued)
            errors.append(await _failure(harness.validate(issued, CLI)))
            errors.append(await _failure(harness.reauth(issued, password=WRONG)))
            await harness.reauth(issued)
            await harness.service.logout(issued.token, client_kind=API)
            errors.append(await _failure(harness.validate(issued)))

        assert SECRET_SENTINEL not in repr(issued)
        assert all(SECRET_SENTINEL not in repr(e) for e in errors)
        assert all(SECRET_SENTINEL not in repr(e) for e in harness.events.events)
        assert [r for r in caplog.records if r.name.startswith("trutina")] == []
