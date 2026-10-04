from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from trutina.authentication import User

from tests.fakes import FakeLoginAttemptRepo, FakePasswordHasher, FakeUserRepo

NOW = datetime(2025, 1, 1, tzinfo=UTC)


@pytest.mark.unit
class TestFakePasswordHasher:
    async def test_verifies_a_matching_password(self):
        hasher = FakePasswordHasher()
        hashed = await hasher.hash(SecretStr("pw"))

        assert await hasher.verify(SecretStr("pw"), hashed) is True

    async def test_rejects_a_wrong_password_and_a_malformed_hash(self):
        hasher = FakePasswordHasher()
        hashed = await hasher.hash(SecretStr("pw"))

        assert await hasher.verify(SecretStr("other"), hashed) is False
        assert await hasher.verify(SecretStr("pw"), "garbage") is False

    async def test_records_the_hash_each_verify_ran_against(self):
        hasher = FakePasswordHasher()

        await hasher.verify(SecretStr("pw"), "dummy")

        assert hasher.verify_calls == ["dummy"]

    def test_reports_configured_stale_hashes(self):
        hasher = FakePasswordHasher()
        hasher.stale_hashes.add("old")

        assert hasher.needs_rehash("old") is True
        assert hasher.needs_rehash("new") is False


@pytest.mark.unit
class TestFakeUserRepo:
    async def test_finds_a_user_by_email_ignoring_case(self):
        repo = FakeUserRepo()
        user = User(
            id=uuid4(),
            email="Ann@Example.com",
            password_hash="h",
            is_active=True,
            created_at=NOW,
        )
        await repo.create(user)

        assert await repo.get_by_email("ann@example.COM") == user
        assert repo.created_users == [user]

    async def test_returns_none_for_a_missing_user(self):
        repo = FakeUserRepo()

        assert await repo.get_by_id(uuid4()) is None
        assert await repo.get_by_email("nobody@example.com") is None

    async def test_updates_the_password_hash(self):
        repo = FakeUserRepo()
        user = User(
            id=uuid4(),
            email="a@b.c",
            password_hash="old",
            is_active=True,
            created_at=NOW,
        )
        await repo.create(user)

        await repo.update_password_hash(user.id, "new")

        stored = await repo.get_by_id(user.id)
        assert stored is not None
        assert stored.password_hash == "new"


@pytest.mark.unit
class TestFakeLoginAttemptRepo:
    async def test_counts_only_matching_recent_failures(self):
        repo = FakeLoginAttemptRepo()
        await repo.record_failure(ip="1.1.1.1", email="A@x.com", at=NOW)
        await repo.record_failure(
            ip="1.1.1.1", email="a@x.com", at=NOW + timedelta(minutes=1)
        )
        await repo.record_failure(ip="2.2.2.2", email="a@x.com", at=NOW)

        count = await repo.count_failures(ip="1.1.1.1", email="a@x.com", since=NOW)
        recent = await repo.count_failures(
            ip="1.1.1.1", email="a@x.com", since=NOW + timedelta(seconds=30)
        )

        assert (count, recent) == (2, 1)

    async def test_clear_removes_only_that_ip_and_email(self):
        repo = FakeLoginAttemptRepo()
        await repo.record_failure(ip="1.1.1.1", email="a@x.com", at=NOW)
        await repo.record_failure(ip="2.2.2.2", email="a@x.com", at=NOW)

        await repo.clear(ip="1.1.1.1", email="a@x.com")

        assert await repo.count_failures(ip="1.1.1.1", email="a@x.com", since=NOW) == 0
        assert await repo.count_failures(ip="2.2.2.2", email="a@x.com", since=NOW) == 1

    async def test_purge_removes_rows_older_than_the_cutoff(self):
        repo = FakeLoginAttemptRepo()
        await repo.record_failure(ip="i", email="e", at=NOW)
        await repo.record_failure(ip="i", email="e", at=NOW + timedelta(hours=2))

        removed = await repo.purge_before(NOW + timedelta(hours=1))

        assert removed == 1
