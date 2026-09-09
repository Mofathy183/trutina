"""MongoDB operation executor with centralized infrastructure error translation.

MongoExecutor provides the single execution path for all Beanie
operations performed by repository implementations. It ensures MongoDB-
and Beanie-specific exceptions are translated into AppError before they
cross the repository boundary, allowing repositories to remain focused on
query construction, persistence mapping, and repository contract
semantics.

Responsibilities
----------------
- Execute Beanie operations with consistent infrastructure error
    translation.
- Centralize the repository execution pipeline so cross-cutting concerns
    such as logging, metrics, retries, or transaction coordination can be
    introduced without modifying repository implementations.

Not responsibilities
--------------------
- Query construction (performed by repository methods).
- Mapping between domain models and persistence documents (performed by
    repository mapping helpers).
- Translation of duplicate-key violations into domain conflicts
    (performed by each repository's duplicate-key handler).
- Business-level existence or validation checks (performed by repository
    methods and domain services).

Future evolution
----------------
When MongoDB transaction support is introduced, MongoExecutor may evolve
to carry an optional ClientSession as execution context. Because Beanie
operations are constructed before being passed to run(), repositories
will remain responsible for attaching the session during query
construction rather than having the executor inject it afterward.

Additional cross-cutting concerns, including logging, metrics,
instrumentation, or retry policies, should be implemented here so every
repository automatically benefits from the same execution behavior.
"""

from collections.abc import Coroutine
from typing import Any, TypeVar

from trutina.infrastructure.mongo.error_translation import translate_mongo_errors

T = TypeVar("T")


class MongoExecutor:
    """Execute Beanie operations with consistent infrastructure behavior.

    MongoExecutor centralizes execution of all Beanie coroutines issued by
    repository implementations. Every operation passes through
    translate_mongo_errors(), ensuring MongoDB- and Beanie-specific
    exceptions never escape the infrastructure layer unchanged while
    allowing repositories to remain focused on persistence logic.

    DuplicateKeyError is intentionally propagated unchanged because only
    the repository has sufficient domain context to translate a violated
    database uniqueness constraint into the appropriate AppError.

    Usage::

        doc = await self._executor.run(
            AccountDocument.find_one(AccountDocument.code == code)
        )
    """

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute a Beanie operation with translated infrastructure errors.

        Every repository delegates Beanie operations through this method
        so infrastructure error translation is applied consistently across
        the persistence layer.

        Args:
            coro: Awaitable Beanie operation to execute, such as
                ``find_one()``, ``insert()``, ``replace()``,
                ``delete()``, ``exists()``, or ``to_list()``.

        Returns:
            The result produced by the executed Beanie operation.

        Raises:
            DuplicateKeyError: Re-raised unchanged so repositories can
                translate database uniqueness violations into the
                appropriate domain AppError.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                underlying database operation cannot be completed due to
                connectivity failures or timeouts.
        """
        async with translate_mongo_errors():
            return await coro
