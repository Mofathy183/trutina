"""Unit tests for PostgresPostingRepo's pure mapping logic.

Covers reconstruction of a LedgerPosting from a PostingModel row, and
conflict translation -- both require no database. save_many()/
get_by_account()/get_by_journal_number()'s actual SQL behavior is
covered under test_repository_integration.py.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.shared.errors import ErrorCode
from trutina.storage_postgres.posting.model import PostingModel
from trutina.storage_postgres.posting.repository import PostgresPostingRepo


class _FakeOrigError(Exception):
    def __init__(self) -> None:
        super().__init__("simulated postgres constraint violation")


def _integrity_error() -> IntegrityError:
    return IntegrityError("stmt", {}, _FakeOrigError())


def _posting_row(
    *,
    account: str = "Cash",
    debit: str = "100",
    credit: str = "0",
    journal_number: int = 1,
    line_index: int = 0,
) -> PostingModel:
    return PostingModel(
        account=account,
        account_key=account.strip().casefold(),
        debit_amount=Decimal(debit),
        credit_amount=Decimal(credit),
        journal_number=journal_number,
        posting_date=datetime(2025, 1, 1),
        line_index=line_index,
    )


@pytest.mark.unit
class TestPostgresPostingRepoToDomain:
    def test_reconstructs_debit_posting(self):
        row = _posting_row(account="Cash", debit="100", credit="0")

        posting = PostgresPostingRepo._to_domain(row)

        assert isinstance(posting, LedgerPosting)
        assert posting.account == "Cash"
        assert posting.is_debit is True
        assert posting.debit_amount == Decimal("100")

    def test_reconstructs_credit_posting(self):
        row = _posting_row(account="Sales Revenue", debit="0", credit="100")

        posting = PostgresPostingRepo._to_domain(row)

        assert posting.is_debit is False
        assert posting.credit_amount == Decimal("100")

    def test_preserves_journal_number_and_posting_date(self):
        row = _posting_row(journal_number=42)
        row.posting_date = datetime(2024, 6, 15)

        posting = PostgresPostingRepo._to_domain(row)

        assert posting.journal_number == 42
        assert posting.posting_date == datetime(2024, 6, 15)


@pytest.mark.unit
class TestPostgresPostingRepoOnDuplicate:
    def test_maps_collision_to_journal_already_posted(self):
        exc = _integrity_error()
        postings = [
            LedgerPosting(
                account="Cash",
                debit_amount=Decimal("100"),
                journal_number=7,
                posting_date=datetime(2025, 1, 1),
            )
        ]

        error = PostgresPostingRepo._on_duplicate(exc, postings)

        assert error.code == ErrorCode.JOURNAL_ALREADY_POSTED
        assert error.context["resource"] == "journal_entry"
        assert error.context["field"] == "journal_number"
        assert error.context["value"] == "7"

    def test_handles_empty_batch_without_raising(self):
        exc = _integrity_error()

        error = PostgresPostingRepo._on_duplicate(exc, postings=[])

        assert error.code == ErrorCode.JOURNAL_ALREADY_POSTED
        assert error.context["value"] == "None"
