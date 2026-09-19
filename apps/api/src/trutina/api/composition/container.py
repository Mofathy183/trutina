"""Typed dependency container for the FastAPI presentation layer.

Container is the API's single composition artifact — the equivalent of
CliContext for the CLI, but resolved eagerly, once, at process startup
rather than lazily per invocation (see bootstrap.py and the API ADR for
the rationale: the API pays connection cost once regardless, so there's
no benefit to laziness and a real cost to first-request latency if it
were lazy).

Container holds only feature services. It intentionally exposes no
MongoDB-specific types — no AsyncMongoClient, no MongoExecutor, no
Mongo*Repo — those are construction details owned entirely by
bootstrap.py. Routes and dependency providers depend on Container's
public attributes only, never on how they were built.
"""

from dataclasses import dataclass

from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.core.trial_balance.service import TrialBalanceService


@dataclass(frozen=True, slots=True)
class Container:
    """Singleton services shared by every request for the life of the process.

    Every attribute is stateless — concurrent requests calling the same
    service concurrently is safe only because no service holds mutable,
    request-specific state. This is an invariant the codebase must
    continue to uphold, not just a fact that happens to be true today;
    see the API ADR's "Service Lifecycle" section for what changes the
    day that invariant needs to be broken (ClientSession, auth context).

    Constructed exactly once, inside bootstrap.py's lifespan, and
    attached to app.state.container. Never constructed inside a route,
    a dependency provider, or at module import time.

    trial_balance_service has no peer-service dependency, unlike
    journal_service (depends on account_service) and posting_service
    (depends on journal_service) — it reads entirely from
    already-persisted postings, so its inclusion here does not change
    the wiring order bootstrap.py must follow for the other three.
    """

    account_service: AccountService
    journal_service: JournalService
    posting_service: PostingService
    trial_balance_service: TrialBalanceService
