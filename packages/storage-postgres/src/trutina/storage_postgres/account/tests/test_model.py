from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table
from sqlalchemy.orm import DeclarativeBase
from trutina.core.account.schemas.account import AccountCategory
from trutina.storage_postgres.account.model import AccountModel
from trutina.storage_postgres.shared import Base


def _table(model: type[DeclarativeBase]) -> Table:
    return cast(Table, model.__table__)


def _check_constraints(table: Table) -> list[CheckConstraint]:
    return [c for c in table.constraints if isinstance(c, CheckConstraint)]


@pytest.mark.unit
class TestAccountModelTable:
    def test_table_name_is_accounts(self):
        assert AccountModel.__tablename__ == "accounts"

    def test_shares_the_one_declarative_registry(self):
        assert AccountModel.metadata is Base.metadata


@pytest.mark.unit
class TestAccountModelId:
    def test_id_is_primary_key(self):
        column = _table(AccountModel).columns["id"]
        assert column.primary_key is True

    def test_id_is_bigint(self):
        column = _table(AccountModel).columns["id"]
        assert column.type.__class__.__name__ == "BigInteger"

    def test_id_autoincrements(self):
        column = _table(AccountModel).columns["id"]
        assert column.autoincrement is True


@pytest.mark.unit
class TestAccountModelColumns:
    def test_code_is_not_nullable(self):
        column = _table(AccountModel).columns["code"]
        assert column.nullable is False

    def test_code_is_unique(self):
        column = _table(AccountModel).columns["code"]
        assert column.unique is True

    def test_name_is_not_nullable(self):
        column = _table(AccountModel).columns["name"]
        assert column.nullable is False

    def test_category_is_not_nullable(self):
        column = _table(AccountModel).columns["category"]
        assert column.nullable is False


@pytest.mark.unit
class TestAccountModelNameKey:
    def test_name_key_is_not_nullable(self):
        column = _table(AccountModel).columns["name_key"]
        assert column.nullable is False

    def test_name_key_is_unique(self):
        column = _table(AccountModel).columns["name_key"]
        assert column.unique is True

    def test_name_key_is_not_a_generated_column(self):
        column = _table(AccountModel).columns["name_key"]
        assert column.computed is None

    def test_name_key_has_no_server_side_default(self):
        column = _table(AccountModel).columns["name_key"]
        assert column.server_default is None


@pytest.mark.unit
class TestAccountModelCategoryCheck:
    def test_check_constraint_exists(self):
        check_names = {c.name for c in _check_constraints(_table(AccountModel))}
        assert "ck_accounts_category" in check_names

    def test_check_constraint_includes_every_category_value(self):
        constraint = next(
            c
            for c in _check_constraints(_table(AccountModel))
            if c.name == "ck_accounts_category"
        )
        sql_text = str(constraint.sqltext)
        for category in AccountCategory:
            assert f"'{category.value}'" in sql_text


@pytest.mark.unit
class TestAccountModelTimestamps:
    def test_created_at_column_exists(self):
        assert "created_at" in _table(AccountModel).columns

    def test_updated_at_column_exists(self):
        assert "updated_at" in _table(AccountModel).columns
