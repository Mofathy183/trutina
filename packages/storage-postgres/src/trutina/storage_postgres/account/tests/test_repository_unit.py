"""Unit tests for PostgresAccountRepo's pure mapping logic.

Covers only what needs no database: reconstructing an Account from an
AccountModel row, and deciding which domain conflict a violated unique
constraint maps to. Every method that actually issues SQL is covered
under test_repository_integration.py instead, against a real database --
constructing an AccountModel requires no live connection, so there is no
stub-settings fixture needed here the way a Beanie-backed adapter would
need.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from trutina.core.account.schemas.account import Account, AccountCategory
from trutina.shared.errors import ErrorCode
from trutina.storage_postgres.account.model import AccountModel
from trutina.storage_postgres.account.repository import PostgresAccountRepo


class _FakeAsyncpgCause(Exception):
    """Mimics the original asyncpg.PostgresError asyncpg attaches via __cause__."""

    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("simulated asyncpg constraint violation")
        self.constraint_name = constraint_name


class _FakeOrigError(Exception):
    """Mimics SQLAlchemy's translated asyncpg wrapper — no constraint_name of its own."""

    def __init__(self) -> None:
        super().__init__("simulated postgres constraint violation")


def _integrity_error(constraint_name: str | None) -> IntegrityError:
    orig = _FakeOrigError()
    orig.__cause__ = _FakeAsyncpgCause(constraint_name)
    return IntegrityError("stmt", {}, orig)


@pytest.mark.unit
class TestPostgresAccountRepoToDomain:
    def test_reconstructs_account_from_row(self):
        model = AccountModel(
            code="1001",
            name="Cash",
            name_key="cash",
            category=AccountCategory.ASSET.value,
        )

        account = PostgresAccountRepo._to_domain(model)

        assert isinstance(account, Account)
        assert account.code == "1001"
        assert account.name == "Cash"
        assert account.category is AccountCategory.ASSET

    @pytest.mark.parametrize("category", list(AccountCategory))
    def test_reconstructs_every_category(self, category):
        model = AccountModel(
            code="1001", name="Cash", name_key="cash", category=category.value
        )

        account = PostgresAccountRepo._to_domain(model)

        assert account.category is category


@pytest.mark.unit
class TestPostgresAccountRepoOnDuplicate:
    def test_maps_code_constraint_to_duplicate_code_error(self):
        exc = _integrity_error("uq_accounts_code")

        error = PostgresAccountRepo._on_duplicate(exc, code="1001", name="Cash")

        assert error.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
        assert error.context["field"] == "code"
        assert error.context["value"] == "1001"

    def test_maps_name_key_constraint_to_duplicate_name_error(self):
        exc = _integrity_error("uq_accounts_name_key")

        error = PostgresAccountRepo._on_duplicate(exc, code="1001", name="Cash")

        assert error.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert error.context["field"] == "name"
        assert error.context["value"] == "Cash"

    def test_maps_unrecognized_constraint_to_unknown_error(self):
        exc = _integrity_error("some_other_constraint")

        error = PostgresAccountRepo._on_duplicate(exc, code="1001", name="Cash")

        assert error.code == ErrorCode.UNKNOWN_ERROR

    def test_maps_missing_constraint_name_to_unknown_error(self):
        exc = _integrity_error(None)

        error = PostgresAccountRepo._on_duplicate(exc, code="1001", name="Cash")

        assert error.code == ErrorCode.UNKNOWN_ERROR
