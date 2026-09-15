"""Integration tests for PostgresJournalRepo against real PostgreSQL.

Does not re-verify JournalEntry's own validation (balance, line count,
date range) -- covered by test_repository_unit.py and trutina-core's own
schema tests. These tests verify persistence behavior: that a reserved
journal number round-trips through save()/get_by_number(), that
next_journal_number() allocates monotonically and without reuse, and
that list_entries() returns every entry in journal-number order.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.journal.schemas.line import JournalLine
from trutina.shared.errors import AppError

from tests.factories import make_journal_entry


@pytest.mark.integration
class TestPostgresJournalRepoNextJournalNumber:
    async def test_returns_a_positive_integer(self, postgres_journal_repo):
        number = await postgres_journal_repo.next_journal_number()

        assert number > 0

    async def test_sequential_calls_return_increasing_numbers(
        self, postgres_journal_repo
    ):
        first = await postgres_journal_repo.next_journal_number()
        second = await postgres_journal_repo.next_journal_number()

        assert second > first

    async def test_advances_even_when_never_saved(self, postgres_journal_repo):
        reserved = await postgres_journal_repo.next_journal_number()
        next_number = await postgres_journal_repo.next_journal_number()

        assert next_number > reserved


@pytest.mark.integration
class TestPostgresJournalRepoSaveAndGet:
    async def test_saves_and_retrieves_entry(self, postgres_journal_repo):
        number = await postgres_journal_repo.next_journal_number()
        entry = make_journal_entry(journal_number=number)

        await postgres_journal_repo.save(entry)
        fetched = await postgres_journal_repo.get_by_number(number)

        assert fetched is not None
        assert fetched.journal_number == number
        assert fetched.is_balanced is True

    async def test_preserves_line_order(self, postgres_journal_repo):
        number = await postgres_journal_repo.next_journal_number()
        entry = make_journal_entry(
            journal_number=number,
            lines=[
                JournalLine(account="Cash", debit_amount=Decimal("150")),
                JournalLine(account="Sales Revenue", credit_amount=Decimal("100")),
                JournalLine(account="Accounts Receivable", credit_amount=Decimal("50")),
            ],
        )

        await postgres_journal_repo.save(entry)
        fetched = await postgres_journal_repo.get_by_number(number)

        assert [line.account for line in fetched.lines] == [
            "Cash",
            "Sales Revenue",
            "Accounts Receivable",
        ]

    async def test_preserves_posting_date_and_description(self, postgres_journal_repo):
        number = await postgres_journal_repo.next_journal_number()
        posting_date = datetime(2024, 6, 15)
        entry = make_journal_entry(
            journal_number=number, posting_date=posting_date, description="Payroll"
        )

        await postgres_journal_repo.save(entry)
        fetched = await postgres_journal_repo.get_by_number(number)

        assert fetched.posting_date == posting_date
        assert fetched.description == "Payroll"

    async def test_returns_none_when_journal_number_missing(
        self, postgres_journal_repo
    ):
        result = await postgres_journal_repo.get_by_number(999_999)

        assert result is None

    async def test_raises_when_saving_duplicate_journal_number(
        self, postgres_journal_repo
    ):
        number = await postgres_journal_repo.next_journal_number()
        await postgres_journal_repo.save(make_journal_entry(journal_number=number))

        with pytest.raises(AppError):
            await postgres_journal_repo.save(make_journal_entry(journal_number=number))


@pytest.mark.integration
class TestPostgresJournalRepoListEntries:
    async def test_returns_empty_list_when_no_entries_exist(
        self, postgres_journal_repo
    ):
        result = await postgres_journal_repo.list_entries()

        assert result == []

    async def test_returns_entries_ordered_by_journal_number(
        self, postgres_journal_repo
    ):
        first_number = await postgres_journal_repo.next_journal_number()
        await postgres_journal_repo.save(
            make_journal_entry(journal_number=first_number)
        )
        second_number = await postgres_journal_repo.next_journal_number()
        await postgres_journal_repo.save(
            make_journal_entry(journal_number=second_number)
        )

        result = await postgres_journal_repo.list_entries()
        numbers = [entry.journal_number for entry in result]

        assert numbers == sorted(numbers)
        assert first_number in numbers
        assert second_number in numbers
