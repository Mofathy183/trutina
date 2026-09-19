"""Integration tests for TrialBalanceService against real PostgreSQL infrastructure.

Does not re-verify AccountBalanceEntry's validation (covered by
schema unit tests), TrialBalanceViewModel's computed fields (covered by
test_dtos.py's unit tests), TrialBalanceService's pass-through behavior
against a fake repo (covered by test_service_unit.py), or the
aggregation query's own SQL correctness -- grouping, case-insensitive
merging, as_of_date filtering, ordering -- all covered by
storage_postgres/trial_balance/tests/test_repository_integration.py.

What this file proves that no other tier can: that TrialBalanceService,
account/journal/posting's real services, and PostgresTrialBalanceRepo
actually agree with each other end to end -- the same "no single
service test could detect a wiring mistake between packages" argument
posting/tests/test_service_integration.py makes for its own
cross-service coverage, one hop further removed here since
TrialBalanceService sits downstream of postings it never writes itself.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from tests.factories import make_create_journal_input


@pytest.mark.integration
class TestTrialBalanceServiceGetTrialBalance:
    async def test_returns_empty_report_when_no_postings_exist(
        self, trial_balance_service
    ):
        result = await trial_balance_service.get_trial_balance()

        assert result.entries == []
        assert result.is_balanced is True

    async def test_reflects_a_single_posted_journal_entry(
        self, services, simple_accounts, trial_balance_service
    ):
        _account_service, journal_service, posting_service = services

        entry = await journal_service.create_journal_entry(make_create_journal_input())
        await posting_service.post_journal_entry(entry.journal_number)

        result = await trial_balance_service.get_trial_balance()

        by_account = {e.account: e for e in result.entries}
        assert by_account["Cash"].debit_total == Decimal("100")
        assert by_account["Sales Revenue"].credit_total == Decimal("100")
        assert result.is_balanced is True

    async def test_aggregates_multiple_posted_entries(
        self, services, simple_accounts, trial_balance_service
    ):
        _account_service, journal_service, posting_service = services

        first = await journal_service.create_journal_entry(
            make_create_journal_input(description="First")
        )
        second = await journal_service.create_journal_entry(
            make_create_journal_input(description="Second")
        )
        await posting_service.post_journal_entry(first.journal_number)
        await posting_service.post_journal_entry(second.journal_number)

        result = await trial_balance_service.get_trial_balance()

        by_account = {e.account: e for e in result.entries}
        assert by_account["Cash"].debit_total == Decimal("200")
        assert by_account["Sales Revenue"].credit_total == Decimal("200")
        assert result.total_debits == result.total_credits == Decimal("200")
        assert result.is_balanced is True

    async def test_unposted_journal_entries_do_not_appear(
        self, services, simple_accounts, trial_balance_service
    ):
        """A journal entry that exists but was never posted has no
        LedgerPosting records yet, so it must contribute nothing to
        the trial balance -- proving TrialBalanceService reads from
        postings, not journal entries directly."""
        _account_service, journal_service, _posting_service = services

        await journal_service.create_journal_entry(make_create_journal_input())

        result = await trial_balance_service.get_trial_balance()

        assert result.entries == []

    async def test_respects_as_of_date_end_to_end(
        self, services, simple_accounts, trial_balance_service
    ):
        _account_service, journal_service, posting_service = services

        early = await journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 1, 1))
        )
        late = await journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 6, 1))
        )
        await posting_service.post_journal_entry(early.journal_number)
        await posting_service.post_journal_entry(late.journal_number)

        result = await trial_balance_service.get_trial_balance(
            as_of_date=datetime(2025, 3, 1)
        )

        by_account = {e.account: e for e in result.entries}
        assert by_account["Cash"].debit_total == Decimal("100")
        assert result.as_of_date == datetime(2025, 3, 1)

    async def test_all_time_report_includes_postings_at_every_date(
        self, services, simple_accounts, trial_balance_service
    ):
        _account_service, journal_service, posting_service = services

        early = await journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 1, 1))
        )
        late = await journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 6, 1))
        )
        await posting_service.post_journal_entry(early.journal_number)
        await posting_service.post_journal_entry(late.journal_number)

        result = await trial_balance_service.get_trial_balance(as_of_date=None)

        by_account = {e.account: e for e in result.entries}
        assert by_account["Cash"].debit_total == Decimal("200")
        assert result.as_of_date is None
