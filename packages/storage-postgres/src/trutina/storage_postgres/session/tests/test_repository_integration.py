import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from trutina.authentication import AccessState, ClientKind, SessionRecord
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.session import PostgresSessionRepo
from trutina.storage_postgres.shared.execution import PostgresExecutor

from tests.factories import make_user

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
IDLE = NOW + timedelta(days=1)
ABSOLUTE = NOW + timedelta(days=7)


def _record(
    token_hash: str = "h1",
    *,
    user_id: UUID,
    kind: ClientKind = ClientKind.API,
    last_used_at: datetime = NOW,
    authenticated_at: datetime = NOW,
    idle_expires_at: datetime = IDLE,
    absolute_expires_at: datetime = ABSOLUTE,
    revoked_at: datetime | None = None,
) -> SessionRecord:
    return SessionRecord(
        token_hash=token_hash,
        user_id=user_id,
        client_kind=kind,
        created_at=NOW,
        last_used_at=last_used_at,
        authenticated_at=authenticated_at,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
        revoked_at=revoked_at,
    )


async def _make_user(
    users, *, email: str = "ann@example.com", is_active: bool = True
) -> UUID:
    user = make_user(email=email, is_active=is_active)
    await users.create(user)
    return user.id


async def _stored(connection, token_hash: str):
    async with connection.engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM sessions WHERE token_hash = :h"), {"h": token_hash}
        )
        return result.mappings().one()


async def _count(connection) -> int:
    async with connection.engine.connect() as conn:
        return (await conn.execute(text("SELECT count(*) FROM sessions"))).scalar_one()


@pytest.mark.integration
class TestPostgresSessionRepoCreate:
    async def test_stores_a_session_that_get_valid_returns_unchanged(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        record = _record(user_id=user_id)

        await postgres_session_repo.create(record)
        result = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=NOW
        )

        assert result is not None
        assert result.session == record
        assert result.session.created_at.tzinfo is not None
        assert result.access == AccessState(is_active=True)

    async def test_rejects_a_duplicate_token_hash(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record("secret-hash", user_id=user_id))

        with pytest.raises(AppError) as exc_info:
            await postgres_session_repo.create(_record("secret-hash", user_id=user_id))

        error = exc_info.value
        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert dict(error.context) == {
            "resource": "session",
            "constraint": "uq_sessions_token_hash",
        }
        assert await _count(postgres_connection) == 1

    async def test_duplicate_error_carries_no_driver_exception_or_token_hash(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record("secret-hash", user_id=user_id))

        with pytest.raises(AppError) as exc_info:
            await postgres_session_repo.create(_record("secret-hash", user_id=user_id))

        error = exc_info.value
        assert error.cause is None
        assert error.__cause__ is None
        assert error.__context__ is None
        assert "secret-hash" not in repr(error)
        assert "secret-hash" not in str(dict(error.context))

    async def test_rejects_a_session_for_an_unknown_user(
        self, postgres_session_repo, postgres_connection
    ):
        with pytest.raises(AppError) as exc_info:
            await postgres_session_repo.create(_record(user_id=uuid4()))

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert exc_info.value.context["constraint"] == "fk_sessions_user_id_users"
        assert exc_info.value.cause is None
        assert await _count(postgres_connection) == 0

    async def test_a_user_with_sessions_cannot_be_deleted(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))

        with pytest.raises(IntegrityError):
            async with postgres_connection.engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": user_id}
                )


@pytest.mark.integration
class TestPostgresSessionRepoGetValid:
    async def test_returns_none_for_an_unknown_hash(self, postgres_session_repo):
        result = await postgres_session_repo.get_valid(
            "missing", client_kind=ClientKind.API, now=NOW
        )

        assert result is None

    @pytest.mark.parametrize(
        ("issued", "asked"),
        [(ClientKind.API, ClientKind.CLI), (ClientKind.CLI, ClientKind.API)],
    )
    async def test_returns_none_for_the_other_client_kind(
        self, postgres_session_repo, postgres_user_repo, issued, asked
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id, kind=issued))

        result = await postgres_session_repo.get_valid("h1", client_kind=asked, now=NOW)

        assert result is None

    async def test_returns_none_for_a_revoked_session(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id, revoked_at=NOW))

        result = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=NOW
        )

        assert result is None

    async def test_idle_expiry_is_exclusive(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        expiry = NOW + timedelta(hours=1)
        await postgres_session_repo.create(
            _record(user_id=user_id, idle_expires_at=expiry)
        )

        at_expiry = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry
        )
        just_before = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry - timedelta(seconds=1)
        )

        assert at_expiry is None
        assert just_before is not None

    async def test_absolute_expiry_is_exclusive(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        expiry = NOW + timedelta(hours=1)
        await postgres_session_repo.create(
            _record(
                user_id=user_id,
                idle_expires_at=NOW + timedelta(days=30),
                absolute_expires_at=expiry,
            )
        )

        at_expiry = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry
        )
        just_before = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry - timedelta(seconds=1)
        )

        assert at_expiry is None
        assert just_before is not None

    async def test_returns_none_for_an_inactive_user(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo, is_active=False)
        await postgres_session_repo.create(_record(user_id=user_id))

        result = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=NOW
        )

        assert result is None

    async def test_returns_none_once_the_user_is_deactivated(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        await postgres_user_repo.set_active(user_id, False)

        result = await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=NOW
        )

        assert result is None

    async def test_never_writes(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        before = await _stored(postgres_connection, "h1")

        await postgres_session_repo.get_valid(
            "h1", client_kind=ClientKind.API, now=NOW + timedelta(hours=1)
        )
        after = await _stored(postgres_connection, "h1")

        assert dict(after) == dict(before)


@pytest.mark.integration
class TestPostgresSessionRepoTouch:
    async def test_advances_last_use_and_idle_expiry(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        later = NOW + timedelta(hours=2)

        await postgres_session_repo.touch(
            "h1", now=later, idle_expires_at=later + timedelta(days=1)
        )

        stored = await _stored(postgres_connection, "h1")
        assert stored["last_used_at"] == later
        assert stored["idle_expires_at"] == later + timedelta(days=1)

    async def test_never_moves_either_value_backward(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(
            _record(user_id=user_id, last_used_at=NOW + timedelta(hours=2))
        )

        await postgres_session_repo.touch(
            "h1", now=NOW, idle_expires_at=NOW + timedelta(hours=1)
        )

        stored = await _stored(postgres_connection, "h1")
        assert stored["last_used_at"] == NOW + timedelta(hours=2)
        assert stored["idle_expires_at"] == IDLE

    async def test_ignores_an_unknown_hash(self, postgres_session_repo):
        await postgres_session_repo.touch("missing", now=NOW, idle_expires_at=IDLE)

    async def test_leaves_a_revoked_session_unchanged(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id, revoked_at=NOW))
        before = await _stored(postgres_connection, "h1")

        await postgres_session_repo.touch(
            "h1", now=NOW + timedelta(hours=1), idle_expires_at=ABSOLUTE
        )

        assert dict(await _stored(postgres_connection, "h1")) == dict(before)

    async def test_concurrent_touches_keep_the_latest_values(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        minutes = [5, 1, 9, 3, 7, 2, 8, 4, 6, 10]

        await asyncio.gather(
            *(
                postgres_session_repo.touch(
                    "h1",
                    now=NOW + timedelta(minutes=m),
                    idle_expires_at=IDLE + timedelta(minutes=m),
                )
                for m in minutes
            )
        )

        stored = await _stored(postgres_connection, "h1")
        assert stored["last_used_at"] == NOW + timedelta(minutes=10)
        assert stored["idle_expires_at"] == IDLE + timedelta(minutes=10)


@pytest.mark.integration
class TestPostgresSessionRepoMarkReauthenticated:
    async def test_sets_authenticated_at(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        later = NOW + timedelta(minutes=10)

        await postgres_session_repo.mark_reauthenticated("h1", now=later)

        assert (await _stored(postgres_connection, "h1"))["authenticated_at"] == later

    async def test_never_moves_authenticated_at_backward(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        recent = NOW + timedelta(hours=1)
        await postgres_session_repo.create(
            _record(user_id=user_id, authenticated_at=recent)
        )

        await postgres_session_repo.mark_reauthenticated("h1", now=NOW)

        assert (await _stored(postgres_connection, "h1"))["authenticated_at"] == recent

    async def test_ignores_unknown_and_revoked_sessions(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id, revoked_at=NOW))
        before = await _stored(postgres_connection, "h1")

        await postgres_session_repo.mark_reauthenticated("missing", now=NOW)
        await postgres_session_repo.mark_reauthenticated(
            "h1", now=NOW + timedelta(hours=1)
        )

        assert dict(await _stored(postgres_connection, "h1")) == dict(before)


@pytest.mark.integration
class TestPostgresSessionRepoRevoke:
    async def test_marks_the_session_revoked(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))

        await postgres_session_repo.revoke("h1", now=NOW)

        assert (await _stored(postgres_connection, "h1"))["revoked_at"] == NOW
        assert (
            await postgres_session_repo.get_valid(
                "h1", client_kind=ClientKind.API, now=NOW
            )
            is None
        )

    async def test_is_idempotent_and_keeps_the_first_revocation_time(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))
        await postgres_session_repo.revoke("h1", now=NOW)

        await postgres_session_repo.revoke("h1", now=NOW + timedelta(hours=1))

        assert (await _stored(postgres_connection, "h1"))["revoked_at"] == NOW

    async def test_ignores_an_unknown_hash(self, postgres_session_repo):
        await postgres_session_repo.revoke("missing", now=NOW)

    async def test_revoke_all_for_user_affects_only_that_user(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        other_id = await _make_user(postgres_user_repo, email="bob@example.com")
        await postgres_session_repo.create(_record("a", user_id=user_id))
        await postgres_session_repo.create(_record("b", user_id=user_id))
        await postgres_session_repo.create(_record("c", user_id=other_id))

        await postgres_session_repo.revoke_all_for_user(user_id, now=NOW)

        assert (await _stored(postgres_connection, "a"))["revoked_at"] == NOW
        assert (await _stored(postgres_connection, "b"))["revoked_at"] == NOW
        assert (await _stored(postgres_connection, "c"))["revoked_at"] is None

    async def test_revoke_all_for_user_keeps_an_earlier_revocation_time(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        earlier = NOW - timedelta(hours=1)
        await postgres_session_repo.create(_record(user_id=user_id, revoked_at=earlier))

        await postgres_session_repo.revoke_all_for_user(user_id, now=NOW)

        assert (await _stored(postgres_connection, "h1"))["revoked_at"] == earlier


@pytest.mark.integration
class TestPostgresSessionRepoPurgeBefore:
    async def test_removes_only_dead_sessions_and_returns_the_count(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        repo = postgres_session_repo
        await repo.create(
            _record("idle", user_id=user_id, idle_expires_at=NOW - timedelta(days=2))
        )
        await repo.create(
            _record(
                "absolute",
                user_id=user_id,
                absolute_expires_at=NOW - timedelta(days=2),
            )
        )
        await repo.create(
            _record("revoked", user_id=user_id, revoked_at=NOW - timedelta(days=3))
        )
        await repo.create(
            _record(
                "recently-revoked",
                user_id=user_id,
                revoked_at=NOW - timedelta(hours=1),
            )
        )
        await repo.create(_record("live", user_id=user_id))

        removed = await repo.purge_before(NOW - timedelta(days=1))

        assert removed == 3
        assert await _count(postgres_connection) == 2
        assert (
            await repo.get_valid("live", client_kind=ClientKind.API, now=NOW)
            is not None
        )

    async def test_keeps_a_session_that_died_exactly_at_the_cutoff(
        self, postgres_session_repo, postgres_user_repo
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(
            _record(user_id=user_id, idle_expires_at=IDLE)
        )

        kept = await postgres_session_repo.purge_before(IDLE)
        removed = await postgres_session_repo.purge_before(IDLE + timedelta(seconds=1))

        assert (kept, removed) == (0, 1)

    async def test_never_removes_a_session_that_is_still_live_at_the_cutoff(
        self, postgres_session_repo, postgres_user_repo, postgres_connection
    ):
        user_id = await _make_user(postgres_user_repo)
        await postgres_session_repo.create(_record(user_id=user_id))

        removed = await postgres_session_repo.purge_before(NOW)

        assert removed == 0
        assert await _count(postgres_connection) == 1

    async def test_returns_zero_when_there_are_no_sessions(self, postgres_session_repo):
        assert await postgres_session_repo.purge_before(NOW) == 0


@pytest_asyncio.fixture
async def single_connection_session_repo(clean_pg_db, test_settings):
    """A repo whose engine can open exactly one connection.

    Any method that held a connection while asking for a second would
    wait out pool_timeout and then fail. Built here, not from
    connect(), because PostgresSettings.pool_timeout_s is not wired.
    """
    engine = create_async_engine(
        test_settings.postgres.uri,
        pool_size=1,
        max_overflow=0,
        pool_timeout=5,
        hide_parameters=True,
    )
    try:
        yield PostgresSessionRepo(
            async_sessionmaker(engine, expire_on_commit=False), PostgresExecutor()
        )
    finally:
        await engine.dispose()


@pytest.mark.integration
class TestPostgresSessionRepoConnectionUse:
    async def test_every_method_completes_on_a_one_connection_pool(
        self, single_connection_session_repo, postgres_user_repo
    ):
        repo = single_connection_session_repo
        user_id = await _make_user(postgres_user_repo)

        await repo.create(_record(user_id=user_id))
        found = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)
        await repo.touch("h1", now=NOW, idle_expires_at=IDLE)
        await repo.mark_reauthenticated("h1", now=NOW)
        await repo.revoke_all_for_user(user_id, now=NOW)
        await repo.revoke("h1", now=NOW)
        removed = await repo.purge_before(NOW + timedelta(days=30))

        assert found is not None
        assert removed == 1

    async def test_more_concurrent_lookups_than_the_pool_size_complete(
        self, single_connection_session_repo, postgres_user_repo
    ):
        repo = single_connection_session_repo
        user_id = await _make_user(postgres_user_repo)
        await repo.create(_record(user_id=user_id))

        results = await asyncio.gather(
            *(
                repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)
                for _ in range(8)
            )
        )

        assert all(result is not None for result in results)
