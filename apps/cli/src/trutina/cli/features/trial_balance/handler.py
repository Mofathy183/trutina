"""
Application-level use case for the Trial Balance CLI feature.

Mirrors cli/features/posting/handler.py: accepts an already-validated
value (here, an optional datetime rather than a DTO, per parser.py's
module docstring) and knows nothing about Typer, Click, or terminal
presentation. Resolves TrialBalanceService lazily from the supplied
CliContext, exactly as every other feature handler does.
"""

from datetime import datetime

from trutina.cli.composition.context import CliContext
from trutina.core.trial_balance import TrialBalanceViewModel


async def get_trial_balance_handler(
    ctx: CliContext,
    as_of_date: datetime | None,
) -> TrialBalanceViewModel:
    """Produce a trial balance, optionally scoped to a cutoff date.

    Args:
        ctx: The CliContext for this invocation. Callers must pass
            ``state.context``, not the CliState wrapper itself.
        as_of_date: Optional cutoff. Only postings recorded on or
            before this date are included. None means all-time -- no
            upper bound.

    Returns:
        The TrialBalanceViewModel for the requested scope. Never
        raises AppError on its own -- an empty ledger simply yields a
        TrialBalanceViewModel with no entries, since TrialBalanceRepo
        returns an empty list rather than erroring when nothing is in
        scope.
    """
    service = await ctx.get_trial_balance_service()
    return await service.get_trial_balance(as_of_date=as_of_date)
