import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from trutina.authentication import Identity, RefreshTokenRecord, RotationOutcome

from tests.fakes import (
    FakeClock,
    FakeRefreshTokenHasher,
    FakeRefreshTokenRepo,
    FakeTokenIssuer,
    FakeTokenVerifier,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _record(
    token_hash: str = "h1",
    *,
    family: UUID | None = None,
    user: UUID | None = None,
    family_created_at: datetime | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        token_hash=token_hash,
        user_id=user if user is not None else uuid4(),
        family_id=family if family is not None else uuid4(),
        family_created_at=(family_created_at if family_created_at is not None else NOW),
        issued_at=issued_at if issued_at is not None else NOW,
        expires_at=(expires_at if expires_at is not None else NOW + timedelta(days=14)),
    )


@pytest.mark.unit
class TestFakeTokens:
    def test_refresh_hasher_is_deterministic(self):
        hasher = FakeRefreshTokenHasher()

        assert hasher.hash(SecretStr("t")) == hasher.hash(SecretStr("t"))

    def test_issued_token_verifies_to_the_same_identity(self):
        clock = FakeClock()
        identity = Identity(uuid4())

        token = FakeTokenIssuer(clock).issue_access_token(identity)

        assert FakeTokenVerifier().verify_access_token(token.value) == identity
        assert token.expires_at == clock.now() + timedelta(minutes=15)

    @pytest.mark.parametrize("value", ["junk", "fake-access-not-a-uuid"])
    def test_verifier_returns_none_for_unrecognised_tokens(self, value):
        assert FakeTokenVerifier().verify_access_token(SecretStr(value)) is None


@pytest.mark.unit
class TestFakeRefreshTokenRepo:
    async def test_rotates_a_live_token_and_stores_the_replacement(self):
        repo = FakeRefreshTokenRepo()
        original = _record("h1")
        replacement = _record("h2", family=original.family_id, user=original.user_id)
        await repo.add(original)

        result = await repo.rotate(
            presented_hash="h1", replacement=replacement, now=NOW
        )

        assert result.outcome is RotationOutcome.ROTATED
        assert result.previous == original
        stored_old = repo.get("h1")
        assert stored_old is not None and stored_old.used_at == NOW
        assert repo.get("h2") == replacement

    async def test_second_use_of_a_token_is_reuse_and_stores_nothing(self):
        repo = FakeRefreshTokenRepo()
        original = _record("h1")
        await repo.add(original)
        await repo.rotate(presented_hash="h1", replacement=_record("h2"), now=NOW)

        result = await repo.rotate(
            presented_hash="h1",
            replacement=_record("h3"),
            now=NOW + timedelta(seconds=5),
        )

        assert result.outcome is RotationOutcome.REUSED
        assert result.previous is not None and result.previous.used_at == NOW
        assert repo.get("h3") is None

    @pytest.mark.parametrize("presented", ["missing", "expired"])
    async def test_unknown_or_expired_token_is_invalid(self, presented):
        repo = FakeRefreshTokenRepo()
        await repo.add(_record("expired", expires_at=NOW))

        result = await repo.rotate(
            presented_hash=presented, replacement=_record("h2"), now=NOW
        )

        assert result.outcome is RotationOutcome.INVALID
        assert result.previous is None

    async def test_of_two_concurrent_rotations_exactly_one_succeeds(self):
        repo = FakeRefreshTokenRepo()
        await repo.add(_record("h1"))

        results = await asyncio.gather(
            repo.rotate(presented_hash="h1", replacement=_record("a"), now=NOW),
            repo.rotate(presented_hash="h1", replacement=_record("b"), now=NOW),
        )

        assert sorted(r.outcome for r in results) == [
            RotationOutcome.REUSED,
            RotationOutcome.ROTATED,
        ]

    async def test_revoke_family_marks_only_that_family(self):
        repo = FakeRefreshTokenRepo()
        family = uuid4()
        await repo.add(_record("a", family=family))
        await repo.add(_record("b", family=family))
        await repo.add(_record("c"))

        await repo.revoke_family(family, now=NOW)

        assert all(repo.get(h).revoked_at == NOW for h in ("a", "b"))  # ty: ignore[unresolved-attribute]
        assert repo.get("c").revoked_at is None  # ty: ignore[unresolved-attribute]

    async def test_revoked_token_cannot_rotate(self):
        repo = FakeRefreshTokenRepo()
        record = _record("a")
        await repo.add(record)
        await repo.revoke_all_for_user(record.user_id, now=NOW)

        result = await repo.rotate(
            presented_hash="a", replacement=_record("b"), now=NOW
        )

        assert result.outcome is RotationOutcome.REUSED

    async def test_purge_removes_only_expired_tokens(self):
        repo = FakeRefreshTokenRepo()
        await repo.add(_record("old", expires_at=NOW - timedelta(days=1)))
        await repo.add(_record("live"))

        removed = await repo.purge_expired(now=NOW)

        assert removed == 1
        assert repo.get("old") is None and repo.get("live") is not None
