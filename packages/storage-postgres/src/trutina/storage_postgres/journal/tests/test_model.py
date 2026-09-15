from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Numeric, Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from trutina.storage_postgres.journal.model import JournalEntryModel, JournalLineModel
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
class TestJournalEntryModelTable:
    def test_table_name_is_journal_entries(self):
        assert JournalEntryModel.__tablename__ == "journal_entries"

    def test_shares_the_one_declarative_registry(self):
        assert JournalEntryModel.metadata is Base.metadata


@pytest.mark.unit
class TestJournalEntryModelJournalNumber:
    def test_journal_number_is_primary_key(self):
        column = _table(JournalEntryModel).columns["journal_number"]
        assert column.primary_key is True

    def test_journal_number_is_bigint(self):
        column = _table(JournalEntryModel).columns["journal_number"]
        assert column.type.__class__.__name__ == "BigInteger"

    def test_journal_number_autoincrements(self):
        column = _table(JournalEntryModel).columns["journal_number"]
        assert column.autoincrement is True


@pytest.mark.unit
class TestJournalEntryModelColumns:
    def test_posting_date_is_not_nullable(self):
        column = _table(JournalEntryModel).columns["posting_date"]
        assert column.nullable is False

    def test_description_is_nullable(self):
        column = _table(JournalEntryModel).columns["description"]
        assert column.nullable is True


@pytest.mark.unit
class TestJournalEntryModelPostingDateCheck:
    def test_check_constraint_exists(self):
        check_names = {c.name for c in _check_constraints(_table(JournalEntryModel))}
        assert "ck_journal_entries_posting_date_range" in check_names

    def test_check_constraint_enforces_lower_bound(self):
        constraint = next(
            c
            for c in _check_constraints(_table(JournalEntryModel))
            if c.name == "ck_journal_entries_posting_date_range"
        )
        assert "2020-01-01" in str(constraint.sqltext)

    def test_check_constraint_enforces_upper_bound(self):
        constraint = next(
            c
            for c in _check_constraints(_table(JournalEntryModel))
            if c.name == "ck_journal_entries_posting_date_range"
        )
        assert "now()" in str(constraint.sqltext)


@pytest.mark.unit
class TestJournalLineModelTable:
    def test_table_name_is_journal_lines(self):
        assert JournalLineModel.__tablename__ == "journal_lines"

    def test_shares_the_one_declarative_registry(self):
        assert JournalLineModel.metadata is Base.metadata


@pytest.mark.unit
class TestJournalLineModelId:
    def test_id_is_primary_key(self):
        column = _table(JournalLineModel).columns["id"]
        assert column.primary_key is True

    def test_id_is_bigint(self):
        column = _table(JournalLineModel).columns["id"]
        assert column.type.__class__.__name__ == "BigInteger"


@pytest.mark.unit
class TestJournalLineModelForeignKey:
    def test_journal_number_is_not_nullable(self):
        column = _table(JournalLineModel).columns["journal_number"]
        assert column.nullable is False

    def test_journal_number_references_journal_entries(self):
        column = _table(JournalLineModel).columns["journal_number"]
        fk = next(iter(column.foreign_keys))
        assert fk.column.table.name == "journal_entries"
        assert fk.column.name == "journal_number"

    def test_journal_number_fk_is_restrict_on_delete(self):
        column = _table(JournalLineModel).columns["journal_number"]
        fk = next(iter(column.foreign_keys))
        assert fk.ondelete == "RESTRICT"


@pytest.mark.unit
class TestJournalLineModelColumns:
    def test_line_index_is_not_nullable(self):
        column = _table(JournalLineModel).columns["line_index"]
        assert column.nullable is False

    def test_account_is_not_nullable(self):
        column = _table(JournalLineModel).columns["account"]
        assert column.nullable is False

    def test_debit_amount_is_numeric_18_2(self):
        column = _table(JournalLineModel).columns["debit_amount"]
        assert _numeric(column).precision == 18
        assert _numeric(column).scale == 2

    def test_credit_amount_is_numeric_18_2(self):
        column = _table(JournalLineModel).columns["credit_amount"]
        assert _numeric(column).precision == 18
        assert _numeric(column).scale == 2

    def test_debit_amount_defaults_to_zero(self):
        column = _table(JournalLineModel).columns["debit_amount"]
        assert column.server_default is not None

    def test_credit_amount_defaults_to_zero(self):
        column = _table(JournalLineModel).columns["credit_amount"]
        assert column.server_default is not None


@pytest.mark.unit
class TestJournalLineModelUniqueness:
    def test_journal_number_and_line_index_are_jointly_unique(self):
        column_sets = [
            {col.name for col in uc.columns}
            for uc in _unique_constraints(_table(JournalLineModel))
        ]
        assert {"journal_number", "line_index"} in column_sets


@pytest.mark.unit
class TestJournalLineModelExactlyOneSideCheck:
    def test_check_constraint_exists(self):
        check_names = {c.name for c in _check_constraints(_table(JournalLineModel))}
        assert "ck_journal_lines_exactly_one_side" in check_names

    def test_check_constraint_references_both_amount_columns(self):
        constraint = next(
            c
            for c in _check_constraints(_table(JournalLineModel))
            if c.name == "ck_journal_lines_exactly_one_side"
        )
        sql_text = str(constraint.sqltext)
        assert "debit_amount" in sql_text
        assert "credit_amount" in sql_text
