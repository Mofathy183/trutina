"""Integration tests for PostgresTrialBalanceRepo against real PostgreSQL.

Does not re-verify AccountBalanceEntry's own field validation (covered
by trutina-core's own schema tests) or the row-to-domain mapping logic
(covered by test_repository_unit.py). These tests verify the
aggregation query itself: grouping, case-insensitive merging via
account_key, the as_of_date cutoff, and result ordering -- behavior
that can only be proven against a real query planner.

Postings reference journal_entries.journal_number via a RESTRICT
foreign key, so every posting written here must first have a real
journal_entries row -- seeded directly via postgres_journal_repo,
mirroring posting/tests/test_repository_integration.py's own
_seed_journal_entry helper.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from tests.factories import make_credit_posting, make_debit_posting, make_journal_entry


async def _seed_journal_entry(postgres_journal_repo, journal_number: int) -> None:
    await postgres_journal_repo.save(make_journal_entry(journal_number=journal_number))


@pytest.mark.integration
class TestPostgresTrialBalanceRepoGetAccountBalances:
    async def test_returns_empty_list_when_no_postings_exist(
        self, postgres_trial_balance_repo
    ):
        result = await postgres_trial_balance_repo.get_account_balances()

        assert result == []

    async def test_aggregates_debit_and_credit_totals_per_account(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash", amount=Decimal("300"), journal_number=1
                ),
                make_credit_posting(
                    account="Sales Revenue", amount=Decimal("300"), journal_number=1
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances()

        by_account = {entry.account: entry for entry in result}
        assert by_account["Cash"].debit_total == Decimal("300")
        assert by_account["Cash"].credit_total == Decimal("0")
        assert by_account["Sales Revenue"].credit_total == Decimal("300")
        assert by_account["Sales Revenue"].debit_total == Decimal("0")

    async def test_sums_multiple_postings_against_the_same_account(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await _seed_journal_entry(postgres_journal_repo, journal_number=2)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash", amount=Decimal("100"), journal_number=1
                ),
                make_credit_posting(
                    account="Sales Revenue", amount=Decimal("100"), journal_number=1
                ),
            ]
        )
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash", amount=Decimal("50"), journal_number=2
                ),
                make_credit_posting(
                    account="Sales Revenue", amount=Decimal("50"), journal_number=2
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances()

        by_account = {entry.account: entry for entry in result}
        assert by_account["Cash"].debit_total == Decimal("150")
        assert by_account["Sales Revenue"].credit_total == Decimal("150")

    async def test_groups_case_insensitive_account_names_into_one_entry(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash", amount=Decimal("100"), journal_number=1
                ),
                make_debit_posting(
                    account="cash", amount=Decimal("50"), journal_number=1
                ),
                make_credit_posting(
                    account="Sales Revenue", amount=Decimal("150"), journal_number=1
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances()

        cash_entries = [entry for entry in result if entry.account.lower() == "cash"]
        assert len(cash_entries) == 1
        assert cash_entries[0].debit_total == Decimal("150")

    async def test_orders_results_ascending_by_account_name(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Sales Revenue", amount=Decimal("50"), journal_number=1
                ),
                make_credit_posting(
                    account="Accounts Receivable",
                    amount=Decimal("50"),
                    journal_number=1,
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances()

        assert [entry.account for entry in result] == sorted(
            entry.account for entry in result
        )

    async def test_excludes_postings_recorded_after_as_of_date(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await _seed_journal_entry(postgres_journal_repo, journal_number=2)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash",
                    amount=Decimal("100"),
                    journal_number=1,
                    posting_date=datetime(2025, 1, 1),
                ),
                make_credit_posting(
                    account="Sales Revenue",
                    amount=Decimal("100"),
                    journal_number=1,
                    posting_date=datetime(2025, 1, 1),
                ),
            ]
        )
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash",
                    amount=Decimal("999"),
                    journal_number=2,
                    posting_date=datetime(2025, 6, 1),
                ),
                make_credit_posting(
                    account="Sales Revenue",
                    amount=Decimal("999"),
                    journal_number=2,
                    posting_date=datetime(2025, 6, 1),
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances(
            as_of_date=datetime(2025, 3, 1)
        )

        by_account = {entry.account: entry for entry in result}
        assert by_account["Cash"].debit_total == Decimal("100")

    async def test_includes_all_postings_when_as_of_date_is_none(
        self, postgres_trial_balance_repo, postgres_journal_repo, postgres_posting_repo
    ):
        await _seed_journal_entry(postgres_journal_repo, journal_number=1)
        await postgres_posting_repo.save_many(
            [
                make_debit_posting(
                    account="Cash",
                    amount=Decimal("100"),
                    journal_number=1,
                    posting_date=datetime(2025, 6, 1),
                ),
                make_credit_posting(
                    account="Sales Revenue",
                    amount=Decimal("100"),
                    journal_number=1,
                    posting_date=datetime(2025, 6, 1),
                ),
            ]
        )

        result = await postgres_trial_balance_repo.get_account_balances(as_of_date=None)

        by_account = {entry.account: entry for entry in result}
        assert by_account["Cash"].debit_total == Decimal("100")
