import logging
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from trutina.authentication import (
    MAX_EMAIL_LENGTH,
    Authenticator,
    Identity,
    PasswordAuthenticator,
    ThrottledAuthenticator,
)
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_user
from tests.factories.secret import SECRET_SENTINEL
from tests.fakes import (
    FakeAuthEventSink,
    FakeClock,
    FakeLoginAttemptRepo,
    FakePasswordHasher,
    FakeUserRepo,
)

MAX_FAILURES = 3
WINDOW = 600
IP = "203.0.113.7"
EMAIL = "ann@example.com"
PASSWORD = "correct horse 1"


class _SpyAttemptRepo(FakeLoginAttemptRepo):
    """Records the name of every call, in order."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        self.calls.append("record_failure")
        await super().record_failure(ip=ip, email=email, at=at)

    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        self.calls.append("count_failures")
        return await super().count_failures(ip=ip, email=email, since=since)

    async def clear(self, *, ip: str, email: str) -> None:
        self.calls.append("clear")
        await super().clear(ip=ip, email=email)

    async def purge_before(self, cutoff: datetime) -> int:
        self.calls.append("purge_before")
        return await super().purge_before(cutoff)


class _BrokenAttemptRepo(_SpyAttemptRepo):
    """Fails every count with the given error."""

    def __init__(self, failure: AppError) -> None:
        super().__init__()
        self.failure = failure

    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        raise self.failure


class _StubAuthenticator(Authenticator):
    """Raises ``error`` when set, otherwise returns ``identity``."""

    def __init__(self, *, error: AppError | None = None) -> None:
        self.error = error
        self.identity = Identity(subject_id=uuid4())
        self.calls: list[tuple[str, str | None]] = []

    async def authenticate(
        self, *, email: str, password: SecretStr, client_ip: str | None
    ) -> Identity:
        self.calls.append((email, client_ip))
        if self.error is not None:
            raise self.error
        return self.identity


class _Harness:
    """A throttle wired to fakes; the stub fails every login until told not to."""

    def __init__(
        self,
        *,
        inner: Authenticator | None = None,
        attempts: _SpyAttemptRepo | None = None,
    ) -> None:
        self.stub = _StubAuthenticator(
            error=AppError(code=ErrorCode.AUTH_INVALID_CREDENTIALS)
        )
        self.attempts = attempts if attempts is not None else _SpyAttemptRepo()
        self.clock = FakeClock()
        self.events = FakeAuthEventSink()
        self.service = ThrottledAuthenticator(
            inner=inner if inner is not None else self.stub,
            attempts=self.attempts,
            clock=self.clock,
            max_failures=MAX_FAILURES,
            window_seconds=WINDOW,
            events=self.events,
        )

    async def login(
        self,
        *,
        email: str = EMAIL,
        password: str = PASSWORD,
        ip: str | None = IP,
    ) -> Identity:
        return await self.service.authenticate(
            email=email, password=SecretStr(password), client_ip=ip
        )

    async def fail(self, times: int, **kwargs) -> None:
        for _ in range(times):
            with pytest.raises(AppError):
                await self.login(**kwargs)

    async def failures(self, *, ip: str = IP, email: str = EMAIL) -> int:
        return await self.attempts.count_failures(
            ip=ip, email=email, since=self.clock.now() - timedelta(seconds=WINDOW)
        )


async def _failure(awaitable) -> AppError:
    with pytest.raises(AppError) as exc_info:
        await awaitable
    return exc_info.value


@pytest.mark.unit
class TestAllowsAttempts:
    async def test_returns_the_inner_identity_and_passes_arguments_through(self):
        harness = _Harness()
        harness.stub.error = None

        identity = await harness.login(email=" Ann@Example.com ")

        assert identity == harness.stub.identity
        assert harness.stub.calls == [(" Ann@Example.com ", IP)]

    async def test_records_an_invalid_credentials_failure_and_reraises_it(self):
        harness = _Harness()

        error = await _failure(harness.login())

        assert error is harness.stub.error
        assert await harness.failures() == 1

    async def test_still_reaches_the_inner_authenticator_below_the_threshold(self):
        harness = _Harness()

        await harness.fail(MAX_FAILURES)

        assert len(harness.stub.calls) == MAX_FAILURES

    async def test_success_clears_earlier_failures(self):
        harness = _Harness()
        await harness.fail(2)
        harness.stub.error = None

        await harness.login()

        assert await harness.failures() == 0
        assert "clear" in harness.attempts.calls

    async def test_success_without_earlier_failures_writes_nothing(self):
        harness = _Harness()
        harness.stub.error = None

        await harness.login()

        assert harness.attempts.calls == ["count_failures"]


@pytest.mark.unit
class TestThrottles:
    async def test_rejects_at_the_threshold_without_reaching_the_inner_authenticator(
        self,
    ):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)
        reached = len(harness.stub.calls)

        error = await _failure(harness.login())

        assert error.code == ErrorCode.AUTH_THROTTLED
        assert dict(error.context) == {"retry_after_seconds": str(WINDOW)}
        assert len(harness.stub.calls) == reached

    async def test_rejects_the_correct_password_while_throttled(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)
        harness.stub.error = None

        error = await _failure(harness.login())

        assert error.code == ErrorCode.AUTH_THROTTLED

    async def test_does_not_record_a_throttled_attempt(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)

        await _failure(harness.login())

        assert await harness.failures() == MAX_FAILURES
        assert harness.attempts.calls.count("record_failure") == MAX_FAILURES

    async def test_throttles_unknown_and_known_emails_identically_without_hashing(
        self,
    ):
        users = FakeUserRepo()
        hasher = FakePasswordHasher()
        await users.create(
            make_user(
                email=EMAIL,
                password_hash=await hasher.hash(SecretStr("right password 1")),
            )
        )
        inner = await PasswordAuthenticator.create(users=users, hasher=hasher)
        harness = _Harness(inner=inner)
        unknown = "nobody@example.com"
        await harness.fail(MAX_FAILURES, email=EMAIL)
        await harness.fail(MAX_FAILURES, email=unknown)
        verifies = len(hasher.verify_calls)

        known_error = await _failure(harness.login(email=EMAIL))
        unknown_error = await _failure(harness.login(email=unknown))

        assert known_error.code == ErrorCode.AUTH_THROTTLED
        assert repr(known_error) == repr(unknown_error)
        assert len(hasher.verify_calls) == verifies

    async def test_ignores_failures_older_than_the_window(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)
        harness.clock.advance(timedelta(seconds=WINDOW + 1))

        error = await _failure(harness.login())

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS

    async def test_is_scoped_to_one_ip_and_email(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)

        other_ip = await _failure(harness.login(ip="198.51.100.9"))
        other_email = await _failure(harness.login(email="bob@example.com"))

        assert other_ip.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert other_email.code == ErrorCode.AUTH_INVALID_CREDENTIALS

    async def test_matches_the_email_ignoring_case_and_whitespace(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES, email="  ANN@Example.COM ")

        error = await _failure(harness.login(email=EMAIL))

        assert error.code == ErrorCode.AUTH_THROTTLED

    async def test_a_missing_ip_shares_the_unknown_bucket(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES, ip=None)

        none_error = await _failure(harness.login(ip=None))
        sentinel_error = await _failure(harness.login(ip="unknown"))

        assert none_error.code == ErrorCode.AUTH_THROTTLED
        assert sentinel_error.code == ErrorCode.AUTH_THROTTLED
        assert await harness.failures(ip="unknown") == MAX_FAILURES

    async def test_skips_an_over_limit_email_without_touching_storage(self):
        harness = _Harness()
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c") + 1) + "@b.c"

        error = await _failure(harness.login(email=email))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert len(harness.stub.calls) == 1
        assert harness.attempts.calls == []


@pytest.mark.unit
class TestPurge:
    async def test_removes_failures_older_than_the_window_when_recording_one(self):
        harness = _Harness()
        await harness.attempts.record_failure(
            ip="198.51.100.9", email="old@example.com", at=harness.clock.now()
        )
        harness.clock.advance(timedelta(seconds=WINDOW + 1))

        await harness.fail(1)

        old = await harness.attempts.count_failures(
            ip="198.51.100.9",
            email="old@example.com",
            since=harness.clock.now() - timedelta(days=1),
        )
        assert old == 0
        assert "purge_before" in harness.attempts.calls

    async def test_does_not_purge_on_success_or_when_throttled(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)
        purges = harness.attempts.calls.count("purge_before")

        await _failure(harness.login())
        harness.clock.advance(timedelta(seconds=WINDOW + 1))
        harness.stub.error = None
        await harness.login()

        assert harness.attempts.calls.count("purge_before") == purges


@pytest.mark.unit
class TestEvents:
    async def test_emits_one_secret_free_event_per_throttled_attempt(self):
        harness = _Harness()
        await harness.fail(MAX_FAILURES)
        assert harness.events.events == []

        await _failure(harness.login())

        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.login_throttled"
        assert dict(event.context) == {"retry_after_seconds": str(WINDOW)}
        assert EMAIL not in repr(event)
        assert IP not in repr(event)

    async def test_emits_nothing_for_ordinary_failures_or_success(self):
        harness = _Harness()
        await harness.fail(2)
        harness.stub.error = None

        await harness.login()

        assert harness.events.events == []

    async def test_works_without_an_event_sink(self):
        harness = _Harness()
        service = ThrottledAuthenticator(
            inner=harness.stub,
            attempts=harness.attempts,
            clock=harness.clock,
            max_failures=1,
            window_seconds=WINDOW,
        )
        await harness.fail(1)

        with pytest.raises(AppError) as exc_info:
            await service.authenticate(
                email=EMAIL, password=SecretStr(PASSWORD), client_ip=IP
            )

        assert exc_info.value.code == ErrorCode.AUTH_THROTTLED


@pytest.mark.unit
class TestErrorsPassThrough:
    async def test_an_inner_storage_error_propagates_and_is_not_recorded(self):
        harness = _Harness()
        failure = AppError.storage_unavailable()
        harness.stub.error = failure

        error = await _failure(harness.login())

        assert error is failure
        assert harness.attempts.calls == ["count_failures"]

    async def test_an_attempt_store_error_propagates_before_the_inner_runs(self):
        failure = AppError.storage_timeout()
        harness = _Harness(attempts=_BrokenAttemptRepo(failure))

        error = await _failure(harness.login())

        assert error is failure
        assert harness.stub.calls == []


@pytest.mark.unit
class TestConstruction:
    @pytest.mark.parametrize(
        ("max_failures", "window_seconds"), [(0, WINDOW), (MAX_FAILURES, 0)]
    )
    def test_rejects_a_limit_below_one(self, max_failures, window_seconds):
        with pytest.raises(ValueError):
            ThrottledAuthenticator(
                inner=_StubAuthenticator(),
                attempts=_SpyAttemptRepo(),
                clock=FakeClock(),
                max_failures=max_failures,
                window_seconds=window_seconds,
            )


@pytest.mark.unit
class TestLeaksNothing:
    async def test_emits_no_logs_and_never_echoes_the_password(self, caplog):
        harness = _Harness()

        with caplog.at_level(logging.DEBUG):
            await harness.fail(MAX_FAILURES, password=SECRET_SENTINEL)
            throttled = await _failure(harness.login(password=SECRET_SENTINEL))

        assert SECRET_SENTINEL not in repr(throttled)
        assert all(SECRET_SENTINEL not in repr(e) for e in harness.events.events)
        assert [r for r in caplog.records if r.name.startswith("trutina")] == []
