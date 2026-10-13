from datetime import UTC, datetime
from uuid import uuid4

import pytest
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_user


@pytest.mark.integration
class TestPostgresUserRepoCreate:
    async def test_creates_and_retrieves_user_by_id(self, postgres_user_repo):
        user = make_user(email="ann@example.com", password_hash="h1")

        await postgres_user_repo.create(user)
        fetched = await postgres_user_repo.get_by_id(user.id)

        assert fetched is not None
        assert fetched.id == user.id
        assert fetched.email == "ann@example.com"
        assert fetched.password_hash == "h1"
        assert fetched.is_active is True

    async def test_persists_an_inactive_user(self, postgres_user_repo):
        user = make_user(is_active=False)

        await postgres_user_repo.create(user)
        fetched = await postgres_user_repo.get_by_id(user.id)

        assert fetched is not None
        assert fetched.is_active is False

    async def test_ignores_a_caller_supplied_created_at(self, postgres_user_repo):
        supplied = datetime(2000, 1, 1, tzinfo=UTC)
        user = make_user(created_at=supplied)

        await postgres_user_repo.create(user)
        fetched = await postgres_user_repo.get_by_id(user.id)

        assert fetched is not None
        assert fetched.created_at != supplied
        assert fetched.created_at > datetime(2020, 1, 1, tzinfo=UTC)

    async def test_rejects_duplicate_email_in_another_casing(self, postgres_user_repo):
        await postgres_user_repo.create(make_user(email="ann@example.com"))
        duplicate = make_user(email="  ANN@Example.COM ")

        with pytest.raises(AppError) as exc_info:
            await postgres_user_repo.create(duplicate)

        assert exc_info.value.code == ErrorCode.DUPLICATE_USER_EMAIL

    async def test_duplicate_email_error_context_has_no_email(self, postgres_user_repo):
        await postgres_user_repo.create(make_user(email="ann@example.com"))

        with pytest.raises(AppError) as exc_info:
            await postgres_user_repo.create(make_user(email="ann@example.com"))

        context = dict(exc_info.value.context)
        assert context == {"resource": "user", "field": "email"}
        assert all("ann@example.com" not in value for value in context.values())


@pytest.mark.integration
class TestPostgresUserRepoLookups:
    async def test_returns_none_when_id_missing(self, postgres_user_repo):
        assert await postgres_user_repo.get_by_id(uuid4()) is None

    async def test_returns_none_when_email_missing(self, postgres_user_repo):
        assert await postgres_user_repo.get_by_email("ghost@example.com") is None

    async def test_finds_user_by_email_ignoring_case_and_whitespace(
        self, postgres_user_repo
    ):
        user = make_user(email="ann@example.com")
        await postgres_user_repo.create(user)

        fetched = await postgres_user_repo.get_by_email("  ANN@Example.COM ")

        assert fetched is not None
        assert fetched.id == user.id


@pytest.mark.integration
class TestPostgresUserRepoUpdatePasswordHash:
    async def test_persists_the_new_hash(self, postgres_user_repo):
        user = make_user(password_hash="old")
        await postgres_user_repo.create(user)

        await postgres_user_repo.update_password_hash(user.id, "new")
        fetched = await postgres_user_repo.get_by_id(user.id)

        assert fetched is not None
        assert fetched.password_hash == "new"
        assert fetched.email == user.email

    async def test_raises_unknown_user_when_id_missing(self, postgres_user_repo):
        with pytest.raises(AppError) as exc_info:
            await postgres_user_repo.update_password_hash(uuid4(), "new")

        assert exc_info.value.code == ErrorCode.UNKNOWN_USER


@pytest.mark.integration
class TestPostgresUserRepoSetActive:
    async def test_deactivates_and_reactivates(self, postgres_user_repo):
        user = make_user(password_hash="keep")
        await postgres_user_repo.create(user)

        await postgres_user_repo.set_active(user.id, False)
        deactivated = await postgres_user_repo.get_by_id(user.id)
        await postgres_user_repo.set_active(user.id, True)
        reactivated = await postgres_user_repo.get_by_id(user.id)

        assert deactivated is not None
        assert deactivated.is_active is False
        assert deactivated.password_hash == "keep"
        assert reactivated is not None
        assert reactivated.is_active is True

    async def test_raises_unknown_user_when_id_missing(self, postgres_user_repo):
        with pytest.raises(AppError) as exc_info:
            await postgres_user_repo.set_active(uuid4(), False)

        assert exc_info.value.code == ErrorCode.UNKNOWN_USER
