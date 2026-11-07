from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from trutina.authentication import AccessState, ClientKind, SessionRecord

from tests.factories import make_user
from tests.fakes import FakeSessionRepo, FakeSessionTokenHasher, FakeUserRepo

NOW = datetime(2025, 1, 1, tzinfo=UTC)
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


async def _setup(
    *, is_active: bool = True
) -> tuple[FakeSessionRepo, FakeUserRepo, UUID]:
    users = FakeUserRepo()
    user = make_user(is_active=is_active)
    await users.create(user)
    return FakeSessionRepo(users), users, user.id


@pytest.mark.unit
class TestFakeSessionTokenHasher:
    def test_is_deterministic(self):
        hasher = FakeSessionTokenHasher()

        assert hasher.hash(SecretStr("t")) == hasher.hash(SecretStr("t"))

    def test_different_tokens_hash_differently(self):
        hasher = FakeSessionTokenHasher()

        assert hasher.hash(SecretStr("a")) != hasher.hash(SecretStr("b"))


@pytest.mark.unit
class TestFakeSessionRepoGetValid:
    async def test_returns_a_live_session_with_its_access_state(self):
        repo, _, user_id = await _setup()
        record = _record(user_id=user_id)
        await repo.create(record)

        result = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)

        assert result is not None
        assert result.session == record
        assert result.access == AccessState(is_active=True)

    async def test_returns_none_for_an_unknown_hash(self):
        repo, _, _ = await _setup()

        result = await repo.get_valid("missing", client_kind=ClientKind.API, now=NOW)

        assert result is None

    @pytest.mark.parametrize(
        ("issued", "asked"),
        [(ClientKind.API, ClientKind.CLI), (ClientKind.CLI, ClientKind.API)],
    )
    async def test_returns_none_for_the_other_client_kind(self, issued, asked):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id, kind=issued))

        result = await repo.get_valid("h1", client_kind=asked, now=NOW)

        assert result is None

    async def test_returns_none_for_a_revoked_session(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id, revoked_at=NOW))

        result = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)

        assert result is None

    async def test_idle_expiry_is_exclusive(self):
        repo, _, user_id = await _setup()
        expiry = NOW + timedelta(hours=1)
        await repo.create(_record(user_id=user_id, idle_expires_at=expiry))

        at_expiry = await repo.get_valid("h1", client_kind=ClientKind.API, now=expiry)
        just_before = await repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry - timedelta(seconds=1)
        )

        assert at_expiry is None
        assert just_before is not None

    async def test_absolute_expiry_is_exclusive(self):
        repo, _, user_id = await _setup()
        expiry = NOW + timedelta(hours=1)
        await repo.create(
            _record(
                user_id=user_id,
                idle_expires_at=NOW + timedelta(days=30),
                absolute_expires_at=expiry,
            )
        )

        at_expiry = await repo.get_valid("h1", client_kind=ClientKind.API, now=expiry)
        just_before = await repo.get_valid(
            "h1", client_kind=ClientKind.API, now=expiry - timedelta(seconds=1)
        )

        assert at_expiry is None
        assert just_before is not None

    async def test_returns_none_for_an_inactive_user(self):
        repo, _, user_id = await _setup(is_active=False)
        await repo.create(_record(user_id=user_id))

        result = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)

        assert result is None

    async def test_returns_none_once_the_user_is_deactivated(self):
        repo, users, user_id = await _setup()
        await repo.create(_record(user_id=user_id))
        await users.set_active(user_id, False)

        result = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)

        assert result is None

    async def test_returns_none_when_the_user_does_not_exist(self):
        repo, _, _ = await _setup()
        await repo.create(_record(user_id=uuid4()))

        result = await repo.get_valid("h1", client_kind=ClientKind.API, now=NOW)

        assert result is None


@pytest.mark.unit
class TestFakeSessionRepoTouch:
    async def test_advances_last_use_and_idle_expiry(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id))
        later = NOW + timedelta(hours=2)

        await repo.touch("h1", now=later, idle_expires_at=later + timedelta(days=1))

        stored = repo.get("h1")
        assert stored is not None
        assert stored.last_used_at == later
        assert stored.idle_expires_at == later + timedelta(days=1)

    async def test_never_moves_either_value_backward(self):
        repo, _, user_id = await _setup()
        await repo.create(
            _record(user_id=user_id, last_used_at=NOW + timedelta(hours=2))
        )

        await repo.touch("h1", now=NOW, idle_expires_at=NOW + timedelta(hours=1))

        stored = repo.get("h1")
        assert stored is not None
        assert stored.last_used_at == NOW + timedelta(hours=2)
        assert stored.idle_expires_at == IDLE

    async def test_ignores_an_unknown_hash(self):
        repo, _, _ = await _setup()

        await repo.touch("missing", now=NOW, idle_expires_at=IDLE)

        assert repo.get("missing") is None

    async def test_leaves_a_revoked_session_unchanged(self):
        repo, _, user_id = await _setup()
        record = _record(user_id=user_id, revoked_at=NOW)
        await repo.create(record)

        await repo.touch("h1", now=NOW + timedelta(hours=1), idle_expires_at=ABSOLUTE)

        assert repo.get("h1") == record


@pytest.mark.unit
class TestFakeSessionRepoMarkReauthenticated:
    async def test_sets_authenticated_at(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id))
        later = NOW + timedelta(minutes=10)

        await repo.mark_reauthenticated("h1", now=later)

        stored = repo.get("h1")
        assert stored is not None
        assert stored.authenticated_at == later

    async def test_never_moves_authenticated_at_backward(self):
        repo, _, user_id = await _setup()
        recent = NOW + timedelta(hours=1)
        await repo.create(_record(user_id=user_id, authenticated_at=recent))

        await repo.mark_reauthenticated("h1", now=NOW)

        stored = repo.get("h1")
        assert stored is not None
        assert stored.authenticated_at == recent

    async def test_ignores_unknown_and_revoked_sessions(self):
        repo, _, user_id = await _setup()
        record = _record(user_id=user_id, revoked_at=NOW)
        await repo.create(record)

        await repo.mark_reauthenticated("missing", now=NOW)
        await repo.mark_reauthenticated("h1", now=NOW + timedelta(hours=1))

        assert repo.get("h1") == record


@pytest.mark.unit
class TestFakeSessionRepoRevoke:
    async def test_marks_the_session_revoked(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id))

        await repo.revoke("h1", now=NOW)

        stored = repo.get("h1")
        assert stored is not None
        assert stored.revoked_at == NOW

    async def test_is_idempotent_and_keeps_the_first_revocation_time(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id))
        await repo.revoke("h1", now=NOW)

        await repo.revoke("h1", now=NOW + timedelta(hours=1))

        stored = repo.get("h1")
        assert stored is not None
        assert stored.revoked_at == NOW

    async def test_ignores_an_unknown_hash(self):
        repo, _, _ = await _setup()

        await repo.revoke("missing", now=NOW)

        assert repo.get("missing") is None

    async def test_revoke_all_for_user_affects_only_that_user(self):
        repo, users, user_id = await _setup()
        other = make_user(email="bob@example.com")
        await users.create(other)
        await repo.create(_record("a", user_id=user_id))
        await repo.create(_record("b", user_id=user_id))
        await repo.create(_record("c", user_id=other.id))

        await repo.revoke_all_for_user(user_id, now=NOW)

        a, b, c = repo.get("a"), repo.get("b"), repo.get("c")
        assert a is not None and a.revoked_at == NOW
        assert b is not None and b.revoked_at == NOW
        assert c is not None and c.revoked_at is None

    async def test_revoke_all_for_user_keeps_an_earlier_revocation_time(self):
        repo, _, user_id = await _setup()
        earlier = NOW - timedelta(hours=1)
        await repo.create(_record(user_id=user_id, revoked_at=earlier))

        await repo.revoke_all_for_user(user_id, now=NOW)

        stored = repo.get("h1")
        assert stored is not None
        assert stored.revoked_at == earlier


@pytest.mark.unit
class TestFakeSessionRepoPurgeBefore:
    async def test_removes_only_dead_sessions_and_returns_the_count(self):
        repo, _, user_id = await _setup()
        await repo.create(
            _record("expired", user_id=user_id, idle_expires_at=NOW - timedelta(days=2))
        )
        await repo.create(
            _record("revoked", user_id=user_id, revoked_at=NOW - timedelta(days=3))
        )
        await repo.create(_record("live", user_id=user_id))

        removed = await repo.purge_before(NOW - timedelta(days=1))

        assert removed == 2
        assert repo.get("expired") is None
        assert repo.get("revoked") is None
        assert repo.get("live") is not None

    async def test_keeps_a_session_that_died_exactly_at_the_cutoff(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id, idle_expires_at=IDLE))

        kept = await repo.purge_before(IDLE)
        removed = await repo.purge_before(IDLE + timedelta(seconds=1))

        assert kept == 0
        assert removed == 1
        assert repo.get("h1") is None

    async def test_never_removes_a_session_that_is_still_live_at_the_cutoff(self):
        repo, _, user_id = await _setup()
        await repo.create(_record(user_id=user_id))

        removed = await repo.purge_before(NOW)

        assert removed == 0
        assert repo.get("h1") is not None
