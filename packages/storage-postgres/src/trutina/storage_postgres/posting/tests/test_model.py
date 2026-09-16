from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Numeric, Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from trutina.storage_postgres.posting.model import PostingModel
from trutina.storage_postgres.shared import Base


def _table(model: type[DeclarativeBase]) -> Table:
    return cast(Table, model.__table__)


def _numeric(column) -> Numeric:
    return cast(Numeric, column.type)


def _check_constraints(table: Table) -> list[CheckConstraint]:
    return [c for c in table.constraints if isinstance(c, CheckConstraint)]


def _unique_constraints(table: Table) -> list[UniqueConstraint]:
    return [c for c in table.constraints if isinstance(c, UniqueConstraint)]


@pytest.mark.unit
class TestPostingModelTable:
    def test_table_name_is_postings(self):
        assert PostingModel.__tablename__ == "postings"

    def test_shares_the_one_declarative_registry(self):
        assert PostingModel.metadata is Base.metadata


@pytest.mark.unit
class TestPostingModelId:
    def test_id_is_primary_key(self):
        column = _table(PostingModel).columns["id"]
        assert column.primary_key is True

    def test_id_is_bigint(self):
        column = _table(PostingModel).columns["id"]
        assert column.type.__class__.__name__ == "BigInteger"


@pytest.mark.unit
class TestPostingModelAccountColumns:
    def test_account_is_not_nullable(self):
        column = _table(PostingModel).columns["account"]
        assert column.nullable is False

    def test_account_key_is_not_nullable(self):
        column = _table(PostingModel).columns["account_key"]
        assert column.nullable is False

    def test_account_key_is_not_a_generated_column(self):
        column = _table(PostingModel).columns["account_key"]
        assert column.computed is None

    def test_account_key_is_not_unique(self):
        column = _table(PostingModel).columns["account_key"]
        assert column.unique is not True

    def test_account_key_has_an_index(self):
        index_names = {index.name for index in _table(PostingModel).indexes}
        assert "ix_postings_account_key" in index_names


@pytest.mark.unit
class TestPostingModelAmountColumns:
    def test_debit_amount_is_numeric_18_2(self):
        column = _table(PostingModel).columns["debit_amount"]
        assert _numeric(column).precision == 18
        assert _numeric(column).scale == 2

    def test_credit_amount_is_numeric_18_2(self):
        column = _table(PostingModel).columns["credit_amount"]
        assert _numeric(column).precision == 18
        assert _numeric(column).scale == 2

    def test_debit_amount_defaults_to_zero(self):
        column = _table(PostingModel).columns["debit_amount"]
        assert column.server_default is not None

    def test_credit_amount_defaults_to_zero(self):
        column = _table(PostingModel).columns["credit_amount"]
        assert column.server_default is not None


@pytest.mark.unit
class TestPostingModelForeignKey:
    def test_journal_number_is_not_nullable(self):
        column = _table(PostingModel).columns["journal_number"]
        assert column.nullable is False

    def test_journal_number_references_journal_entries(self):
        column = _table(PostingModel).columns["journal_number"]
        fk = next(iter(column.foreign_keys))
        assert fk.column.table.name == "journal_entries"
        assert fk.column.name == "journal_number"

    def test_journal_number_fk_is_restrict_on_delete(self):
        column = _table(PostingModel).columns["journal_number"]
        fk = next(iter(column.foreign_keys))
        assert fk.ondelete == "RESTRICT"


@pytest.mark.unit
class TestPostingModelPostingDate:
    def test_posting_date_is_not_nullable(self):
        column = _table(PostingModel).columns["posting_date"]
        assert column.nullable is False

    def test_check_constraint_exists(self):
        check_names = {c.name for c in _check_constraints(_table(PostingModel))}
        assert "ck_postings_posting_date_range" in check_names

    def test_check_constraint_enforces_lower_bound(self):
        constraint = next(
            c
            for c in _check_constraints(_table(PostingModel))
            if c.name == "ck_postings_posting_date_range"
        )
        assert "2020-01-01" in str(constraint.sqltext)

    def test_check_constraint_enforces_upper_bound(self):
        constraint = next(
            c
            for c in _check_constraints(_table(PostingModel))
            if c.name == "ck_postings_posting_date_range"
        )
        assert "now()" in str(constraint.sqltext)


@pytest.mark.unit
class TestPostingModelLineIndex:
    def test_line_index_is_not_nullable(self):
        column = _table(PostingModel).columns["line_index"]
        assert column.nullable is False

    def test_journal_number_and_line_index_are_jointly_unique(self):
        column_sets = [
            {col.name for col in uc.columns}
            for uc in _unique_constraints(_table(PostingModel))
        ]
        assert {"journal_number", "line_index"} in column_sets


@pytest.mark.unit
class TestPostingModelExactlyOneSideCheck:
    def test_check_constraint_exists(self):
        check_names = {c.name for c in _check_constraints(_table(PostingModel))}
        assert "ck_postings_exactly_one_side" in check_names

    def test_check_constraint_references_both_amount_columns(self):
        constraint = next(
            c
            for c in _check_constraints(_table(PostingModel))
            if c.name == "ck_postings_exactly_one_side"
        )
        sql_text = str(constraint.sqltext)
        assert "debit_amount" in sql_text
        assert "credit_amount" in sql_text
