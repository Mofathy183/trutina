"""Application handler for the trial balance API.

Coordinates the single trial-balance workflow by delegating to
``TrialBalanceService``. Defines the boundary between the API layer and
the application layer, leaving request mapping, response presentation,
and error translation to their respective components -- mirroring
posting/handler.py's shape for this feature's single read-only action.
"""

from datetime import datetime

from trutina.core.trial_balance import TrialBalanceService, TrialBalanceViewModel


async def get_trial_balance_handler(
    service: TrialBalanceService,
    as_of_date: datetime | None,
) -> TrialBalanceViewModel:
    """Produce a trial balance, optionally scoped to a cutoff date.

    Args:
        service: The trial balance service coordinating the workflow.
        as_of_date: Optional cutoff. Only postings recorded on or
            before this value are included. None means all-time.

    Returns:
        The trial balance for the requested scope. This handler raises
        nothing of its own -- an empty ledger, or a cutoff that
        excludes every posting, simply yields a TrialBalanceViewModel
        with an empty ``entries`` list, per TrialBalanceRepo's
        documented contract.
    """
    return await service.get_trial_balance(as_of_date=as_of_date)
