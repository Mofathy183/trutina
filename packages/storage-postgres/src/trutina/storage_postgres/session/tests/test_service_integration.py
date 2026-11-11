"""The session service on real PostgreSQL (M3.4).

Wires the real ``SessionService`` to ``PostgresSessionRepo``,
``PostgresUserRepo`` and ``PostgresLoginAttemptRepo`` with a real Argon2id
hasher (cheapest parameters) and a real SHA-256 token hasher. Only the
clock and the event sink are fakes, so expiry and the touch interval are
deterministic.

It lives here, not in trutina-authentication, because it reads tables with
SQLAlchemy and authentication must never import storage. For the same
reason the log check uses a plain stdlib handler.

Closes, at service level, what the unit tests prove against fakes (R4). It
adds no behavior. Route-level proof belongs to M3.7 and M3.8.
"""

import asyncio
import logging
from datetime import timedelta

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from trutina.authentication import (
    Argon2PasswordHasher,
    ClientKind,
    IssuedSession,
    PasswordAuthenticator,
    RegisteredUser,
    RegisterInput,
    RegistrationService,
    SessionLifetime,
    SessionRecord,
    SessionService,
    Sha256SessionTokenHasher,
    ThrottledAuthenticator,
)
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.identity import PostgresUserRepo
from trutina.storage_postgres.login_attempt import PostgresLoginAttemptRepo
from trutina.storage_postgres.session import PostgresSessionRepo
from trutina.storage_postgres.shared.execution import PostgresExecutor

from tests.fakes import FakeAuthEventSink, FakeClock

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


class _Stack:
    """Real services over real repositories."""

    def __init__(self, users, attempts, sessions, engine) -> None:
        self.users = users
        self.sessions = sessions
        self.engine = engine
        self.clock = FakeClock()
        self.events = FakeAuthEventSink()
        self.token_hasher = Sha256SessionTokenHasher()
        # Cheapest parameters Argon2 accepts, so the suite stays fast.
        self.hasher = Argon2PasswordHasher(
            time_cost=1, memory_cost_kib=8, parallelism=1, max_concurrency=2
        )
        self.registration = RegistrationService(
            users=users, hasher=self.hasher, clock=self.clock, events=self.events
        )
        self.service: SessionService
        self.issued: list[IssuedSession] = []

    @classmethod
    async def create(cls, users, attempts, sessions, engine) -> _Stack:
        stack = cls(users, attempts, sessions, engine)
        inner = await PasswordAuthenticator.create(users=users, hasher=stack.hasher)
        throttled = ThrottledAuthenticator(
            inner=inner,
            attempts=attempts,
            clock=stack.clock,
            max_failures=MAX_FAILURES,
            window_seconds=WINDOW,
            events=stack.events,
        )
        stack.service = SessionService(
            sessions=sessions,
            users=users,
            authenticator=throttled,
            hasher=stack.token_hasher,
            clock=stack.clock,
            lifetimes=LIFETIMES,
            touch_interval=TOUCH,
            reauth_window=REAUTH,
            purge_retention=RETENTION,
            events=stack.events,
        )
        return stack

    async def register(
        self, email: str = EMAIL, password: str = PASSWORD
    ) -> RegisteredUser:
        return await self.registration.register(
            RegisterInput(email=email, password=SecretStr(password))
        )

    async def login(
        self, *, email: str = EMAIL, password: str = PASSWORD, kind: ClientKind = API
    ) -> IssuedSession:
        issued = await self.service.login(
            email=email, password=SecretStr(password), client_ip=IP, client_kind=kind
        )
        self.issued.append(issued)
        return issued

    async def validate(self, issued: IssuedSession, kind: ClientKind = API):
        return await self.service.validate(issued.token, client_kind=kind)

    def hash_of(self, issued: IssuedSession) -> str:
        return self.token_hasher.hash(issued.token)

    async def scalar(self, sql: str, **params):
        async with self.engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar_one()

    async def dump(self, table: str) -> str:
        async with self.engine.connect() as conn:
            result = await conn.execute(text(f"SELECT t::text FROM {table} t"))
            return "\n".join(result.scalars().all())


async def _failure(awaitable) -> AppError:
    with pytest.raises(AppError) as exc_info:
        await awaitable
    return exc_info.value


@pytest_asyncio.fixture
async def stack(
    postgres_user_repo,
    postgres_login_attempt_repo,
    postgres_session_repo,
    postgres_connection,
):
    return await _Stack.create(
        postgres_user_repo,
        postgres_login_attempt_repo,
        postgres_session_repo,
        postgres_connection.engine,
    )


@pytest_asyncio.fixture
async def one_connection_stack(clean_pg_db, test_settings):
    """Every repository shares an engine that can open exactly one connection.

    Any step that held a connection while asking for another, or while
    hashing, would wait out the pool timeout and fail.
    """
    engine = create_async_engine(
        test_settings.postgres.uri,
        pool_size=1,
        max_overflow=0,
        pool_timeout=5,
        hide_parameters=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    executor = PostgresExecutor()
    try:
        yield await _Stack.create(
            PostgresUserRepo(factory, executor),
            PostgresLoginAttemptRepo(factory, executor),
            PostgresSessionRepo(factory, executor),
            engine,
        )
    finally:
        await engine.dispose()


@pytest.mark.integration
class TestSessionLifecycleOnPostgres:
    async def test_login_validate_logout_then_the_token_is_rejected(self, stack):
        registered = await stack.register()

        issued = await stack.login()
        valid = await stack.validate(issued)
        await stack.service.logout(issued.token, client_kind=API)
        error = await _failure(stack.validate(issued))

        assert valid.session.user_id == registered.id
        assert error.code == ErrorCode.AUTH_TOKEN_INVALID
        assert dict(error.context) == {}

    async def test_stores_only_the_hash_of_the_token(self, stack):
        await stack.register()

        issued = await stack.login()
        raw = issued.token.get_secret_value()

        stored = await stack.scalar("SELECT token_hash FROM sessions")
        assert stored == stack.hash_of(issued)
        assert stored != raw
        for table in ("sessions", "users", "login_attempts", "audit_events"):
            assert raw not in await stack.dump(table)

    async def test_a_session_issued_for_one_kind_is_rejected_for_the_other(self, stack):
        await stack.register()
        api = await stack.login(kind=API)
        cli = await stack.login(kind=CLI)

        assert (await _failure(stack.validate(api, CLI))).code == (
            ErrorCode.AUTH_TOKEN_INVALID
        )
        assert (await _failure(stack.validate(cli, API))).code == (
            ErrorCode.AUTH_TOKEN_INVALID
        )

    async def test_records_a_use_when_the_touch_interval_has_passed(self, stack):
        await stack.register()
        issued = await stack.login()
        stack.clock.advance(TOUCH)

        await stack.validate(issued)

        h = stack.hash_of(issued)
        sql = "SELECT {} FROM sessions WHERE token_hash = :h"
        assert await stack.scalar(sql.format("last_used_at"), h=h) == stack.clock.now()
        assert await stack.scalar(sql.format("idle_expires_at"), h=h) == (
            stack.clock.now() + timedelta(hours=24)
        )

    async def test_concurrent_validations_with_a_due_touch_never_error(self, stack):
        await stack.register()
        issued = await stack.login()
        stack.clock.advance(TOUCH + timedelta(seconds=1))

        results = await asyncio.gather(*(stack.validate(issued) for _ in range(8)))

        assert len(results) == 8
        last_used = await stack.scalar(
            "SELECT last_used_at FROM sessions WHERE token_hash = :h",
            h=stack.hash_of(issued),
        )
        assert last_used == stack.clock.now()

    async def test_reauthentication_refreshes_the_check_and_keeps_the_token(
        self, stack
    ):
        await stack.register()
        issued = await stack.login()
        stack.clock.advance(timedelta(minutes=40))
        with pytest.raises(AppError) as stale:
            stack.service.require_recent_auth(await stack.validate(issued))
        assert stale.value.code == ErrorCode.AUTH_REAUTH_REQUIRED

        await stack.service.reauthenticate(
            issued.token,
            client_kind=API,
            password=SecretStr(PASSWORD),
            client_ip=IP,
        )

        stack_hash = stack.hash_of(issued)
        assert await stack.scalar("SELECT count(*) FROM sessions") == 1
        assert (
            await stack.scalar(
                "SELECT authenticated_at FROM sessions WHERE token_hash = :h",
                h=stack_hash,
            )
            == stack.clock.now()
        )
        stack.service.require_recent_auth(await stack.validate(issued))

    async def test_a_wrong_password_leaves_the_session_valid_and_unchanged(self, stack):
        await stack.register()
        issued = await stack.login()
        before = await stack.scalar("SELECT authenticated_at FROM sessions")
        stack.clock.advance(timedelta(minutes=40))

        error = await _failure(
            stack.service.reauthenticate(
                issued.token,
                client_kind=API,
                password=SecretStr(WRONG),
                client_ip=IP,
            )
        )

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert await stack.scalar("SELECT authenticated_at FROM sessions") == before
        await stack.validate(issued)

    async def test_deactivating_the_user_ends_validation_at_once(self, stack):
        registered = await stack.register()
        issued = await stack.login()

        await stack.users.set_active(registered.id, False)

        assert (await _failure(stack.validate(issued))).code == (
            ErrorCode.AUTH_TOKEN_INVALID
        )

    async def test_revoke_all_ends_every_session_of_the_user(self, stack):
        registered = await stack.register()
        await stack.login()
        await stack.login(kind=CLI)

        await stack.service.revoke_all_for_user(registered.id)

        assert (
            await stack.scalar("SELECT count(*) FROM sessions WHERE revoked_at IS NULL")
            == 0
        )

    async def test_login_deletes_sessions_dead_longer_than_the_retention_window(
        self, stack
    ):
        registered = await stack.register()
        now = stack.clock.now()
        await stack.sessions.create(
            SessionRecord(
                token_hash="dead-hash",
                user_id=registered.id,
                client_kind=API,
                created_at=now - timedelta(days=40),
                last_used_at=now - timedelta(days=40),
                authenticated_at=now - timedelta(days=40),
                idle_expires_at=now - timedelta(days=30),
                absolute_expires_at=now - timedelta(days=33),
            )
        )

        await stack.login()

        assert (
            await stack.scalar(
                "SELECT count(*) FROM sessions WHERE token_hash = 'dead-hash'"
            )
            == 0
        )
        assert await stack.scalar("SELECT count(*) FROM sessions") == 1


@pytest.mark.integration
class TestSessionServiceConnectionUse:
    async def test_the_whole_flow_completes_on_a_one_connection_pool(
        self, one_connection_stack
    ):
        s = one_connection_stack
        await s.register()

        issued = await s.login()
        s.clock.advance(TOUCH)
        results = await asyncio.gather(*(s.validate(issued) for _ in range(8)))
        s.clock.advance(REAUTH)
        await s.service.reauthenticate(
            issued.token, client_kind=API, password=SecretStr(PASSWORD), client_ip=IP
        )
        await s.service.logout(issued.token, client_kind=API)
        error = await _failure(s.validate(issued))

        assert all(r.session.client_kind is API for r in results)
        assert error.code == ErrorCode.AUTH_TOKEN_INVALID


class _Collector(logging.Handler):
    """Plain handler on the root logger, used instead of caplog on purpose.

    caplog was seen to miss records from async tests under the
    session-scoped loop, which would let a leak test pass by capturing
    nothing.
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
        logging.getLogger("trutina.m34.control").info("control-line")

        assert "control-line" in collector.text()

    async def test_no_raw_token_reaches_logs_errors_events_or_tables(
        self, stack, collector
    ):
        errors: list[AppError] = []
        await stack.register()

        issued = await stack.login()
        await stack.validate(issued)
        errors.append(await _failure(stack.validate(issued, CLI)))
        errors.append(
            await _failure(
                stack.service.reauthenticate(
                    issued.token,
                    client_kind=API,
                    password=SecretStr(WRONG),
                    client_ip=IP,
                )
            )
        )
        await stack.service.logout(issued.token, client_kind=API)
        errors.append(await _failure(stack.validate(issued)))

        blobs = {
            "logs": collector.text(),
            "errors": "\n".join(repr(e) + repr(dict(e.context)) for e in errors),
            "events": "\n".join(repr(e) for e in stack.events.events),
            "users": await stack.dump("users"),
            "login_attempts": await stack.dump("login_attempts"),
            "audit_events": await stack.dump("audit_events"),
            "sessions": await stack.dump("sessions"),
        }
        for name, blob in blobs.items():
            for issued_session in stack.issued:
                raw = issued_session.token.get_secret_value()
                assert raw not in blob, f"raw token leaked into {name}"
