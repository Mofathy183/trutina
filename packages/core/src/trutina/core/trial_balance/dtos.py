"""
Service-boundary DTOs for the trial_balance feature.

A trial balance is a derived, read-only report, so this module defines
an output-only view model only -- the same reasoning posting/dtos.py
documents for PostingViewModel: there is no input DTO because nothing
is submitted by a caller. TrialBalanceService derives a
TrialBalanceViewModel directly from the AccountBalanceEntry records
TrialBalanceRepo returns.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, computed_field

from .schemas.account_balance import AccountBalanceEntry

# ViewModels — data coming OUT of the service


class TrialBalanceViewModel(BaseModel):
    """Read-only view of a complete trial balance.

    Provides the service layer's public representation of a trial
    balance: one AccountBalanceEntry per account with posting activity
    in scope, plus report-level totals.

    ``total_debits``, ``total_credits``, and ``is_balanced`` are
    computed fields derived from ``entries`` so they can never disagree
    with the rows they summarize -- the same "derived, never stored"
    rule ``JournalEntry.total_debits`` / ``total_credits`` /
    ``is_balanced`` already follows (see packages/core/CONTEXT.md).
    """

    entries: list[AccountBalanceEntry]

    as_of_date: datetime | None = None
    """The cutoff this report was generated for. None means all-time --
    every posting ever recorded was included, with no upper date bound.
    """

    @computed_field
    @property
    def total_debits(self) -> Decimal:
        """Sum of every entry's debit_total.

        Derived on every access rather than cached, so it can never
        diverge from the entries it summarizes.
        """
        return sum((entry.debit_total for entry in self.entries), Decimal("0"))

    @computed_field
    @property
    def total_credits(self) -> Decimal:
        """Sum of every entry's credit_total.

        Derived on every access rather than cached, so it can never
        diverge from the entries it summarizes.
        """
        return sum((entry.credit_total for entry in self.entries), Decimal("0"))

    @computed_field
    @property
    def is_balanced(self) -> bool:
        """Whether total_debits equals total_credits.

        This is a read-model proving the books balanced, not an
        invariant this class enforces itself -- every JournalEntry
        backing these postings already validated its own balance at
        creation time (see JournalEntry.is_balanced). A False result
        here would indicate corrupted or partially migrated data, not
        a constructable-but-invalid trial balance -- the shape of this
        model does not prevent an unbalanced result from existing, it
        only makes one visible.
        """
        return self.total_debits == self.total_credits
