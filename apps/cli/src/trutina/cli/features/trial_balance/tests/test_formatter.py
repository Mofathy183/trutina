from datetime import datetime
from decimal import Decimal

import pytest
from rich.panel import Panel
from rich.text import Text
from trutina.cli.features.trial_balance.formatter import (
    build_trial_balance,
    print_trial_balance,
)
from trutina.cli.shared.ui import console
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

from tests.factories import make_account_balance_entry


def _vm(entries=None, as_of_date=None) -> TrialBalanceViewModel:
    return TrialBalanceViewModel(entries=entries or [], as_of_date=as_of_date)


@pytest.mark.unit
class TestBuildTrialBalance:
    def test_returns_panel(self):
        result = build_trial_balance(_vm([make_account_balance_entry()]))

        assert isinstance(result, Panel)

    def test_empty_entries_returns_warning_text(self):
        result = build_trial_balance(_vm([]))

        assert isinstance(result.renderable, Text)
        assert "No postings found" in result.renderable.plain
        assert result.style == "warning"

    def test_title_is_all_time_when_no_as_of_date(self):
        result = build_trial_balance(_vm([make_account_balance_entry()]))

        assert result.title == "Trial Balance"

    def test_title_shows_as_of_date_when_scoped(self):
        result = build_trial_balance(
            _vm([make_account_balance_entry()], as_of_date=datetime(2025, 6, 15))
        )

        assert result.title == "Trial Balance (as of 2025-06-15)"

    def test_shows_account_and_amounts(self):
        vm = _vm(
            [make_account_balance_entry(account="Cash", debit_total=Decimal("250.00"))]
        )

        with console.capture() as capture:
            console.print(build_trial_balance(vm))

        output = capture.get()
        assert "Cash" in output
        assert "250.00" in output

    def test_shows_balanced_summary_when_totals_match(self):
        vm = _vm(
            [
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

        with console.capture() as capture:
            console.print(build_trial_balance(vm))

        assert "Balanced: Yes" in capture.get()

    def test_shows_unbalanced_summary_when_totals_differ(self):
        vm = _vm(
            [
                make_account_balance_entry(
                    account="Cash",
                    debit_total=Decimal("100"),
                    credit_total=Decimal("0"),
                ),
                make_account_balance_entry(
                    account="Sales Revenue",
                    debit_total=Decimal("0"),
                    credit_total=Decimal("90"),
                ),
            ]
        )

        with console.capture() as capture:
            console.print(build_trial_balance(vm))

        assert "Balanced: No" in capture.get()


@pytest.mark.unit
class TestPrintTrialBalance:
    def test_matches_build_output(self):
        vm = _vm([make_account_balance_entry()])

        with console.capture() as build_capture:
            console.print(build_trial_balance(vm))

        with console.capture() as print_capture:
            print_trial_balance(vm)

        assert build_capture.get() == print_capture.get()
