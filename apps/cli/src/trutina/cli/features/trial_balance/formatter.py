"""
Trial Balance CLI formatting for Trutina.

Consumes TrialBalanceViewModel from trutina.core.reporting and renders
it as Rich renderables. This module never imports AccountBalanceEntry
or any other reporting domain schema directly -- the ViewModel is the
only contract it depends on, the same boundary rule
cli/features/posting/formatter.py enforces for PostingViewModel.

Build functions are pure: they construct and return a Rich renderable
without printing it. Print functions are thin wrappers that build then
print. Mirrors cli/features/posting/formatter.py's build/print split
exactly.
"""

from decimal import Decimal

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from trutina.cli.shared.ui import console, panel, table
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fmt_amount(amount: Decimal) -> str:
    """Format a non-negative Decimal total for display.

    Unlike PostingViewModel's debit_amount/credit_amount (Decimal |
    None, single-sided), AccountBalanceEntry's debit_total/credit_total
    are always-present, independently non-negative Decimals -- an
    account legitimately accumulates both debit and credit activity
    over its history. There is no None case to render as blank here.

    Args:
        amount: The aggregated Decimal total from the ViewModel.

    Returns:
        A two-decimal string such as "1,000.00".
    """
    return f"{amount:,.2f}"


def _fmt_as_of_date(vm: TrialBalanceViewModel) -> str | None:
    """Format the report's cutoff date for the panel title, if scoped."""
    if vm.as_of_date is None:
        return None
    return vm.as_of_date.strftime("%Y-%m-%d")


def _build_trial_balance_table(vm: TrialBalanceViewModel):
    """Build the per-account debit/credit totals table.

    One row per AccountBalanceEntry, ordered exactly as the ViewModel
    provides them (ascending by account name, per TrialBalanceRepo's
    contract) -- this function does not re-sort.

    Args:
        vm: The trial balance ViewModel to render.

    Returns:
        A configured Rich Table with all entries added.
    """
    built = table(
        ("Account", "left", "assets"),
        ("Debit", "right", "debit"),
        ("Credit", "right", "credit"),
    )
    for entry in vm.entries:
        built.add_row(
            entry.account,
            _fmt_amount(entry.debit_total),
            _fmt_amount(entry.credit_total),
        )
    return built


def _build_summary_line(vm: TrialBalanceViewModel) -> Text:
    """Build the report-level totals/balanced summary line.

    total_debits, total_credits, and is_balanced are all computed
    fields on the ViewModel itself (see TrialBalanceViewModel), so this
    formatter never sums entries or checks the balance itself -- it
    only renders what the ViewModel already derived.

    Args:
        vm: The trial balance ViewModel to summarize.

    Returns:
        A single styled Text line -- warning style if the ledger is
        not balanced (which would indicate corrupted or partially
        migrated data, not a normal outcome), info style otherwise.
    """
    style = "info" if vm.is_balanced else "warning"
    balanced_word = "Yes" if vm.is_balanced else "No"
    return Text(
        f"Total Debits: {_fmt_amount(vm.total_debits)}    "
        f"Total Credits: {_fmt_amount(vm.total_credits)}    "
        f"Balanced: {balanced_word}",
        style=style,
    )


# ---------------------------------------------------------------------------
# Public build functions -- pure, return a renderable, never print
# ---------------------------------------------------------------------------


def build_trial_balance(vm: TrialBalanceViewModel) -> Panel:
    """Build a summary panel for a trial balance report.

    Returns an explicit empty-state panel when no accounts have
    posting activity in scope (as_of_date excludes everything, or the
    ledger is empty), otherwise a panel containing the per-account
    table plus the report-level summary line.

    Args:
        vm: The trial balance ViewModel to render.

    Returns:
        A configured Rich Panel. Not printed.
    """
    as_of = _fmt_as_of_date(vm)
    title = "Trial Balance" if as_of is None else f"Trial Balance (as of {as_of})"

    if not vm.entries:
        return panel(
            Text("No postings found.", style="warning"),
            title=title,
            style="warning",
        )

    content = Group(
        _build_trial_balance_table(vm),
        Text(""),
        _build_summary_line(vm),
    )
    return panel(content, title=title)


# ---------------------------------------------------------------------------
# Public print functions -- thin: build, then print
# ---------------------------------------------------------------------------


def print_trial_balance(vm: TrialBalanceViewModel) -> None:
    """Build and print the trial balance summary panel.

    Args:
        vm: The trial balance ViewModel to render.
    """
    console.print(build_trial_balance(vm))
