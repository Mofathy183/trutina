"""Composition root and lifespan management for the Trutina API.

bootstrap.py owns the one and only sequence that opens the shared
PostgreSQL connection, builds the singleton service graph, and attaches
it to app.state as a Container.

Table existence is guaranteed by Alembic migrations applied before this
process starts. Nothing in this module creates or alters schema, and it
performs no schema-registration step of its own.

This is the only module in the API layer permitted to import
PostgresConnection-adjacent infrastructure types (PostgresConnection,
PostgresExecutor, any concrete Postgres*Repo). Routes, dependency
providers, and app.py never see these types directly -- they only ever
see Container's service attributes.

Startup failure policy
-----------------------
If the initial PostgreSQL ping (performed inside connect()) fails,
startup fails loudly: the exception propagates out of the lifespan
context manager, FastAPI/uvicorn abort startup, and the process exits
non-zero without ever accepting a request. Process orchestration
(systemd, Kubernetes restart-with-backoff, etc.) is expected to own
retry policy; this module does not retry.

This is distinct from *post-startup* PostgreSQL failures (e.g. a network
partition after the process is already serving traffic), which are
already handled per-request by translate_postgres_errors() ->
AppError.storage_unavailable()/storage_timeout() and surfaced through
the API's normal error-handling path, not through this module.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from trutina.config import Settings
from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.storage_postgres.account import PostgresAccountRepo
from trutina.storage_postgres.journal import PostgresJournalRepo
from trutina.storage_postgres.posting import PostgresPostingRepo
from trutina.storage_postgres.shared import PostgresConnection, connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor

from .container import Container


def build_container(connection: PostgresConnection) -> Container:
    """Construct the singleton service graph bound to an open connection.

    JournalService depends on AccountService, PostingService depends on
    JournalService. All three repositories are built from the same
    PostgresExecutor instance and the connection's session_factory, so
    every repository shares one error-translation choke point and one
    pool of sessions.

    AccountService is given a posting-history predicate bound to the
    same posting_repo instance PostingService uses, so that
    delete_account() enforces the ACCOUNT_HAS_POSTINGS safeguard against
    the same data PostingService itself would report through
    get_postings_by_account().

    Split out from the lifespan function specifically so it can be unit
    tested in isolation, given a connection built by a test fixture.

    Args:
        connection: An already-verified PostgresConnection, typically
            obtained from connect(settings.postgres).

    Returns:
        A Container wired against real PostgreSQL-backed repositories.
    """
    executor = PostgresExecutor()

    account_repo = PostgresAccountRepo(connection.session_factory, executor)
    journal_repo = PostgresJournalRepo(connection.session_factory, executor)
    posting_repo = PostgresPostingRepo(connection.session_factory, executor)

    async def _has_postings(account_name: str) -> bool:
        postings = await posting_repo.get_by_account(account_name)
        return len(postings) > 0

    account_service = AccountService(account_repo, has_postings=_has_postings)
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
    TestSettings (an isolated PostgreSQL database) without touching the
    environment-sourced get_settings() used in production. Nothing at
    bootstrap.py's module level performs I/O; the sequence below only
    runs when the returned context manager is actually entered by
    FastAPI/uvicorn.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        connection = await connect(settings.postgres)

        app.state.container = build_container(connection)

        try:
            yield
        finally:
            await disconnect(connection)

    return lifespan
