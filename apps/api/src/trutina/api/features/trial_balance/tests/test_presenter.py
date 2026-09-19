from datetime import datetime
from decimal import Decimal

import pytest
from trutina.api.features.trial_balance.presenter import (
    to_account_balance_item,
    to_trial_balance_response,
)
from trutina.api.features.trial_balance.schemas import (
    AccountBalanceItem,
    TrialBalanceResponse,
)
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

from tests.factories import make_account_balance_entry


@pytest.mark.unit
class TestToAccountBalanceItem:
    def test_returns_account_balance_item_instance(self):
        result = to_account_balance_item(make_account_balance_entry())

        assert isinstance(result, AccountBalanceItem)

    def test_maps_fields(self):
        entry = make_account_balance_entry(
            account="Cash", debit_total=Decimal("100.00"), credit_total=Decimal("0.00")
        )

        result = to_account_balance_item(entry)

        assert result.account == "Cash"
        assert result.debit_total == Decimal("100.00")
        assert result.credit_total == Decimal("0.00")


@pytest.mark.unit
class TestToTrialBalanceResponse:
    def test_returns_trial_balance_response_instance(self):
        vm = TrialBalanceViewModel(entries=[make_account_balance_entry()])

        result = to_trial_balance_response(vm)

        assert isinstance(result, TrialBalanceResponse)

    def test_wraps_every_entry(self):
        vm = TrialBalanceViewModel(
            entries=[
                make_account_balance_entry(account="Cash"),
                make_account_balance_entry(account="Sales Revenue"),
            ]
        )

        result = to_trial_balance_response(vm)

        assert len(result.entries) == 2

    def test_preserves_order(self):
        vm = TrialBalanceViewModel(
            entries=[
                make_account_balance_entry(account="Cash"),
                make_account_balance_entry(account="Sales Revenue"),
            ]
        )

        result = to_trial_balance_response(vm)

        assert result.entries[0].account == "Cash"
        assert result.entries[1].account == "Sales Revenue"

    def test_preserves_computed_totals_and_balanced_flag(self):
        vm = TrialBalanceViewModel(
            entries=[
                make_account_balance_entry(
                    account="Cash",
                    debit_total=Decimal("100"),
                    credit_total=Decimal("0"),
                ),
                make_account_balance_entry(
                    account="Sales Revenue",
                    debit_total=Decimal("0"),
                    credit_total=Decimal("100"),
                ),
            ]
        )

        result = to_trial_balance_response(vm)

        assert result.total_debits == Decimal("100")
        assert result.total_credits == Decimal("100")
        assert result.is_balanced is True

    def test_empty_entries_returns_empty_list(self):
        vm = TrialBalanceViewModel(entries=[])

        result = to_trial_balance_response(vm)

        assert result.entries == []

    def test_success_flag_is_true(self):
        vm = TrialBalanceViewModel(entries=[])

        result = to_trial_balance_response(vm)

        assert result.success is True

    def test_preserves_as_of_date(self):
        cutoff = datetime(2025, 1, 1)
        vm = TrialBalanceViewModel(entries=[], as_of_date=cutoff)

        result = to_trial_balance_response(vm)

        assert result.as_of_date == cutoff

    def test_as_of_date_is_none_for_all_time_report(self):
        vm = TrialBalanceViewModel(entries=[])

        result = to_trial_balance_response(vm)

        assert result.as_of_date is None
