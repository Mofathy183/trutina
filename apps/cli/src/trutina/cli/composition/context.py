from types import TracebackType
from typing import Self

from beanie import init_beanie
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from trutina.config import Settings, get_settings
from trutina.core.account import AccountRepo, AccountService
from trutina.core.journal import JournalRepo, JournalService
from trutina.core.posting import PostingRepo, PostingService
from trutina.shared.errors import AppError
from trutina.storage_mongo import MongoConnection, connect, disconnect
from trutina.storage_mongo.account import AccountDocument, MongoAccountRepo
from trutina.storage_mongo.journal import JournalDocument, MongoJournalRepo
from trutina.storage_mongo.posting import MongoPostingRepo, PostingDocument
from trutina.storage_mongo.shared import MongoExecutor

_DOCUMENT_MODELS = [AccountDocument, JournalDocument, PostingDocument]


class CliContext:
    """Per-command composition root for the CLI dependency graph.

    Lazily constructs and caches repositories, services, and the shared
    MongoDB connection for a single CLI invocation. No external resources
    are acquired until a command requests a repository or service.

    Repositories passed in at construction (``account_repo=``, etc.) are
    treated as caller-owned. This context never opens a connection to
    create them and never tears them down during ``aclose()``. Repositories
    created lazily by this context are context-owned and are discarded when
    the context closes so future lookups rebuild them against a fresh
    connection.

    Lifecycle ownership: in production, ``main.py`` is the sole owner of
    a ``CliContext``'s lifetime. It constructs exactly one context per
    invocation via ``build_context()`` and wraps Typer's dispatch in
    ``async with context: ...``, guaranteeing ``aclose()`` runs even if a
    command raises or Click exits via ``SystemExit``. Callers that
    construct a ``CliContext`` directly outside that flow (tests, in
    particular) are responsible for awaiting ``aclose()`` themselves,
    either explicitly or via ``async with``.

    A single ``MongoExecutor`` instance is created eagerly in
    ``__init__`` and shared by every context-owned repository this
    context builds. ``MongoExecutor`` holds no connection state of its
    own -- it only wraps Beanie operations with consistent MongoDB error
    translation -- so eager construction here performs no I/O and simply
    avoids allocating a redundant instance per repository.
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

        self._connection: MongoConnection | None = None
        self._beanie_ready = False
        self._executor = MongoExecutor()

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

    async def _get_connection(self) -> MongoConnection:
        """Return the shared MongoDB connection for this CLI invocation.

        Establishes the connection and initializes Beanie on first access.
        Subsequent calls reuse the same verified connection and initialized
        document registry until the context is closed.

        Raises:
            AppError: STORAGE_TIMEOUT if the server cannot be reached
                within the configured server-selection timeout.
                STORAGE_UNAVAILABLE for any other MongoDB connection
                failure. This mirrors the translation already performed
                by ``infrastructure/mongo/error_translation.py`` for
                repository operations, so a connection failure at CLI
                startup surfaces through the same ``AppError`` contract
                as any other storage failure raised further down the
                stack -- callers never see a raw ``pymongo`` exception.
        """
        if self._connection is None:
            try:
                self._connection = await connect(self._settings.mongo)
            except ServerSelectionTimeoutError as exc:
                raise AppError.storage_timeout(cause=exc) from exc
            except ConnectionFailure as exc:
                raise AppError.storage_unavailable(cause=exc) from exc

        if not self._beanie_ready:
            await init_beanie(
                database=self._connection.db,
                document_models=_DOCUMENT_MODELS,
            )
            self._beanie_ready = True

        return self._connection

    async def get_account_repo(self) -> AccountRepo:
        """Return the account repository for this CLI invocation.

        Lazily creates and caches the default MongoDB implementation when
        no repository was supplied at construction, reusing this
        context's shared ``MongoExecutor``.
        """
        if self._account_repo is None:
            await self._get_connection()
            self._account_repo = MongoAccountRepo(self._executor)

        return self._account_repo

    async def get_journal_repo(self) -> JournalRepo:
        """Return the journal repository for this CLI invocation.

        Lazily creates and caches the default MongoDB implementation when
        no repository was supplied at construction, reusing this
        context's shared ``MongoExecutor``.
        """
        if self._journal_repo is None:
            await self._get_connection()
            self._journal_repo = MongoJournalRepo(self._executor)

        return self._journal_repo

    async def get_posting_repo(self) -> PostingRepo:
        """Return the posting repository for this CLI invocation.

        Lazily creates and caches the default MongoDB implementation when
        no repository was supplied at construction, reusing this
        context's shared ``MongoExecutor``.
        """
        if self._posting_repo is None:
            await self._get_connection()
            self._posting_repo = MongoPostingRepo(self._executor)

        return self._posting_repo

    async def get_account_service(self) -> AccountService:
        """Return the account service for this CLI invocation.

        The service is constructed once from the active account repository
        and reused until the context is closed.
        """
        if self._account_service is None:
            self._account_service = AccountService(await self.get_account_repo())

        return self._account_service

    async def get_journal_service(self) -> JournalService:
        """Return the journal service for this CLI invocation.

        The service is constructed once from the active journal repository
        and account service, then reused until the context is closed.
        """
        if self._journal_service is None:
            self._journal_service = JournalService(
                repo=await self.get_journal_repo(),
                account_service=await self.get_account_service(),
            )

        return self._journal_service

    async def get_posting_service(self) -> PostingService:
        """Return the posting service for this CLI invocation.

        The service is constructed once from the active posting repository
        and journal service, then reused until the context is closed.
        """
        if self._posting_service is None:
            self._posting_service = PostingService(
                repo=await self.get_posting_repo(),
                journal_service=await self.get_journal_service(),
            )

        return self._posting_service

    async def aclose(self) -> None:
        """Close the MongoDB connection and reset context-owned cached state.

        Idempotent -- safe to call when no connection was opened and safe
        to call multiple times. In production this is always invoked by
        ``main.py``'s ``async with build_context() as context: ...``
        block; direct callers (tests constructing ``CliContext``
        themselves) must call it explicitly, ideally via ``async with``.

        Repositories lazily created by this context are discarded so future
        repository lookups reconnect and rebuild them against a fresh
        MongoDB connection. Cached services are always cleared because they
        depend on whichever repository instances were active before the
        context closed.

        Repositories supplied by the caller remain untouched because their
        lifecycle is owned outside this context.
        """
        try:
            if self._connection is not None:
                await disconnect(self._connection)
        finally:
            self._connection = None
            self._beanie_ready = False

            if not self._account_repo_injected:
                self._account_repo = None
            if not self._journal_repo_injected:
                self._journal_repo = None
            if not self._posting_repo_injected:
                self._posting_repo = None

            self._account_service = None
            self._journal_service = None
            self._posting_service = None
