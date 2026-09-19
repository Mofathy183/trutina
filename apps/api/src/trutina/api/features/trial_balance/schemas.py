"""HTTP response schemas for the trial balance API.

The trial balance feature exposes only a read-side HTTP contract. A
trial balance is a derived report computed from already-persisted
ledger postings, never submitted by a caller, so this module defines a
response schema only -- mirroring posting/schemas.py's own
output-only rationale for the same reason (see that module's
docstring).

``AccountBalanceItem`` represents one account's aggregated debit/credit
activity, while ``TrialBalanceResponse`` wraps the full report,
including the report-level computed totals and balanced flag.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from trutina.api.shared.response import SuccessResponse


class AccountBalanceItem(BaseModel):
    """Read-only representation of one account's aggregated posting activity.

    Mirrors the fields the service layer's AccountBalanceEntry
    provides, defined independently so a future change to that domain
    schema's internal shape doesn't automatically change this API's
    public response contract -- the same boundary rule PostingItem
    applies to LedgerPosting.

    debit_total and credit_total are both independently non-negative --
    unlike a single posting, an account legitimately accumulates both
    debit and credit activity over its history.
    """

    account: str = Field(description="The account this balance was aggregated for.")
    debit_total: Decimal = Field(
        description="Sum of every debit posting recorded against this account."
    )
    credit_total: Decimal = Field(
        description="Sum of every credit posting recorded against this account."
    )


class TrialBalanceResponse(SuccessResponse):
    """Successful response containing a complete trial balance report.

    ``entries`` is an empty list, not an error, when no account has
    posting activity in scope -- either the ledger has no postings at
    all, or ``as_of_date`` excludes everything recorded so far.
    ``total_debits``, ``total_credits``, and ``is_balanced`` mirror the
    service-layer ViewModel's own computed fields; this schema does not
    recompute them.
    """

    entries: list[AccountBalanceItem] = Field(
        description="One entry per account with posting activity in scope."
    )
    as_of_date: datetime | None = Field(
        description="The cutoff this report was generated for. None means all-time."
    )
    total_debits: Decimal = Field(description="Sum of every entry's debit_total.")
    total_credits: Decimal = Field(description="Sum of every entry's credit_total.")
    is_balanced: bool = Field(
        description="Whether total_debits equals total_credits for this report."
    )
