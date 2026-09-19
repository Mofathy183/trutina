"""
trial_balance feature: read-model aggregation over the accounting domain.

Public API:
- AccountBalanceEntry -- one account's aggregated debit/credit activity
- TrialBalanceRepo -- the read-only aggregation contract
- TrialBalanceService -- the single entry point for producing a trial balance
- TrialBalanceViewModel -- the report-level output DTO

The concrete PostgreSQL adapter, PostgresTrialBalanceRepo, lives in a
different package (trutina.storage_postgres.trial_balance) and is not
re-exported here, mirroring how posting's PostgresPostingRepo is not
re-exported from trutina.core.posting.

Depends only on trutina.shared -- no import from trutina.core.posting
exists in this module despite the conceptual relationship (see the
Trial Balance Feature Plan ADR, D1).
"""

from .dtos import TrialBalanceViewModel
from .repo import TrialBalanceRepo
from .schemas.account_balance import AccountBalanceEntry
from .service import TrialBalanceService

__all__ = [
    "AccountBalanceEntry",
    "TrialBalanceRepo",
    "TrialBalanceService",
    "TrialBalanceViewModel",
]
