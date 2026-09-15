"""PostgreSQL operation executor with centralized infrastructure error translation.

PostgresExecutor provides the single execution path for all SQLAlchemy
operations performed by repository implementations, once repository
implementations exist (Phase 5). Ensures SQLAlchemy/asyncpg-specific
exceptions are translated into AppError before they cross the storage
boundary, allowing repositories to remain focused on query construction,
persistence mapping, and repository contract semantics.

Responsibilities
----------------
- Execute SQLAlchemy operations with consistent infrastructure error
    translation.
- Centralize the repository execution pipeline so cross-cutting concerns
    such as logging, metrics, retries, or a shared AsyncSession/unit-of-
    work scope can be introduced without modifying repository
    implementations.

Not responsibilities
--------------------
- Query construction (performed by repository methods).
- Mapping between domain models and ORM rows (performed by repository
    mapping helpers).
- Translation of constraint violations into domain conflicts (performed
    by each repository's own conflict handler, via violated_constraint()).
- Business-level existence or validation checks (performed by repository
    methods and domain services).

Future evolution
----------------
Once repository implementations exist (Phase 5), this class's shape may
need to change: SQLAlchemy's unit-of-work is session-scoped, unlike
Beanie's global Document registration, so run() may eventually need to
accept or hold an AsyncSession rather than only a bare coroutine. That
shape is deliberately left open rather than guessed at here.
"""

from collections.abc import Coroutine
from typing import Any, TypeVar

from .error_translation import translate_postgres_errors

T = TypeVar("T")


class PostgresExecutor:
    """Execute SQLAlchemy operations with consistent infrastructure behavior.

    Centralizes execution of all SQLAlchemy coroutines issued by
    repository implementations. Every operation passes through
    translate_postgres_errors(), ensuring SQLAlchemy/asyncpg-specific
    exceptions never escape the storage layer unchanged while allowing
    repositories to remain focused on persistence logic.

    IntegrityError is intentionally propagated unchanged because only
    the repository has sufficient domain context to translate a
    violated database constraint into the appropriate AppError.

    Usage::

        result = await self._executor.run(
            session.execute(select(AccountRow).where(AccountRow.code == code))
        )
    """

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute a SQLAlchemy operation with translated infrastructure errors.

        Every repository delegates SQLAlchemy operations through this
        method so infrastructure error translation is applied
        consistently across the storage layer.

        Args:
            coro: Awaitable SQLAlchemy operation to execute, such as
                ``session.execute(...)``, ``session.flush()``, or
                ``session.commit()``.

        Returns:
            The result produced by the executed SQLAlchemy operation.

        Raises:
            IntegrityError: Re-raised unchanged so repositories can
                translate database constraint violations into the
                appropriate domain AppError.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                underlying database operation cannot be completed due
                to connectivity failures or timeouts.
        """
        async with translate_postgres_errors():
            return await coro
