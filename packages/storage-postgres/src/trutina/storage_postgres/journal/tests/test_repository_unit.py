"""Unit tests for PostgresJournalRepo's pure mapping logic.

Covers reconstruction of a JournalEntry from JournalEntryModel/
JournalLineModel rows, and conflict translation -- both require no
database. save()/get_by_number()/list_entries()/next_journal_number()'s
actual SQL behavior is covered under test_repository_integration.py.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from trutina.core.journal.schemas.journal import JournalEntry
from trutina.shared.errors import ErrorCode
from trutina.storage_postgres.journal.model import JournalEntryModel, JournalLineModel
from trutina.storage_postgres.journal.repository import PostgresJournalRepo


class _FakeOrigError(Exception):
    def __init__(self) -> None:
        super().__init__("simulated postgres constraint violation")


def _integrity_error() -> IntegrityError:
    return IntegrityError("stmt", {}, _FakeOrigError())


def _entry_row(journal_number: int = 1) -> JournalEntryModel:
    return JournalEntryModel(
        journal_number=journal_number,
        posting_date=datetime(2025, 1, 1),
        description="Test entry",
    )


def _line_row(
    journal_number: int, line_index: int, account: str, debit: str, credit: str
) -> JournalLineModel:
    return JournalLineModel(
        journal_number=journal_number,
        line_index=line_index,
        account=account,
        debit_amount=Decimal(debit),
        credit_amount=Decimal(credit),
    )


@pytest.mark.unit
class TestPostgresJournalRepoToDomain:
    def test_reconstructs_entry_from_rows(self):
        entry_row = _entry_row(journal_number=1)
        lines = [
            _line_row(1, 0, "Cash", "100", "0"),
            _line_row(1, 1, "Sales Revenue", "0", "100"),
        ]

        entry = PostgresJournalRepo._to_domain(entry_row, lines)

        assert isinstance(entry, JournalEntry)
        assert entry.journal_number == 1
        assert entry.is_balanced is True
        assert len(entry.lines) == 2

    def test_preserves_line_order_by_line_index(self):
        entry_row = _entry_row(journal_number=1)
        lines = [
            _line_row(1, 0, "Cash", "150", "0"),
            _line_row(1, 1, "Sales Revenue", "0", "100"),
            _line_row(1, 2, "Sales Revenue", "0", "50"),
        ]

        entry = PostgresJournalRepo._to_domain(entry_row, lines)

        assert [line.account for line in entry.lines] == [
            "Cash",
            "Sales Revenue",
            "Sales Revenue",
        ]

    def test_preserves_description(self):
        entry_row = JournalEntryModel(
            journal_number=1, posting_date=datetime(2025, 1, 1), description="Payroll"
        )
        lines = [
            _line_row(1, 0, "Cash", "100", "0"),
            _line_row(1, 1, "Sales Revenue", "0", "100"),
        ]

        entry = PostgresJournalRepo._to_domain(entry_row, lines)

        assert entry.description == "Payroll"

    def test_preserves_none_description(self):
        entry_row = _entry_row(journal_number=1)
        entry_row.description = None
        lines = [
            _line_row(1, 0, "Cash", "100", "0"),
            _line_row(1, 1, "Sales Revenue", "0", "100"),
        ]

        entry = PostgresJournalRepo._to_domain(entry_row, lines)

        assert entry.description is None


@pytest.mark.unit
class TestPostgresJournalRepoOnDuplicate:
    def test_returns_app_error_with_journal_number_context(self):
        exc = _integrity_error()

        error = PostgresJournalRepo._on_duplicate(exc, journal_number=42)

        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert error.context["resource"] == "journal_entry"
        assert error.context["field"] == "journal_number"
        assert error.context["value"] == "42"
