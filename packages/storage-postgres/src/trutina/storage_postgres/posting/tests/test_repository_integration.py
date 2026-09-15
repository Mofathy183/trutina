"""Integration tests for PostgresPostingRepo against real PostgreSQL.

Does not re-verify LedgerPosting's own validation (single-sidedness,
date range) -- covered by test_repository_unit.py and trutina-core's own
schema tests, or PostingService's derivation/orchestration logic --
covered by packages/core's own service tests. These tests verify
persistence behavior only: that a batch round-trips through
save_many()/get_by_journal_number(), that get_by_account() matches
case-insensitively via account_key, and that the UNIQUE
(journal_number, line_index) constraint actually rejects a colliding
batch rather than silently duplicating postings.

Postings reference journal_entries.journal_number via a RESTRICT foreign
key (see posting/model.py), so every posting written here must first
have a real journal_entries row -- these tests seed one directly via
postgres_journal_repo rather than duplicating that setup by hand.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_journal_entry


async def _seed_journal_entry(postgres_journal_repo, journal_number: int) -> None:
    await postgres_journal_repo.save(make_journal_entry(journal_number=journal_number))


def _debit_posting(
    journal_number: int, account: str = "Cash", amount: str = "100"
) -> LedgerPosting:
    return LedgerPosting(
        account=account,
        debit_amount=Decimal(amount),
        journal_number=journal_number,
        posting_date=datetime(2025, 1, 1),
    )


def _credit_posting(
    journal_number: int, account: str = "Sales Revenue", amount: str = "100"
) -> LedgerPosting:
    return LedgerPosting(
        account=account,
        credit_amount=Decimal(amount),
        journal_number=journal_number,
        posting_date=datetime(2025, 1, 1),
    )


@pytest.mark.integration
class TestPostgresPostingRepoSaveMany:
    async def test_saves_and_retrieves_batch(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        batch = [_debit_posting(1), _credit_posting(1)]

        await postgres_posting_repo.save_many(batch)
        result = await postgres_posting_repo.get_by_journal_number(1)

        assert len(result) == 2

    async def test_preserves_save_order_via_line_index(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        batch = [
            _debit_posting(1, account="Cash", amount="300"),
            _credit_posting(1, account="Sales Revenue", amount="200"),
            _credit_posting(1, account="Accounts Receivable", amount="100"),
        ]

        await postgres_posting_repo.save_many(batch)
        result = await postgres_posting_repo.get_by_journal_number(1)

        assert [p.account for p in result] == [
            "Cash",
            "Sales Revenue",
            "Accounts Receivable",
        ]

    async def test_raises_journal_already_posted_on_duplicate_batch(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        batch = [_debit_posting(1), _credit_posting(1)]
        await postgres_posting_repo.save_many(batch)

        with pytest.raises(AppError) as exc_info:
            await postgres_posting_repo.save_many(batch)

        assert exc_info.value.code == ErrorCode.JOURNAL_ALREADY_POSTED

    async def test_does_not_persist_partial_batch_on_collision(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        batch = [_debit_posting(1), _credit_posting(1)]
        await postgres_posting_repo.save_many(batch)

        with pytest.raises(AppError):
            await postgres_posting_repo.save_many(
                [_debit_posting(1, account="Cash", amount="999")]
            )

        result = await postgres_posting_repo.get_by_journal_number(1)
        assert len(result) == 2
        assert all(p.debit_amount != Decimal("999") for p in result if p.is_debit)


@pytest.mark.integration
class TestPostgresPostingRepoGetByAccount:
    async def test_returns_postings_for_account(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many([_debit_posting(1), _credit_posting(1)])

        result = await postgres_posting_repo.get_by_account("Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"

    async def test_matches_account_case_insensitively(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many([_debit_posting(1), _credit_posting(1)])

        result = await postgres_posting_repo.get_by_account("cAsH")

        assert len(result) == 1
        assert result[0].account == "Cash"

    async def test_returns_empty_list_when_no_postings_for_account(
        self, postgres_posting_repo
    ):
        result = await postgres_posting_repo.get_by_account("Cash")

        assert result == []


@pytest.mark.integration
class TestPostgresPostingRepoGetByJournalNumber:
    async def test_returns_empty_list_when_no_postings_exist(
        self, postgres_posting_repo
    ):
        result = await postgres_posting_repo.get_by_journal_number(999)

        assert result == []

    async def test_separates_postings_by_journal_number(
        self, postgres_posting_repo, postgres_journal_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await _seed_journal_entry(postgres_journal_repo, journal_number=2)
        await postgres_posting_repo.save_many([_debit_posting(1), _credit_posting(1)])
        await postgres_posting_repo.save_many([_debit_posting(2), _credit_posting(2)])

        result1 = await postgres_posting_repo.get_by_journal_number(1)
        result2 = await postgres_posting_repo.get_by_journal_number(2)

        assert len(result1) == 2
        assert len(result2) == 2
        assert all(p.journal_number == 1 for p in result1)
        assert all(p.journal_number == 2 for p in result2)
