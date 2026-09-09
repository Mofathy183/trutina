"""Integration tests for MongoAccountRepo against a real MongoDB instance.

These tests require a running MongoDB database configured via
TRUTINA_TEST_MONGO__URI and TRUTINA_TEST_MONGO__DB in .env.test.
Mark: @pytest.mark.integration — excluded from the fast unit-test run.

Fixture stack
-------------
test_settings (session)
    └── mongo_connection (session)
            └── beanie_init (session)
                    └── clean_db (function) ← truncates docs, keeps indexes
                            └── mongo_account_repo (function)

clean_db uses delete_many({}) rather than drop_collection() so that
the unique indexes Beanie creates during beanie_init are preserved
across every test in the session. If indexes were dropped, uniqueness
tests would silently pass when they should fail.

Coverage
--------
- create: persist, category, duplicate code, duplicate name,
  case-insensitive name collision, multiple accounts same category.
- exists_by_code: True, False, False-after-delete.
- exists_by_name: True, False, case-insensitive True.
- get_by_code: found, not-found, Account instance, normal_balance derived.
- get_by_name: found, not-found, case-insensitive, original display name.
- list_all: empty, single, multiple, ascending-code sort, Account instances.
- update: name, name_key atomicity, category, not-found, duplicate name on
  rename, same-name allowed, code immutability.
- delete_by_code: deletes, not-found, exists_by_code False after, name
  slot freed.
- Enum round-trip: every AccountCategory survives write → read.
- BSON exclusion: normal_balance absent from raw document.
- Index integrity: unique indexes survive clean_db.
- list_all sort: ascending by code regardless of insert order.
- Timestamps: created_at set once at insert and preserved across N
  updates, updated_at changes on every update, and the actual (naive)
  tz behavior after a real MongoDB round trip — see
  TestMongoAccountRepoTimestamps for why these live here and not in
  unit tests.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from trutina.core.account.repo import AccountRepo
from trutina.core.account.schemas.account import Account, AccountCategory
from trutina.infrastructure.mongo.account import AccountDocument
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_account


def _floor_to_milliseconds(dt: datetime) -> datetime:
    """Match MongoDB's BSON datetime precision.

    BSON truncates sub-millisecond precision on write. A locally
    captured datetime.now(UTC) (microsecond precision) can land in the
    same millisecond bucket as a write that happens microseconds later
    — once that write is truncated, it can come back *before* the local
    timestamp unless the local timestamp is floored to the same
    precision first.
    """
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


@pytest.mark.integration
class TestMongoAccountRepoCreate:
    async def test_persists_account(self, mongo_account_repo):
        account = make_account(code="1001", name="Cash")

        await mongo_account_repo.create(account)

        result = await mongo_account_repo.get_by_code("1001")
        assert result is not None
        assert result.code == "1001"
        assert result.name == "Cash"

    async def test_persists_category(self, mongo_account_repo: AccountRepo):
        account = make_account(code="1001", category=AccountCategory.REVENUE)

        await mongo_account_repo.create(account)

        result = await mongo_account_repo.get_by_code("1001")
        assert result is not None
        assert result.category is AccountCategory.REVENUE

    async def test_raises_duplicate_account_code(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.create(
                make_account(code="1001", name="Petty Cash")
            )

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
        assert exc_info.value.context["field"] == "code"
        assert exc_info.value.context["value"] == "1001"

    async def test_raises_duplicate_account_name(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.create(make_account(code="2001", name="Cash"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert exc_info.value.context["field"] == "name"
        assert exc_info.value.context["value"] == "Cash"

    async def test_raises_duplicate_name_case_insensitively(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.create(make_account(code="2001", name="CASH"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME

    async def test_allows_different_names_with_same_category(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET)
        )
        await mongo_account_repo.create(
            make_account(code="1002", name="Bank", category=AccountCategory.ASSET)
        )

        result = await mongo_account_repo.list_all()
        assert len(result) == 2


@pytest.mark.integration
class TestMongoAccountRepoExistsByCode:
    async def test_returns_true_when_account_exists(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001"))

        assert await mongo_account_repo.exists_by_code("1001") is True

    async def test_returns_false_when_account_does_not_exist(
        self, mongo_account_repo: AccountRepo
    ):
        assert await mongo_account_repo.exists_by_code("9999") is False

    async def test_returns_false_after_account_is_deleted(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001"))
        await mongo_account_repo.delete_by_code("1001")

        assert await mongo_account_repo.exists_by_code("1001") is False


@pytest.mark.integration
class TestMongoAccountRepoExistsByName:
    async def test_returns_true_when_account_exists(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(name="Cash"))

        assert await mongo_account_repo.exists_by_name("Cash") is True

    async def test_returns_false_when_account_does_not_exist(
        self, mongo_account_repo: AccountRepo
    ):
        assert await mongo_account_repo.exists_by_name("Nonexistent") is False

    @pytest.mark.parametrize("variant", ["cash", "CASH", "cAsH"])
    async def test_returns_true_case_insensitively(
        self, mongo_account_repo: AccountRepo, variant: str
    ):
        await mongo_account_repo.create(make_account(name="Cash"))

        assert await mongo_account_repo.exists_by_name(variant) is True


@pytest.mark.integration
class TestMongoAccountRepoGetByCode:
    async def test_returns_account_when_found(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        result = await mongo_account_repo.get_by_code("1001")

        assert result is not None
        assert result.code == "1001"
        assert result.name == "Cash"

    async def test_returns_none_when_not_found(self, mongo_account_repo: AccountRepo):
        result = await mongo_account_repo.get_by_code("9999")
        assert result is None

    async def test_returns_account_instance(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001"))

        result = await mongo_account_repo.get_by_code("1001")

        assert isinstance(result, Account)

    async def test_normal_balance_is_derived_not_stored(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(
            make_account(code="1001", category=AccountCategory.ASSET)
        )

        result = await mongo_account_repo.get_by_code("1001")

        assert result is not None
        assert result.normal_balance == "debit"


@pytest.mark.integration
class TestMongoAccountRepoGetByName:
    async def test_returns_account_when_found(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        result = await mongo_account_repo.get_by_name("Cash")

        assert result is not None
        assert result.code == "1001"

    async def test_returns_none_when_not_found(self, mongo_account_repo: AccountRepo):
        result = await mongo_account_repo.get_by_name("Nonexistent")
        assert result is None

    @pytest.mark.parametrize("variant", ["cash", "CASH", "cAsH"])
    async def test_resolves_case_insensitively(
        self, mongo_account_repo: AccountRepo, variant: str
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        result = await mongo_account_repo.get_by_name(variant)

        assert result is not None
        assert result.code == "1001"

    async def test_returns_original_display_name(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(
            make_account(code="1001", name="Accounts Receivable")
        )

        result = await mongo_account_repo.get_by_name("accounts receivable")

        assert result is not None
        assert result.name == "Accounts Receivable"


@pytest.mark.integration
class TestMongoAccountRepoListAll:
    async def test_returns_empty_list_when_no_accounts(
        self, mongo_account_repo: AccountRepo
    ):
        result = await mongo_account_repo.list_all()
        assert result == []

    async def test_returns_single_account(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001"))

        result = await mongo_account_repo.list_all()

        assert len(result) == 1
        assert result[0].code == "1001"

    async def test_returns_all_accounts(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        await mongo_account_repo.create(make_account(code="2001", name="Revenue"))
        await mongo_account_repo.create(make_account(code="3001", name="Equipment"))

        result = await mongo_account_repo.list_all()

        assert len(result) == 3

    async def test_returns_accounts_sorted_by_code_ascending(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="3001", name="Equipment"))
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        await mongo_account_repo.create(make_account(code="2001", name="Revenue"))

        result = await mongo_account_repo.list_all()

        assert [a.code for a in result] == ["1001", "2001", "3001"]

    async def test_returns_account_instances(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001"))

        result = await mongo_account_repo.list_all()

        assert all(isinstance(a, Account) for a in result)


@pytest.mark.integration
class TestMongoAccountRepoUpdate:
    async def test_updates_name(self, mongo_account_repo: AccountRepo):
        original = make_account(code="1001", name="Cash")
        await mongo_account_repo.create(original)

        updated = Account(code="1001", name="Main Cash", category=original.category)
        await mongo_account_repo.update(updated)

        result = await mongo_account_repo.get_by_code("1001")
        assert result is not None
        assert result.name == "Main Cash"

    async def test_updates_name_key_atomically_with_name(
        self, mongo_account_repo: AccountRepo
    ):
        original = make_account(code="1001", name="Cash")
        await mongo_account_repo.create(original)

        updated = Account(code="1001", name="Petty Cash", category=original.category)
        await mongo_account_repo.update(updated)

        assert await mongo_account_repo.get_by_name("cash") is None
        result = await mongo_account_repo.get_by_name("petty cash")
        assert result is not None
        assert result.name == "Petty Cash"

    async def test_updates_category(self, mongo_account_repo: AccountRepo):
        original = make_account(code="1001", category=AccountCategory.ASSET)
        await mongo_account_repo.create(original)

        updated = Account(
            code="1001", name=original.name, category=AccountCategory.EXPENSE
        )
        await mongo_account_repo.update(updated)

        result = await mongo_account_repo.get_by_code("1001")
        assert result is not None
        assert result.category is AccountCategory.EXPENSE

    async def test_raises_when_account_does_not_exist(
        self, mongo_account_repo: AccountRepo
    ):
        ghost = Account(code="9999", name="Ghost", category=AccountCategory.ASSET)

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.update(ghost)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "9999"

    async def test_raises_duplicate_name_on_rename(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        await mongo_account_repo.create(make_account(code="2001", name="Bank"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.update(
                Account(code="2001", name="Cash", category=AccountCategory.ASSET)
            )

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert exc_info.value.context["value"] == "Cash"

    async def test_allows_update_when_name_is_unchanged(
        self, mongo_account_repo: AccountRepo
    ):
        original = make_account(
            code="1001", name="Cash", category=AccountCategory.ASSET
        )
        await mongo_account_repo.create(original)

        updated = Account(code="1001", name="Cash", category=AccountCategory.LIABILITY)
        await mongo_account_repo.update(updated)

        result = await mongo_account_repo.get_by_code("1001")
        assert result is not None
        assert result.category is AccountCategory.LIABILITY
        assert result.name == "Cash"

    async def test_code_is_immutable(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        updated = Account(code="1001", name="New Cash", category=AccountCategory.ASSET)
        await mongo_account_repo.update(updated)

        assert await mongo_account_repo.get_by_code("1001") is not None
        assert await mongo_account_repo.get_by_code("9999") is None


@pytest.mark.integration
class TestMongoAccountRepoDeleteByCode:
    async def test_deletes_account(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001"))

        await mongo_account_repo.delete_by_code("1001")

        assert await mongo_account_repo.get_by_code("1001") is None

    async def test_raises_when_account_does_not_exist(
        self, mongo_account_repo: AccountRepo
    ):
        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.delete_by_code("9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "9999"

    async def test_exists_by_code_returns_false_after_delete(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001"))

        await mongo_account_repo.delete_by_code("1001")

        assert await mongo_account_repo.exists_by_code("1001") is False

    async def test_name_slot_freed_after_delete(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        await mongo_account_repo.delete_by_code("1001")

        await mongo_account_repo.create(make_account(code="2001", name="Cash"))

        result = await mongo_account_repo.get_by_code("2001")
        assert result is not None
        assert result.name == "Cash"

    async def test_does_not_affect_other_accounts(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        await mongo_account_repo.create(make_account(code="2001", name="Bank"))

        await mongo_account_repo.delete_by_code("2001")

        assert await mongo_account_repo.get_by_code("1001") is not None
        assert await mongo_account_repo.get_by_code("2001") is None


@pytest.mark.integration
class TestMongoAccountRepoTimestamps:
    async def test_created_at_is_set_on_creation(self, mongo_account_repo: AccountRepo):
        before = _floor_to_milliseconds(datetime.now(UTC))
        await mongo_account_repo.create(make_account(code="1001"))
        after = datetime.now(UTC)

        doc = await AccountDocument.find_one(AccountDocument.code == "1001")

        assert doc is not None
        assert doc.created_at is not None

        created_at = doc.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        assert before <= created_at <= after

    async def test_updated_at_equals_created_at_on_creation(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001"))

        doc = await AccountDocument.find_one(AccountDocument.code == "1001")

        assert doc is not None
        assert doc.created_at == doc.updated_at

    async def test_created_at_is_unchanged_after_update(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        original = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert original is not None

        await asyncio.sleep(0.01)
        await mongo_account_repo.update(
            Account(code="1001", name="Main Cash", category=AccountCategory.ASSET)
        )

        updated = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert updated is not None
        assert updated.created_at == original.created_at

    async def test_created_at_remains_unchanged_across_multiple_updates(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        first = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert first is not None

        await asyncio.sleep(0.01)
        await mongo_account_repo.update(
            Account(code="1001", name="Main Cash", category=AccountCategory.ASSET)
        )
        await asyncio.sleep(0.01)
        await mongo_account_repo.update(
            Account(code="1001", name="Main Cash", category=AccountCategory.EXPENSE)
        )

        last = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert last is not None
        assert last.created_at == first.created_at

    async def test_updated_at_changes_after_update(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))
        original = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert original is not None

        await asyncio.sleep(0.01)
        await mongo_account_repo.update(
            Account(code="1001", name="Main Cash", category=AccountCategory.ASSET)
        )

        updated = await AccountDocument.find_one(AccountDocument.code == "1001")
        assert updated is not None
        assert updated.updated_at is not None
        assert updated.updated_at > original.updated_at

    async def test_timestamps_are_naive_after_a_database_round_trip(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001"))

        doc = await AccountDocument.find_one(AccountDocument.code == "1001")

        assert doc is not None
        assert doc.created_at is not None
        assert doc.created_at.tzinfo is None


@pytest.mark.integration
class TestAccountCategoryEnumRoundTrip:
    @pytest.mark.parametrize("category", list(AccountCategory))
    async def test_category_round_trips_correctly(
        self, mongo_account_repo: AccountRepo, category: AccountCategory
    ):
        code = f"RT-{category.value}"
        name = f"Round Trip {category.value.capitalize()}"

        await mongo_account_repo.create(
            Account(code=code, name=name, category=category)
        )

        result = await mongo_account_repo.get_by_code(code)
        assert result is not None
        assert result.category is category


@pytest.mark.integration
class TestNormalBalanceExclusion:
    async def test_normal_balance_not_stored_in_bson(
        self, mongo_account_repo: AccountRepo, clean_db
    ):
        await mongo_account_repo.create(
            make_account(code="1001", category=AccountCategory.ASSET)
        )

        raw = await clean_db["accounts"].find_one({"code": "1001"})

        assert raw is not None
        assert "normal_balance" not in raw


@pytest.mark.integration
class TestIndexIntegrityAfterCleanDb:
    async def test_unique_code_index_enforced_after_cleanup(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.create(make_account(code="1001", name="Other"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE

    async def test_unique_name_index_enforced_after_cleanup(
        self, mongo_account_repo: AccountRepo
    ):
        await mongo_account_repo.create(make_account(code="1001", name="Cash"))

        with pytest.raises(AppError) as exc_info:
            await mongo_account_repo.create(make_account(code="2001", name="Cash"))

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME


@pytest.mark.integration
class TestListAllSort:
    async def test_sort_is_stable_and_ascending(self, mongo_account_repo: AccountRepo):
        await mongo_account_repo.create(
            Account(code="3001", name="Equipment", category=AccountCategory.ASSET)
        )
        await mongo_account_repo.create(
            Account(code="1001", name="Cash", category=AccountCategory.ASSET)
        )
        await mongo_account_repo.create(
            Account(code="2001", name="Revenue", category=AccountCategory.REVENUE)
        )

        result = await mongo_account_repo.list_all()

        assert [a.code for a in result] == ["1001", "2001", "3001"]
