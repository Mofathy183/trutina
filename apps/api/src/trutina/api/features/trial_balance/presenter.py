"""Presentation helpers for the trial balance API.

Transforms the service-layer TrialBalanceViewModel into the HTTP
response schema returned by the trial balance endpoint. This module
defines the translation between the application layer and the public
API contract without introducing business rules or transport-specific
logic -- mirroring posting/presenter.py's shape.
"""

from trutina.core.trial_balance.dtos import TrialBalanceViewModel
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry

from .schemas import AccountBalanceItem, TrialBalanceResponse


def to_account_balance_item(entry: AccountBalanceEntry) -> AccountBalanceItem:
    """Convert a domain AccountBalanceEntry into its HTTP representation.

    Args:
        entry: One aggregated account balance produced by the
            application layer.

    Returns:
        The corresponding API response item.
    """
    return AccountBalanceItem(
        account=entry.account,
        debit_total=entry.debit_total,
        credit_total=entry.credit_total,
    )


def to_trial_balance_response(
    view_model: TrialBalanceViewModel,
) -> TrialBalanceResponse:
    """Convert a trial balance view model into the API response envelope.

    total_debits, total_credits, and is_balanced are read directly off
    the view model's own computed fields -- this presenter never
    recomputes them, the same "derived once, read everywhere" rule the
    view model itself exists to enforce.

    Args:
        view_model: The trial balance produced by the application layer.

    Returns:
        A successful response containing the mapped report.
    """
    return TrialBalanceResponse(
        entries=[to_account_balance_item(entry) for entry in view_model.entries],
        as_of_date=view_model.as_of_date,
        total_debits=view_model.total_debits,
        total_credits=view_model.total_credits,
        is_balanced=view_model.is_balanced,
    )
