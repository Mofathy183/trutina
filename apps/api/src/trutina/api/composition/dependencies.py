"""Per-service dependency providers for FastAPI routes.

Each provider is a plain (non-async) function returning one service
from the request's Container — never the whole container. This is what
makes `app.dependency_overrides[get_account_service] = ...` a one-line
override for a single service in tests, without needing to fake the
entire dependency graph.

Providers are intentionally synchronous: they perform an attribute
lookup on already-constructed, request-scoped-free singletons, so
wrapping them in a coroutine would add overhead with no benefit.
"""

from fastapi import Request
from trutina.config import ApiSettings, get_settings
from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.core.trial_balance.service import TrialBalanceService


def get_settings_dep() -> ApiSettings:
    """Provide the API-layer settings section for request handlers.

    Returns:
        The cached ``ApiSettings`` slice of the application settings.
        Cheap to call per-request since ``get_settings()`` itself is
        ``lru_cache``d — this does no I/O.
    """
    return get_settings().api


def get_account_service(request: Request) -> AccountService:
    return request.app.state.container.account_service


def get_journal_service(request: Request) -> JournalService:
    return request.app.state.container.journal_service


def get_posting_service(request: Request) -> PostingService:
    return request.app.state.container.posting_service


def get_trial_balance_service(request: Request) -> TrialBalanceService:
    return request.app.state.container.trial_balance_service
