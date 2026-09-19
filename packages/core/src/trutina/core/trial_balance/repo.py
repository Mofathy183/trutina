"""Repository contract for the trial_balance feature.

Defines the persistence-read boundary used by TrialBalanceService.
Unlike account/journal/posting's repository contracts, this one is
read-only -- a trial balance is never written, only computed from
postings that already exist.

Implementations must remain asynchronous, must not contain business
rules beyond the aggregation itself, and must translate storage-specific
failures into AppError instances before they cross this boundary.

Exception Contract
------------------

Concrete implementations must translate storage-specific failures into
AppError before they cross the repository boundary.

Services depend only on AppError and must never be coupled to storage
libraries, database drivers, or transport-specific exceptions.

The exact translation strategy is implementation-specific.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from .schemas.account_balance import AccountBalanceEntry


class TrialBalanceRepo(ABC):
    """Read-only persistence contract for trial balance aggregation.

    Defines the single aggregation query required by trial balance
    workflows: sum every posting's debit and credit amounts, grouped by
    account, optionally scoped to postings recorded on or before a
    given date.

    Implementations must:

    - Remain asynchronous.
    - Avoid business-rule enforcement beyond the aggregation itself --
        computing report-level totals or an is_balanced flag is
        TrialBalanceService's responsibility, not this contract's.
    - Return an empty list when no postings exist in scope, never
        raise for that case.
    - Include only accounts with at least one posting in scope. An
        account with no matching postings must not appear as a
        zero-value row (per the Trial Balance Feature Plan ADR, D3 --
        full-chart inclusion with zero-padding is deferred to v2 and
        belongs at the service layer, not this contract).
    - Translate storage-specific failures into AppError.
    - Remain independent of CLI, Rich, and Typer concerns.

    The contract defines the aggregation's persistence behavior only.
    Deriving report-level totals (total_debits, total_credits,
    is_balanced) from the returned entries remains the responsibility
    of TrialBalanceService.
    """

    @abstractmethod
    async def get_account_balances(
        self,
        as_of_date: datetime | None = None,
    ) -> list[AccountBalanceEntry]:
        """Aggregate every posting's amounts, grouped by account.

        Sums debit_amount and credit_amount separately per account
        across every LedgerPosting in scope. When as_of_date is given,
        only postings with posting_date <= as_of_date are included in
        the aggregation; when omitted, every posting ever recorded is
        included (an all-time trial balance).

        Args:
            as_of_date: Optional cutoff. Postings recorded after this
                date are excluded from the aggregation. None means
                all-time -- no upper bound.

        Returns:
            One AccountBalanceEntry per account with at least one
            posting in scope, ordered ascending by account name.
            Returns an empty list when no postings exist in scope.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...
