"""HTTP routes for the trial balance feature.

Exposes a single read-only endpoint that produces an aggregated trial
balance report from existing ledger postings. Trial balance has no
request body -- it is computed, never submitted -- so this feature has
only a query parameter to map, unlike account/journal's request-body
features. The route still follows the same Router -> Mapper -> Handler
-> Presenter pipeline every other feature uses (see
posting/router.py), just with a query parameter standing in for a
Request Schema.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from trutina.api.composition.dependencies import get_trial_balance_service
from trutina.core.trial_balance import TrialBalanceService

from .handler import get_trial_balance_handler
from .mapper import to_as_of_date
from .presenter import to_trial_balance_response
from .schemas import TrialBalanceResponse

router = APIRouter(prefix="/trial-balance", tags=["trial-balance"])


@router.get(
    "",
    response_model=TrialBalanceResponse,
)
async def get_trial_balance(
    as_of: Annotated[
        datetime | None,
        Query(
            description=(
                "Only include postings recorded on or before this date/time. "
                "Omit for an all-time trial balance."
            )
        ),
    ] = None,
    service: TrialBalanceService = Depends(get_trial_balance_service),
) -> TrialBalanceResponse:
    """Produce the trial balance: aggregated debit/credit totals per account.

    Args:
        as_of: Optional cutoff date/time. Only postings recorded on or
            before this value are included in the aggregation.
        service: The trial balance service.

    Returns:
        The trial balance report for the requested scope.
    """
    mapped_as_of = to_as_of_date(as_of)
    view_model = await get_trial_balance_handler(service, mapped_as_of)
    return to_trial_balance_response(view_model)
