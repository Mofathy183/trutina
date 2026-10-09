"""Integration tests for JournalService against real MongoDB infrastructure.

Does NOT re-verify balance/line-count/date validation (covered by
``test_service.py`` against ``FakeAccountRepo``/``FakeJournalRepo``) or
Mongo document mapping (covered by
``infrastructure/mongo/journal/tests/test_repository_integration.py``).

These tests exist to prove three seams the unit tests cannot reach because
they use fakes:

1. Account references resolve against a chart built from a *real*
    ``AccountService`` snapshot, not an in-memory ``FakeAccountRepo`` dict.
2. Journal-number allocation goes through MongoDB's real atomic counter
    (``findOneAndUpdate`` / ``$inc``) rather than ``FakeJournalRepo``'s
    plain incrementing int.
3. A journal entry built, persisted, and re-fetched through real Mongo
    still reports as balanced and matches what was submitted.
"""

import pytest
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import TEST_ACTOR, make_create_journal_input


@pytest.mark.integration
class TestJournalServiceCreateAndRetrieve:
    async def test_create_and_retrieve_round_trip_is_balanced(
        self, services, simple_accounts
    ):
        _account_service, journal_service, _posting_service = services

        created = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        fetched = await journal_service.get_journal_entry(created.journal_number)

        assert fetched.journal_number == created.journal_number
        assert fetched.is_balanced is True
        assert fetched.total_debits == fetched.total_credits


@pytest.mark.integration
class TestJournalServiceUnknownAccount:
    async def test_unknown_account_raises_business_error(self, services):
        """No accounts are seeded here (no ``simple_accounts``), so every
        line's account reference is unresolvable against the real chart.
        """
        _account_service, journal_service, _posting_service = services

        with pytest.raises(AppError) as exc_info:
            await journal_service.create_journal_entry(
                make_create_journal_input(), actor=TEST_ACTOR
            )

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.integration
class TestJournalServiceNumberAllocation:
    async def test_journal_numbers_increase_monotonically(
        self, services, simple_accounts
    ):
        """Verifies monotonic allocation only — does not assume numbering
        starts at 1, since that's an implementation detail of the counter,
        not a business invariant.
        """
        _account_service, journal_service, _posting_service = services

        first = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        second = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        assert second.journal_number == first.journal_number + 1
