"""Integration tests for PostgresAccountRepo against real PostgreSQL.

Does not re-verify Account's own validation, or which constraint name
maps to which ErrorCode -- both are already covered by
test_repository_unit.py. These tests verify persistence behavior only:
that writes and reads round-trip correctly, that the unique indexes on
`code` and `name_key` are actually enforced by the database (not just
assumed), and that a missing row surfaces the same AppError an in-memory
substitute would.
"""

import pytest
from trutina.core.account.schemas.account import AccountCategory
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_account


@pytest.mark.integration
class TestPostgresAccountRepoCreate:
    async def test_creates_and_retrieves_account(self, postgres_account_repo):
        account = make_account(code="1001", name="Cash", category=AccountCategory.ASSET)

        await postgres_account_repo.create(account)
        fetched = await postgres_account_repo.get_by_code("1001")

        assert fetched is not None
        assert fetched.code == "1001"
        assert fetched.name == "Cash"
        assert fetched.category is AccountCategory.ASSET

    async def test_rejects_duplicate_code(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.create(
                make_account(code="1001", name="Petty Cash")
            )

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE

    async def test_rejects_duplicate_name_case_insensitively(
        self, postgres_account_repo
    ):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.create(make_account(code="2001", name="CASH"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME


@pytest.mark.integration
class TestPostgresAccountRepoLookups:
    async def test_returns_none_when_code_missing(self, postgres_account_repo):
        result = await postgres_account_repo.get_by_code("9999")

        assert result is None

    async def test_returns_none_when_name_missing(self, postgres_account_repo):
        result = await postgres_account_repo.get_by_name("Ghost")

        assert result is None

    async def test_finds_account_by_name_case_insensitively(
        self, postgres_account_repo
    ):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        result = await postgres_account_repo.get_by_name("cAsH")

        assert result is not None
        assert result.code == "1001"

    async def test_exists_by_code_true_and_false(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        assert await postgres_account_repo.exists_by_code("1001") is True
        assert await postgres_account_repo.exists_by_code("9999") is False

    async def test_exists_by_name_true_and_false(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        assert await postgres_account_repo.exists_by_name("Cash") is True
        assert await postgres_account_repo.exists_by_name("Ghost") is False


@pytest.mark.integration
class TestPostgresAccountRepoUpdate:
    async def test_updates_existing_account(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))
        updated = make_account(
            code="1001", name="Main Cash", category=AccountCategory.ASSET
        )

        await postgres_account_repo.update(updated)
        fetched = await postgres_account_repo.get_by_code("1001")

        assert fetched.name == "Main Cash"

    async def test_updated_name_is_findable_by_new_name_key(
        self, postgres_account_repo
    ):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))
        await postgres_account_repo.update(make_account(code="1001", name="Main Cash"))

        old_lookup = await postgres_account_repo.get_by_name("Cash")
        new_lookup = await postgres_account_repo.get_by_name("Main Cash")

        assert old_lookup is None
        assert new_lookup is not None
        assert new_lookup.code == "1001"

    async def test_raises_when_updating_unknown_code(self, postgres_account_repo):
        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.update(make_account(code="9999"))

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT

    async def test_raises_when_updated_name_collides(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))
        await postgres_account_repo.create(make_account(code="2001", name="Bank"))

        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.update(make_account(code="2001", name="Cash"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME


@pytest.mark.integration
class TestPostgresAccountRepoDelete:
    async def test_deletes_existing_account(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))

        await postgres_account_repo.delete_by_code("1001")

        assert await postgres_account_repo.get_by_code("1001") is None

    async def test_raises_when_deleting_unknown_code(self, postgres_account_repo):
        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.delete_by_code("9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.integration
class TestPostgresAccountRepoList:
    async def test_returns_empty_list_when_no_accounts_exist(
        self, postgres_account_repo
    ):
        result = await postgres_account_repo.list_all()

        assert result == []

    async def test_returns_all_persisted_accounts(self, postgres_account_repo):
        await postgres_account_repo.create(make_account(code="1001", name="Cash"))
        await postgres_account_repo.create(
            make_account(code="4001", name="Sales Revenue")
        )

        result = await postgres_account_repo.list_all()

        assert {a.code for a in result} == {"1001", "4001"}
