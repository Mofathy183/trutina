"""PostgreSQL connection lifecycle helpers.

Provides the application's PostgreSQL connection bootstrap and shutdown
functions. This module sits at the infrastructure boundary and is used
by concrete repository implementations and the Postgres test fixtures
without introducing database concerns into services, domain models, or
CLI code.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from trutina.config import PostgresSettings
from trutina.shared.errors import AppError


@dataclass(frozen=True, slots=True)
class PostgresConnection:
    """Verified PostgreSQL connection resources.

    Bundles the SQLAlchemy async engine and a session factory into a
    single immutable value object so callers can pass persistence
    resources together after connectivity has been successfully
    verified. There is no separate "selected database" handle the way
    some drivers expose one -- the database name already lives in the
    engine's connection URI, so the engine alone fully describes what's
    connected. session_factory is what every repository opens a unit of
    work against; the engine itself is only touched directly by
    connect()/disconnect().

    Attributes:
        engine: Connected, ping-verified SQLAlchemy async engine, owning
            the connection pool.
        session_factory: Callable producing a new AsyncSession bound to
            this engine. expire_on_commit is disabled so a repository
            can still read attributes off an object after commit()
            without triggering an implicit re-fetch.
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def _is_timeout(exc: OperationalError) -> bool:
    """Return True when an OperationalError's cause chain is a timeout.

    SQLAlchemy's async engine does not raise a distinct timeout exception
    type the way PyMongo raises ServerSelectionTimeoutError -- a
    connect_args={"timeout": ...} expiry surfaces as a plain
    asyncio.TimeoutError (a subclass of builtins.TimeoutError since
    Python 3.11) chained onto OperationalError via __cause__. Walking the
    cause chain is what makes this distinguishable from a connection
    that was actively refused, which raises OperationalError with a
    driver-specific cause instead (e.g. ConnectionRefusedError).
    """
    cause = exc.__cause__
    while cause is not None:
        if isinstance(cause, TimeoutError):
            return True
        cause = cause.__cause__
    return False


async def connect(postgres: PostgresSettings) -> PostgresConnection:
    """Create and verify a PostgreSQL connection.

    Builds a SQLAlchemy async engine from the given settings, verifies
    connectivity with a trivial ``SELECT 1``, and returns the engine
    together with a session factory bound to it. If connectivity
    verification fails, the engine is disposed (closing any connections
    it may have already opened) and the failure is translated into an
    ``AppError`` before propagating -- ``STORAGE_TIMEOUT`` when the
    failure's cause chain bottoms out in a timeout, ``STORAGE_UNAVAILABLE``
    for any other connection-time ``OperationalError`` (e.g. connection
    refused). Engine construction itself performs no I/O -- a malformed
    URI fails synchronously inside create_async_engine() with a
    SQLAlchemy ArgumentError, before this function's try block is
    reached, so there is nothing to dispose in that case.

    Args:
        postgres: PostgreSQL configuration values.

    Returns:
        A verified connection bundle containing both the engine and a
        ready-to-use session factory.

    Raises:
        AppError: STORAGE_TIMEOUT if the connectivity check fails due to
            a timeout anywhere in the exception's cause chain.
            STORAGE_UNAVAILABLE for any other connection-time failure
            (e.g. the server refused the connection).
    """
    engine = create_async_engine(
        postgres.uri,
        pool_size=postgres.pool_size,
        max_overflow=postgres.max_overflow,
        pool_pre_ping=postgres.pool_pre_ping,
        connect_args={"timeout": postgres.connect_timeout_s},
    )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        await engine.dispose()
        if _is_timeout(exc):
            raise AppError.storage_timeout(cause=exc) from exc
        raise AppError.storage_unavailable(cause=exc) from exc

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    return PostgresConnection(
        engine=engine,
        session_factory=session_factory,
    )


async def disconnect(connection: PostgresConnection) -> None:
    """Release PostgreSQL connection resources.

    Disposes the underlying SQLAlchemy engine associated with the
    supplied connection bundle, closing every pooled connection.

    Args:
        connection: Connection resources previously created by
            ``connect()``.
    """
    await connection.engine.dispose()
