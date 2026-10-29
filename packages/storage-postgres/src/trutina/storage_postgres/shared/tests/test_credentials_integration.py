"""End-to-end credential verification against real PostgreSQL (M2.8).

Wires the real ``RegistrationService``, ``PasswordAuthenticator`` and
``ThrottledAuthenticator`` to the real ``PostgresUserRepo`` and
``PostgresLoginAttemptRepo`` and a real ``Argon2PasswordHasher`` (cheapest
parameters). Only the clock and the event sink are fakes: the clock makes
the throttle window deterministic, since ``attempted_at`` is caller
supplied (D27).

It lives in this package rather than in trutina-authentication because it
reads tables with SQLAlchemy, and authentication must never import
storage. For the same reason it cannot import trutina.observability, so
the log check uses a plain stdlib handler; the structlog pipeline's own
redaction is covered in trutina-observability, and the route-level proof
belongs to M3.7.

Scope: closes, at service level, the end-to-end criteria that M2.0 to
M2.7 deferred (R4). It adds no behavior.
"""

import asyncio
import logging
from datetime import timedelta

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from trutina.authentication import (
    MAX_PASSWORD_LENGTH,
    Argon2PasswordHasher,
    Identity,
    PasswordAuthenticator,
    RegisteredUser,
    RegisterInput,
    RegistrationService,
    ThrottledAuthenticator,
)
from trutina.shared.errors import AppError, ErrorCode

from tests.fakes import FakeAuthEventSink, FakeClock

MAX_FAILURES = 3
WINDOW = 600
IP = "203.0.113.7"
OTHER_IP = "198.51.100.9"
EMAIL = "ann@example.com"
PASSWORD = "correct horse 1"
WRONG = "wrong horse 99"


class _RecordingHasher(Argon2PasswordHasher):
    """Real Argon2id hasher that also records what it was asked to do.

    ``verify_calls`` holds the stored hash passed to every ``verify``, so a
    test can prove the dummy-hash path ran without any timing assertion.
    """

    def __init__(
        self, *, time_cost: int, memory_cost_kib: int, max_concurrency: int
    ) -> None:
        super().__init__(
            time_cost=time_cost,
            memory_cost_kib=memory_cost_kib,
            parallelism=1,
            max_concurrency=max_concurrency,
        )
        self.hash_calls = 0
        self.verify_calls: list[str] = []

    async def hash(self, password: SecretStr) -> str:
        self.hash_calls += 1
        return await super().hash(password)

    async def verify(self, password: SecretStr, password_hash: str) -> bool:
        self.verify_calls.append(password_hash)
        return await super().verify(password, password_hash)


def _hasher(time_cost: int = 1) -> _RecordingHasher:
    # Cheapest parameters Argon2 accepts, so the suite stays fast.
    return _RecordingHasher(time_cost=time_cost, memory_cost_kib=8, max_concurrency=2)


class _Credentials:
    """Real services over real repositories, exposing what tests assert on."""

    def __init__(self, users, attempts, engine) -> None:
        self.users = users
        self.attempts = attempts
        self.engine = engine
        self.clock = FakeClock()
        self.events = FakeAuthEventSink()
        self.hasher = _hasher()
        self.registration = RegistrationService(
            users=users, hasher=self.hasher, clock=self.clock, events=self.events
        )
        self.inner: PasswordAuthenticator
        self.service: ThrottledAuthenticator

    async def start(self) -> None:
        self.service = await self.throttled_for(self.hasher, remember=True)

    async def throttled_for(
        self, hasher: Argon2PasswordHasher, *, remember: bool = False
    ) -> ThrottledAuthenticator:
        inner = await PasswordAuthenticator.create(users=self.users, hasher=hasher)
        if remember:
            self.inner = inner
        return ThrottledAuthenticator(
            inner=inner,
            attempts=self.attempts,
            clock=self.clock,
            max_failures=MAX_FAILURES,
            window_seconds=WINDOW,
            events=self.events,
        )

    async def register(
        self, email: str = EMAIL, password: str = PASSWORD
    ) -> RegisteredUser:
        return await self.registration.register(
            RegisterInput(email=email, password=SecretStr(password))
        )

    async def login(
        self,
        email: str = EMAIL,
        password: str = PASSWORD,
        ip: str | None = IP,
        *,
        service: ThrottledAuthenticator | None = None,
    ) -> Identity:
        return await (service or self.service).authenticate(
            email=email, password=SecretStr(password), client_ip=ip
        )

    async def fail(self, times: int, **kwargs) -> None:
        for _ in range(times):
            error = await _failure(self.login(**kwargs))
            assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS

    async def count(self, *, ip: str = IP, email: str = EMAIL) -> int:
        return await self.attempts.count_failures(
            ip=ip, email=email, since=self.clock.now() - timedelta(seconds=WINDOW)
        )

    async def sql_scalar(self, sql: str, **params):
        async with self.engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar_one()

    async def sql_dump(self, table: str) -> str:
        async with self.engine.connect() as conn:
            result = await conn.execute(text(f"SELECT t::text FROM {table} t"))  # noqa: S608
            return "\n".join(result.scalars().all())

    async def password_hash(self, email: str = EMAIL) -> str:
        return await self.sql_scalar(
            "SELECT password_hash FROM users WHERE email = :e", e=email
        )


async def _failure(awaitable) -> AppError:
    with pytest.raises(AppError) as exc_info:
        await awaitable
    return exc_info.value


@pytest_asyncio.fixture
async def creds(postgres_user_repo, postgres_login_attempt_repo, postgres_connection):
    harness = _Credentials(
        postgres_user_repo, postgres_login_attempt_repo, postgres_connection.engine
    )
    await harness.start()
    return harness


@pytest.mark.integration
class TestRegisterThenLogin:
    async def test_logs_in_with_a_differently_typed_email(self, creds):
        registered = await creds.register(email=" Ann@Example.com ")

        identity = await creds.login(email="  ANN@example.COM ")

        assert identity == Identity(subject_id=registered.id)
        assert registered.email == EMAIL

    async def test_stores_a_normalized_email_and_an_argon2id_hash_only(self, creds):
        await creds.register(email=" Ann@Example.com ")

        stored = await creds.password_hash()

        assert stored.startswith("$argon2id$")
        assert "m=8,t=1,p=1" in stored
        assert PASSWORD not in stored
        assert await creds.sql_scalar("SELECT count(*) FROM users") == 1

    async def test_rejects_a_second_registration_in_another_casing_before_hashing(
        self, creds
    ):
        await creds.register()

        with pytest.raises(AppError) as exc_info:
            await creds.register(email="ANN@Example.COM")

        error = exc_info.value
        assert error.code == ErrorCode.DUPLICATE_USER_EMAIL
        assert dict(error.context) == {"resource": "user", "field": "email"}
        assert creds.hasher.hash_calls == 2  # dummy hash at start + one registration
        assert await creds.sql_scalar("SELECT count(*) FROM users") == 1

    async def test_registration_emits_one_event_with_the_subject_id_only(self, creds):
        registered = await creds.register()

        assert len(creds.events.events) == 1
        event = creds.events.events[0]
        assert event.name == "auth.user_registered"
        assert dict(event.context) == {"subject_id": str(registered.id)}

    async def test_replaces_a_stale_hash_after_a_successful_login(self, creds):
        await creds.register()
        before = await creds.password_hash()
        newer = _hasher(time_cost=2)
        service = await creds.throttled_for(newer)

        await creds.login(service=service)
        after = await creds.password_hash()
        await creds.login(service=service)
        after_again = await creds.password_hash()

        assert "t=1" in before
        assert after != before
        assert "m=8,t=2,p=1" in after
        assert after_again == after  # a current hash is not rewritten

    async def test_a_failed_login_never_rehashes(self, creds):
        await creds.register()
        before = await creds.password_hash()
        service = await creds.throttled_for(_hasher(time_cost=2))

        error = await _failure(creds.login(password=WRONG, service=service))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert await creds.password_hash() == before

    async def test_registration_and_login_share_password_normalization(self, creds):
        registered = await creds.register(password="  Ｐass word 1  ")

        identity = await creds.login(password="Pass word 1")

        assert identity == Identity(subject_id=registered.id)

    async def test_the_unique_index_decides_a_concurrent_duplicate_registration(
        self, creds
    ):
        results = await asyncio.gather(
            creds.register(email="race@example.com"),
            creds.register(email="RACE@example.com"),
            return_exceptions=True,
        )

        winners = [r for r in results if isinstance(r, RegisteredUser)]
        losers = [r for r in results if isinstance(r, AppError)]
        assert len(winners) == 1
        assert len(losers) == 1
        assert losers[0].code == ErrorCode.DUPLICATE_USER_EMAIL
        assert dict(losers[0].context) == {"resource": "user", "field": "email"}
        assert await creds.sql_scalar("SELECT count(*) FROM users") == 1


@pytest.mark.integration
class TestIndistinguishableFailures:
    async def test_every_failure_cause_gives_the_same_error(
        self, creds, postgres_user_repo
    ):
        await creds.register(email="active@example.com")
        off = await creds.register(email="off@example.com")
        await postgres_user_repo.set_active(off.id, False)

        unknown = await _failure(creds.login(email="nobody@example.com"))
        wrong = await _failure(creds.login(email="active@example.com", password=WRONG))
        disabled = await _failure(creds.login(email="off@example.com"))
        oversized = await _failure(
            creds.login(
                email="active@example.com", password="a" * (MAX_PASSWORD_LENGTH + 1)
            )
        )

        errors = [unknown, wrong, disabled, oversized]
        assert {e.code for e in errors} == {ErrorCode.AUTH_INVALID_CREDENTIALS}
        assert all(dict(e.context) == {} for e in errors)
        assert len({repr(e) for e in errors}) == 1

    async def test_an_unknown_email_costs_a_verify_against_the_dummy_hash(self, creds):
        creds.hasher.verify_calls.clear()

        await _failure(creds.login(email="nobody@example.com"))

        assert creds.hasher.verify_calls == [creds.inner._dummy_hash]

    async def test_a_disabled_user_with_the_right_password_is_verified_then_refused(
        self, creds, postgres_user_repo
    ):
        user = await creds.register()
        stored = await creds.password_hash()
        await postgres_user_repo.set_active(user.id, False)
        creds.hasher.verify_calls.clear()

        error = await _failure(creds.login())

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert creds.hasher.verify_calls == [stored]

    async def test_reactivating_a_user_restores_login(self, creds, postgres_user_repo):
        user = await creds.register()
        await postgres_user_repo.set_active(user.id, False)
        await _failure(creds.login())

        await postgres_user_repo.set_active(user.id, True)

        assert (await creds.login()).subject_id == user.id

    async def test_over_limit_input_never_reaches_storage_or_the_hasher(self, creds):
        creds.hasher.verify_calls.clear()

        await _failure(creds.login(password="a" * (MAX_PASSWORD_LENGTH + 1)))
        await _failure(creds.login(password="   "))

        assert creds.hasher.verify_calls == []


@pytest.mark.integration
class TestThrottlingOnPostgres:
    async def test_throttles_at_the_limit_even_for_the_correct_password(self, creds):
        await creds.register()
        await creds.fail(MAX_FAILURES, password=WRONG)
        creds.hasher.verify_calls.clear()

        error = await _failure(creds.login())  # correct password

        assert error.code == ErrorCode.AUTH_THROTTLED
        assert dict(error.context) == {"retry_after_seconds": str(WINDOW)}
        assert creds.hasher.verify_calls == []  # throttled attempts cost no hash

    async def test_a_throttled_attempt_is_not_recorded(self, creds):
        await creds.register()
        await creds.fail(MAX_FAILURES, password=WRONG)

        await _failure(creds.login())
        await _failure(creds.login())

        assert await creds.sql_scalar("SELECT count(*) FROM login_attempts") == (
            MAX_FAILURES
        )

    async def test_known_and_unknown_emails_are_throttled_identically(self, creds):
        await creds.register()
        unknown = "nobody@example.com"
        await creds.fail(MAX_FAILURES, password=WRONG)
        await creds.fail(MAX_FAILURES, email=unknown)
        creds.hasher.verify_calls.clear()

        known_error = await _failure(creds.login(password=WRONG))
        unknown_error = await _failure(creds.login(email=unknown))

        assert known_error.code == ErrorCode.AUTH_THROTTLED
        assert repr(known_error) == repr(unknown_error)
        assert creds.hasher.verify_calls == []

    async def test_a_failure_exactly_one_window_old_still_counts(self, creds):
        user = await creds.register()
        await creds.fail(MAX_FAILURES, password=WRONG)

        creds.clock.advance(timedelta(seconds=WINDOW))
        at_boundary = await _failure(creds.login())
        creds.clock.advance(timedelta(seconds=1))
        identity = await creds.login()

        assert (
            at_boundary.code == ErrorCode.AUTH_THROTTLED
        )  # count_failures is inclusive
        assert identity.subject_id == user.id

    async def test_never_locks_the_account(self, creds):
        user = await creds.register()
        await creds.fail(MAX_FAILURES, password=WRONG)
        await _failure(creds.login())

        from_other_ip = await creds.login(ip=OTHER_IP)

        assert from_other_ip.subject_id == user.id

    async def test_a_success_clears_only_its_own_ip_and_email_pair(self, creds):
        user = await creds.register()
        await creds.register(email="bob@example.com")
        await creds.fail(2, password=WRONG)
        await creds.fail(2, password=WRONG, ip=OTHER_IP)
        await creds.fail(2, email="bob@example.com", password=WRONG)

        identity = await creds.login()

        assert identity.subject_id == user.id
        assert await creds.count() == 0
        assert await creds.count(ip=OTHER_IP) == 2
        assert await creds.count(email="bob@example.com") == 2

    async def test_recording_a_failure_purges_rows_older_than_the_window(self, creds):
        await creds.attempts.record_failure(
            ip=OTHER_IP, email="old@example.com", at=creds.clock.now()
        )
        creds.clock.advance(timedelta(seconds=WINDOW + 1))

        await _failure(creds.login(email="nobody@example.com"))

        remaining = await creds.attempts.count_failures(
            ip=OTHER_IP,
            email="old@example.com",
            since=creds.clock.now() - timedelta(days=1),
        )
        assert remaining == 0
        assert await creds.count(email="nobody@example.com") == 1

    async def test_stores_the_normalized_email_and_unknown_for_a_missing_ip(
        self, creds
    ):
        await _failure(creds.login(email="  Ghost@Example.COM ", ip=None))

        row_ip = await creds.sql_scalar("SELECT ip FROM login_attempts")
        row_key = await creds.sql_scalar("SELECT email_key FROM login_attempts")

        assert (row_ip, row_key) == ("unknown", "ghost@example.com")

    async def test_emits_one_event_per_throttled_attempt_and_none_for_failures(
        self, creds
    ):
        await creds.register()
        creds.events.events.clear()
        await creds.fail(MAX_FAILURES, password=WRONG)
        assert creds.events.events == []

        await _failure(creds.login())

        assert [e.name for e in creds.events.events] == ["auth.login_throttled"]
        assert dict(creds.events.events[0].context) == {
            "retry_after_seconds": str(WINDOW)
        }


class _Collector(logging.Handler):
    """Plain handler attached to the root logger.

    Used instead of caplog on purpose: caplog was seen to miss records from
    async tests under the session-scoped loop (see test_connection_logging),
    which would let a leak test pass by capturing nothing.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def text(self) -> str:
        return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in self.records)


@pytest.fixture
def collector():
    handler = _Collector()
    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


@pytest.mark.integration
class TestNothingLeaks:
    async def test_the_collector_sees_records(self, collector):
        logging.getLogger("trutina.m28.control").info("control-line")

        assert "control-line" in collector.text()

    async def test_no_password_or_hash_reaches_logs_errors_events_or_tables(
        self, creds, collector
    ):
        errors: list[AppError] = []

        await creds.register()
        hash_before = await creds.password_hash()

        # Rehash path: a login under a newer hasher rewrites the stored hash.
        service = await creds.throttled_for(_hasher(time_cost=2))
        await creds.login(service=service)
        hash_after = await creds.password_hash()

        errors.append(await _failure(creds.login(email="nobody@example.com")))
        for _ in range(MAX_FAILURES):
            errors.append(await _failure(creds.login(password=WRONG)))
        errors.append(await _failure(creds.login()))  # throttled
        creds.clock.advance(timedelta(seconds=WINDOW + 1))
        await creds.login(service=service)  # succeeds again, same hasher as the rehash
        hash_final = await creds.password_hash()

        secrets = [PASSWORD, WRONG]
        hashes = [hash_before, hash_after, hash_final]
        assert hash_before != hash_after  # the scenario really exercised a rehash

        blobs = {
            "logs": collector.text(),
            "errors": "\n".join(repr(e) + repr(dict(e.context)) for e in errors),
            "events": "\n".join(repr(e) for e in creds.events.events),
            "login_attempts": await creds.sql_dump("login_attempts"),
            "audit_events": await creds.sql_dump("audit_events"),
        }
        for name, blob in blobs.items():
            for secret in secrets + hashes:
                assert secret not in blob, f"{secret!r} leaked into {name}"

        users_dump = await creds.sql_dump("users")
        for secret in secrets:
            assert secret not in users_dump
        assert hash_final in users_dump  # the only place a hash may live
