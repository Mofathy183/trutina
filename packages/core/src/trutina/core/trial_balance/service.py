"""
Service layer for the trial_balance feature.

TrialBalanceService derives a trial balance from existing ledger
postings via TrialBalanceRepo. It is the only entry point for
producing a TrialBalanceViewModel.

Responsibilities:

- Retrieve aggregated account balances via TrialBalanceRepo, optionally
    scoped to an as_of_date cutoff.
- Wrap the result in a TrialBalanceViewModel, which derives its own
    report-level totals (total_debits, total_credits, is_balanced) as
    computed fields -- this service does not compute them itself.
- Log "trial_balance.generated" through the standard library's logging
    module once a report has been produced. Unlike the read-only
    lookups on the other three services, report generation is
    deliberately logged -- it is the one output this service exists to
    produce, not a passive lookup. Only entry count and the requested
    as_of_date are logged, never any amount. This module imports
    nothing from trutina.observability or structlog.

TrialBalanceService has no peer-service dependency, unlike
PostingService (which depends on JournalService) or JournalService
(which depends on AccountService). A trial balance is read entirely
from already-persisted postings; it does not need to re-derive or
re-validate anything from the journal or account domains, because
those invariants were already enforced when the underlying postings
were created (see packages/core/CONTEXT.md's discussion of why
PostingService performs zero re-validation of what JournalService
already validated -- the same reasoning applies here, one layer
further removed).
"""

import logging
from datetime import datetime

from .dtos import TrialBalanceViewModel
from .repo import TrialBalanceRepo

logger = logging.getLogger(__name__)


class TrialBalanceService:
    """Coordinates trial balance derivation.

    TrialBalanceService turns the current (or historical, as of a
    given date) state of the ledger into a single read-only report.
    It performs no persistence of its own -- TrialBalanceRepo is a
    read-only contract, so there is nothing for this service to save.

    Attributes:
        _repo: The read-only persistence boundary for aggregated
            account balances.
    """

    def __init__(self, repo: TrialBalanceRepo) -> None:
        """Initialize the service with its injected repository.

        Args:
            repo: Repository implementation used to aggregate account
                balances.
        """
        self._repo = repo

    async def get_trial_balance(
        self,
        as_of_date: datetime | None = None,
    ) -> TrialBalanceViewModel:
        """Produce a trial balance from the current ledger state.

        Retrieves aggregated account balances from TrialBalanceRepo and
        wraps them in a TrialBalanceViewModel. The view model's
        total_debits, total_credits, and is_balanced are derived by
        the view model itself from the returned entries -- this method
        does not compute or verify them. Logs "trial_balance.generated"
        with the entry count and the requested as_of_date -- never any
        debit/credit amount.

        Args:
            as_of_date: Optional cutoff. When given, only postings
                recorded on or before this date are included. None
                means all-time -- every posting ever recorded.

        Returns:
            A TrialBalanceViewModel containing one entry per account
            with posting activity in scope, plus the requested
            as_of_date for the caller's own reference.
        """
        entries = await self._repo.get_account_balances(as_of_date=as_of_date)
        view_model = TrialBalanceViewModel(entries=entries, as_of_date=as_of_date)

        logger.info(
            "trial_balance.generated",
            extra={
                "context": {
                    "entry_count": len(entries),
                    "as_of_date": as_of_date.isoformat() if as_of_date else None,
                }
            },
        )

        return view_model
