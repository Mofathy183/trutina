"""SQLAlchemy/asyncpg exception translation utilities.

Provides the translate_postgres_errors() async context manager for use
in every repository method, once repository implementations exist
(Phase 5). Translates SQLAlchemy/asyncpg exceptions into AppError at the
storage boundary so the service layer never handles driver-specific
exceptions.

IntegrityError is intentionally excluded. The context manager re-raises
it unchanged so a repository can translate the violated constraint with
its own domain context -- see violated_constraint() below.

Exception hierarchy (most-specific first):
    TimeoutError
        Raised when a connection attempt or operation cannot complete
        within the configured timeout. Whether asyncpg's own connect
        timeout ever reaches this handler as a bare TimeoutError, or is
        always wrapped in an OperationalError by SQLAlchemy's dialect
        first, is not yet confirmed against a real server -- this branch
        is included defensively rather than left out on an unverified
        assumption. See connection.py's own docstring for the same flag.
        -> maps to AppError.storage_timeout()
    OperationalError
        SQLAlchemy's wrapper for connection-level failures reported by
        the server or driver (connection refused, connection dropped,
        too many connections, and -- possibly -- a connect-time
        timeout; see above).
        -> maps to AppError.storage_unavailable()
    IntegrityError
        Constraint violations (unique, foreign key, check). Re-raised
        unchanged so a repository can translate the violated constraint
        with its own domain context.
    SQLAlchemyError (catch-all)
        -> maps to AppError.unknown()
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from trutina.shared.errors import AppError


def violated_constraint(exc: IntegrityError) -> str | None:
    """Return the name of the constraint violated by exc, or None.

    SQLAlchemy's asyncpg dialect re-raises a translated wrapper exception
    as IntegrityError.orig, chaining the original asyncpg.PostgresError
    (which carries diagnostic fields like constraint_name) via __cause__
    rather than copying those fields onto the wrapper. Check both, since
    a future dialect version or a different driver might attach it
    directly to orig.
    """
    direct = getattr(exc.orig, "constraint_name", None)
    if direct is not None:
        return direct
    return getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)


@asynccontextmanager
async def translate_postgres_errors() -> AsyncGenerator[None]:
    """Translate SQLAlchemy/asyncpg infrastructure exceptions into AppError.

    Wraps a single awaitable SQLAlchemy call so that storage-level
    failures never escape the storage boundary as driver-specific
    exceptions.

    Usage -- read path (no IntegrityError risk):

        async with translate_postgres_errors():
            result = await session.execute(select(AccountRow)...)

    Usage -- write path (catch IntegrityError outside the context):

        try:
            async with translate_postgres_errors():
                session.add(row)
                await session.flush()
        except IntegrityError as exc:
            raise self._on_conflict(exc, account) from exc

    IntegrityError is a SQLAlchemyError subclass, but this context
    manager re-raises it before its SQLAlchemyError catch-all. A
    repository that does not catch it therefore exposes it unchanged
    rather than converting it to AppError.unknown().

    Raises:
        AppError: STORAGE_TIMEOUT when a connection attempt or operation
            times out.
        AppError: STORAGE_UNAVAILABLE when OperationalError is caught.
        AppError: UNKNOWN_ERROR for any other SQLAlchemyError.
    """
    try:
        yield
    except IntegrityError:
        raise  # repository handles this -- it knows what the constraint means
    except TimeoutError as exc:
        raise AppError.storage_timeout(cause=exc) from exc
    except OperationalError as exc:
        raise AppError.storage_unavailable(cause=exc) from exc
    except SQLAlchemyError as exc:
        raise AppError.unknown(cause=exc) from exc
