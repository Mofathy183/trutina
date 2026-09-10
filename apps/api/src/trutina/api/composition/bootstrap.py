"""Composition root and lifespan management for the Trutina API.

bootstrap.py is the API's equivalent of cli/bootstrap.py + main.py::run()
combined: it owns the one and only sequence that opens the shared
MongoDB connection, initializes Beanie, builds the singleton service
graph, and attaches it to app.state as a Container.

This is the only module in the API layer permitted to import
AsyncMongoClient-adjacent infrastructure types (MongoConnection,
MongoExecutor, any concrete Mongo*Repo). Routes, dependency providers,
and app.py never see these types directly — they only ever see
Container's service attributes.

Startup failure policy
-----------------------
If the initial MongoDB ping (performed inside connect()) fails, startup
fails loudly: the exception propagates out of the lifespan context
manager, FastAPI/uvicorn abort startup, and the process exits non-zero
without ever accepting a request. This mirrors connect()'s existing
behavior for the CLI. An API process that starts "successfully" but
can't reach its database has no correct way to answer any request, so
serving traffic in that state would only convert one obvious, fail-fast
startup error into a confusing wall of per-request 5xx responses.
Process orchestration (systemd, Kubernetes restart-with-backoff, etc.)
is expected to own retry policy; this module does not retry.

This is distinct from *post-startup* MongoDB failures (e.g. a network
partition after the process is already serving traffic), which are
already handled per-request by translate_mongo_errors() ->
AppError.storage_unavailable()/storage_timeout() and surfaced through
the API's normal error-handling path, not through this module.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from trutina.config import Settings
from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.storage_mongo import connect, disconnect
from trutina.storage_mongo.account import AccountDocument, MongoAccountRepo
from trutina.storage_mongo.journal import JournalDocument, MongoJournalRepo
from trutina.storage_mongo.posting import MongoPostingRepo, PostingDocument
from trutina.storage_mongo.shared import MongoExecutor

from .container import Container

# Mirrors tests/fixtures/mongo.py::DOCUMENT_MODELS. Kept as a separate
# list rather than imported from the test fixture, since production code
# must not depend on the test tree; add new Document classes here *and*
# in tests/fixtures/mongo.py when a fourth one is introduced.
DOCUMENT_MODELS = [AccountDocument, JournalDocument, PostingDocument]


def build_container() -> Container:
    """Construct the singleton service graph.

    Pure construction — no I/O, no MongoDB connection required. Mirrors
    CliContext's wiring exactly: JournalService depends on AccountService,
    PostingService depends on JournalService. MongoExecutor and the
    Mongo*Repo constructors take no connection/client argument — every
    Beanie operation resolves its collection through global Document
    registration set up by init_beanie(), not through anything held here
    — which is precisely what makes this function safe to call with no
    MongoDB instance reachable at all (see TestBuildContainer.test_performs_no_io).

    Split out from the lifespan function specifically so it can be unit
    tested in isolation.
    """
    executor = MongoExecutor()

    account_repo = MongoAccountRepo(executor)
    journal_repo = MongoJournalRepo(executor)
    posting_repo = MongoPostingRepo(executor)

    account_service = AccountService(account_repo)
    journal_service = JournalService(
        repo=journal_repo,
        account_service=account_service,
    )
    posting_service = PostingService(
        repo=posting_repo,
        journal_service=journal_service,
    )

    return Container(
        account_service=account_service,
        journal_service=journal_service,
        posting_service=posting_service,
    )


def make_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build a lifespan context manager bound to a specific Settings instance.

    Kept as a factory rather than a single module-level `lifespan`
    object so tests can run the full startup/shutdown sequence against
    TestSettings (an isolated MongoDB) without touching the
    environment-sourced get_settings() used in production — mirroring
    how build_context(settings=...) already works on the CLI side.
    Nothing at bootstrap.py's module level performs I/O; the sequence
    below only runs when the returned context manager is actually
    entered by FastAPI/uvicorn.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        connection = await connect(settings.mongo)

        await init_beanie(database=connection.db, document_models=DOCUMENT_MODELS)

        app.state.container = build_container()

        try:
            yield
        finally:
            await disconnect(connection)

    return lifespan
