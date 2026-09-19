from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

from tests.factories import make_account_balance_entry


@pytest.mark.unit
class TestTrialBalanceViewModel:
    def test_creates_view_model_with_entries(self):
        entries = [make_account_balance_entry(account="Cash")]

        vm = TrialBalanceViewModel(entries=entries)

        assert vm.entries == entries

    def test_as_of_date_defaults_to_none(self):
        vm = TrialBalanceViewModel(entries=[])

        assert vm.as_of_date is None

    def test_as_of_date_is_preserved_when_provided(self):
        as_of = datetime(2025, 6, 30)

        vm = TrialBalanceViewModel(entries=[], as_of_date=as_of)

        assert vm.as_of_date == as_of

    def test_computes_total_debits_by_summing_entries(self):
        entries = [
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("300"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("300"),
            ),
            make_account_balance_entry(
                account="Accounts Receivable",
                debit_total=Decimal("50"),
                credit_total=Decimal("0"),
            ),
        ]

        vm = TrialBalanceViewModel(entries=entries)

        assert vm.total_debits == Decimal("350")

    def test_computes_total_credits_by_summing_entries(self):
        entries = [
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("300"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("300"),
            ),
        ]

        vm = TrialBalanceViewModel(entries=entries)

        assert vm.total_credits == Decimal("300")

    def test_is_balanced_true_when_totals_are_equal(self):
        entries = [
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("100"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("100"),
            ),
        ]

        vm = TrialBalanceViewModel(entries=entries)

        assert vm.is_balanced is True

    def test_is_balanced_false_when_totals_differ(self):
        """TrialBalanceViewModel does not itself enforce balance -- it
        reports whether the underlying entries happen to balance. A
        False result here signals corrupted or partially migrated
        data upstream, not an invalid view model (see the property's
        own docstring)."""
        entries = [
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("100"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("90"),
            ),
        ]

        vm = TrialBalanceViewModel(entries=entries)

        assert vm.is_balanced is False

    def test_empty_entries_produce_zero_totals(self):
        vm = TrialBalanceViewModel(entries=[])

        assert vm.total_debits == Decimal("0")
        assert vm.total_credits == Decimal("0")

    def test_empty_entries_are_considered_balanced(self):
        """Zero equals zero -- an empty report is trivially balanced,
        not an error state."""
        vm = TrialBalanceViewModel(entries=[])

        assert vm.is_balanced is True
