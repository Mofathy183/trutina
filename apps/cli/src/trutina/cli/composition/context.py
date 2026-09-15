"""Per-command composition root for the CLI dependency graph."""

from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Self

from trutina.config import Settings, get_settings
from trutina.core.account import AccountRepo, AccountService
from trutina.core.journal import JournalRepo, JournalService
from trutina.core.posting import PostingRepo, PostingService
from trutina.storage_postgres.account import PostgresAccountRepo
from trutina.storage_postgres.journal import PostgresJournalRepo
from trutina.storage_postgres.posting import PostgresPostingRepo
from trutina.storage_postgres.shared import PostgresConnection, connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


class CliContext:
    """Per-command composition root for the CLI dependency graph.

    Lazily constructs and caches repositories, services, and the shared
    PostgreSQL connection for a single CLI invocation. No external
    resources are acquired until a command requests a repository or
    service.

    Repositories passed in at construction (``account_repo=``, etc.) are
    treated as caller-owned. This context never opens a connection to
    create them and never tears them down during ``aclose()``.
    Repositories created lazily by this context are context-owned and
    are discarded when the context closes so future lookups rebuild them
    against a fresh connection.

    Lifecycle ownership: in production, ``main.py`` is the sole owner of
    a ``CliContext``'s lifetime. It constructs exactly one context per
    invocation via ``build_context()`` and wraps Typer's dispatch in
    ``async with context: ...``, guaranteeing ``aclose()`` runs even if
    a command raises or Click exits via ``SystemExit``. Callers that
    construct a ``CliContext`` directly outside that flow (tests, in
    particular) are responsible for awaiting ``aclose()`` themselves,
    either explicitly or via ``async with``.

    A single ``PostgresExecutor`` instance is created eagerly in
    ``__init__`` and shared by every context-owned repository this
    context builds. ``PostgresExecutor`` holds no connection state of
    its own -- it only wraps SQLAlchemy operations with consistent
    error translation -- so eager construction here performs no I/O and
    simply avoids allocating a redundant instance per repository.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        account_repo: AccountRepo | None = None,
        journal_repo: JournalRepo | None = None,
        posting_repo: PostingRepo | None = None,
    ) -> None:
        self._settings = settings or get_settings()

        self._connection: PostgresConnection | None = None
        self._executor = PostgresExecutor()

        self._account_repo = account_repo
        self._journal_repo = journal_repo
        self._posting_repo = posting_repo

        # Track which repositories were supplied by the caller so only
        # context-owned repositories participate in this context's
        # connection lifecycle.
        self._account_repo_injected = account_repo is not None
        self._journal_repo_injected = journal_repo is not None
        self._posting_repo_injected = posting_repo is not None

        self._account_service: AccountService | None = None
        self._journal_service: JournalService | None = None
        self._posting_service: PostingService | None = None

    async def __aenter__(self) -> Self:
        """Return this context for use with ``async with``."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Release any lazily created resources when the context exits.

        Runs even when the ``async with`` block exits via an exception,
        including ``SystemExit`` raised by Click's normal dispatch
        handling -- this is what lets ``main.py`` guarantee cleanup for
        every invocation outcome, not only the success path.
        """
        await self.aclose()

    async def _get_connection(self) -> PostgresConnection:
        """Return the shared PostgreSQL connection for this CLI invocation.

        Establishes and verifies the connection on first access via
        connect(), which performs its own timeout-vs-unavailable
        translation and raises AppError directly. Subsequent calls reuse
        the same connection until the context is closed.

        Raises:
            AppError: STORAGE_TIMEOUT if the connection attempt exceeds
                the configured timeout, or STORAGE_UNAVAILABLE for any
                other connection-time failure. Both are raised by
                connect() itself and propagate unchanged from here.
        """
        if self._connection is None:
            self._connection = await connect(self._settings.postgres)

        return self._connection

    async def get_account_repo(self) -> AccountRepo:
        """Return the account repository for this CLI invocation.

        Lazily creates and caches the default PostgreSQL implementation
        when no repository was supplied at construction, reusing this
        context's shared ``PostgresExecutor``.
        """
        if self._account_repo is None:
            connection = await self._get_connection()
            self._account_repo = PostgresAccountRepo(
                connection.session_factory, self._executor
            )

        return self._account_repo

    async def get_journal_repo(self) -> JournalRepo:
        """Return the journal repository for this CLI invocation.

        Lazily creates and caches the default PostgreSQL implementation
        when no repository was supplied at construction, reusing this
        context's shared ``PostgresExecutor``.
        """
        if self._journal_repo is None:
            connection = await self._get_connection()
            self._journal_repo = PostgresJournalRepo(
                connection.session_factory, self._executor
            )

        return self._journal_repo

    async def get_posting_repo(self) -> PostingRepo:
        """Return the posting repository for this CLI invocation.

        Lazily creates and caches the default PostgreSQL implementation
        when no repository was supplied at construction, reusing this
        context's shared ``PostgresExecutor``.
        """
        if self._posting_repo is None:
            connection = await self._get_connection()
            self._posting_repo = PostgresPostingRepo(
                connection.session_factory, self._executor
            )

        return self._posting_repo

    async def get_account_service(self) -> AccountService:
        """Return the account service for this CLI invocation.

        The service is constructed once from the active account
        repository, plus a posting-history check bound to the active
        posting repository, and reused until the context is closed.
        """
        if self._account_service is None:
            posting_repo = await self.get_posting_repo()
            self._account_service = AccountService(
                await self.get_account_repo(),
                has_postings=self._make_has_postings_check(posting_repo),
            )

        return self._account_service

    async def get_journal_service(self) -> JournalService:
        """Return the journal service for this CLI invocation.

        The service is constructed once from the active journal
        repository and account service, then reused until the context
        is closed.
        """
        if self._journal_service is None:
            self._journal_service = JournalService(
                repo=await self.get_journal_repo(),
                account_service=await self.get_account_service(),
            )

        return self._journal_service

    async def get_posting_service(self) -> PostingService:
        """Return the posting service for this CLI invocation.

        The service is constructed once from the active posting
        repository and journal service, then reused until the context
        is closed.
        """
        if self._posting_service is None:
            self._posting_service = PostingService(
                repo=await self.get_posting_repo(),
                journal_service=await self.get_journal_service(),
            )

        return self._posting_service

    @staticmethod
    def _make_has_postings_check(
        posting_repo: PostingRepo,
    ) -> Callable[[str], Awaitable[bool]]:
        """Bind a posting-existence predicate to a specific PostingRepo.

        Kept as a closure rather than a bound method on PostingRepo
        itself, since the predicate's only consumer is
        AccountService's has_postings constructor parameter -- it
        belongs to this composition boundary, not to the repository
        contract itself.
        """

        async def _has_postings(account_name: str) -> bool:
            postings = await posting_repo.get_by_account(account_name)
            return len(postings) > 0

        return _has_postings

    async def aclose(self) -> None:
        """Close the PostgreSQL connection and reset context-owned cached state.

        Idempotent -- safe to call when no connection was opened and
        safe to call multiple times. In production this is always
        invoked by ``main.py``'s ``async with build_context() as
        context: ...`` block; direct callers (tests constructing
        ``CliContext`` themselves) must call it explicitly, ideally via
        ``async with``.

        Repositories lazily created by this context are discarded so
        future repository lookups reconnect and rebuild them against a
        fresh connection. Cached services are always cleared because
        they depend on whichever repository instances were active
        before the context closed.

        Repositories supplied by the caller remain untouched because
        their lifecycle is owned outside this context.
        """
        try:
            if self._connection is not None:
                await disconnect(self._connection)
        finally:
            self._connection = None

            if not self._account_repo_injected:
                self._account_repo = None
            if not self._journal_repo_injected:
                self._journal_repo = None
            if not self._posting_repo_injected:
                self._posting_repo = None

            self._account_service = None
            self._journal_service = None
            self._posting_service = None
