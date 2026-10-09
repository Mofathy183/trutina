"""Integration tests for PostingService against real MongoDB infrastructure.

Does NOT re-verify posting derivation logic, frozen-record validation, or
Mongo document mapping/ordering — covered respectively by
``test_service.py`` (fake-repo unit tests),
``modules/posting/tests/test_ledger_posting_schema.py``, and
``infrastructure/mongo/posting/tests/test_repository_integration.py``.

PostingService is the most valuable integration target in the project: a
single posting workflow chains three services (Account, Journal, Posting)
and three Mongo repositories, none of which are exercised together
anywhere else in the suite. These tests prove that chain behaves correctly
as a unit, ending with one explicit cross-service workflow test that
re-reads everything back out through the service layer to catch
normalization drift, DTO-mapping drift, or wiring mistakes that no
single-service test could detect.
"""

import pytest
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import TEST_ACTOR, make_create_journal_input


@pytest.mark.integration
class TestPostingServicePostJournalEntry:
    async def test_posts_journal_and_postings_balance(self, services, simple_accounts):
        _account_service, journal_service, posting_service = services

        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        postings = await posting_service.post_journal_entry(
            entry.journal_number, actor=TEST_ACTOR
        )

        assert len(postings) == len(entry.lines)
        assert all(p.journal_number == entry.journal_number for p in postings)

        total_debits = sum(p.debit_amount or 0 for p in postings)
        total_credits = sum(p.credit_amount or 0 for p in postings)
        assert total_debits == total_credits


@pytest.mark.integration
class TestPostingServiceDuplicatePosting:
    async def test_posting_same_journal_twice_raises_business_error(
        self, services, simple_accounts
    ):
        """Proves the duplicate-posting guard (a check-then-save against
        real Mongo, not an in-memory fake) still holds the
        one-posting-per-journal-entry invariant.
        """
        _account_service, journal_service, posting_service = services

        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await posting_service.post_journal_entry(entry.journal_number, actor=TEST_ACTOR)

        with pytest.raises(AppError) as exc_info:
            await posting_service.post_journal_entry(
                entry.journal_number, actor=TEST_ACTOR
            )

        assert exc_info.value.code == ErrorCode.JOURNAL_ALREADY_POSTED


@pytest.mark.integration
class TestPostingServiceRetrieval:
    async def test_postings_retrievable_by_journal_number_preserve_invariants(
        self, services, simple_accounts
    ):
        _account_service, journal_service, posting_service = services

        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await posting_service.post_journal_entry(entry.journal_number, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_journal_number(
            entry.journal_number
        )

        assert len(result) == len(entry.lines)
        assert all(p.journal_number == entry.journal_number for p in result)
        assert sum(p.debit_amount or 0 for p in result) == sum(
            p.credit_amount or 0 for p in result
        )


@pytest.mark.integration
class TestCrossServiceWorkflow:
    async def test_account_journal_posting_remain_consistent_end_to_end(
        self, services, simple_accounts
    ):
        """The single end-to-end workflow test for this project.

        Walks Account -> Journal -> Posting creation, then re-reads every
        result back out through the service layer (not raw Mongo), to catch
        the class of bug no single-service test can: account-name
        normalization drift between AccountService and JournalLine,
        DTO-mapping drift between JournalViewModel and the lines
        PostingService derives from it, or a repository wired to the wrong
        service.
        """
        account_service, journal_service, posting_service = services

        cash = await account_service.get_account("1001")
        revenue = await account_service.get_account("4001")

        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        assert entry.is_balanced is True

        postings = await posting_service.post_journal_entry(
            entry.journal_number, actor=TEST_ACTOR
        )

        cash_postings = await posting_service.get_postings_by_account(cash.name)
        revenue_postings = await posting_service.get_postings_by_account(revenue.name)

        # Re-fetch the journal independently to confirm what was posted
        # matches what was actually persisted, not just what was returned
        # from the original create_journal_entry() call.
        refetched_entry = await journal_service.get_journal_entry(entry.journal_number)

        assert len(postings) == len(refetched_entry.lines)
        assert len(cash_postings) + len(revenue_postings) == len(postings)
        assert all(p.journal_number == refetched_entry.journal_number for p in postings)

        total_debits = sum(p.debit_amount or 0 for p in postings)
        total_credits = sum(p.credit_amount or 0 for p in postings)
        assert total_debits == total_credits == refetched_entry.total_debits
