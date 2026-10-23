"""Concrete LoginAttemptRepo implementation backed by PostgreSQL.

Contains no throttling policy: thresholds, windows and the retry delay
belong to the authentication service. The email is normalized here with
the same `normalize_email()` the User model uses, so stored keys and
lookups can never disagree.
"""

from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.authentication import LoginAttemptRepo, normalize_email
from trutina.storage_postgres.shared.execution import PostgresExecutor

from .model import LoginAttemptModel


class PostgresLoginAttemptRepo(LoginAttemptRepo):
    """LoginAttemptRepo implementation backed by a login_attempts table.

    Attributes:
        _session_factory: Produces a new AsyncSession per operation.
        _executor: Routes every database operation through
            translate_postgres_errors() so infrastructure failures
            surface as AppError.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        executor: PostgresExecutor,
    ) -> None:
        """Initialize the repository with its session factory and executor.

        Args:
            session_factory: Bound to an already-verified engine.
            executor: Wraps every operation this repository performs.
        """
        self._session_factory = session_factory
        self._executor = executor

    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        """Insert one failure row, stored with the normalized email.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT for
                infrastructure failures.
        """
        key = normalize_email(email)

        async def _record() -> None:
            async with self._session_factory() as session:
                session.add(LoginAttemptModel(ip=ip, email_key=key, attempted_at=at))
                await session.commit()

        await self._executor.run(_record())

    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        key = normalize_email(email)

        async def _count() -> int:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(LoginAttemptModel)
                    .where(
                        LoginAttemptModel.ip == ip,
                        LoginAttemptModel.email_key == key,
                        LoginAttemptModel.attempted_at >= since,
                    )
                )
                return result.scalar_one()

        return await self._executor.run(_count())

    async def clear(self, *, ip: str, email: str) -> None:
        key = normalize_email(email)

        async def _clear() -> None:
            async with self._session_factory() as session:
                await session.execute(
                    delete(LoginAttemptModel).where(
                        LoginAttemptModel.ip == ip,
                        LoginAttemptModel.email_key == key,
                    )
                )
                await session.commit()

        await self._executor.run(_clear())

    async def purge_before(self, cutoff: datetime) -> int:
        async def _purge() -> int:
            async with self._session_factory() as session:
                result = await session.execute(
                    delete(LoginAttemptModel).where(
                        LoginAttemptModel.attempted_at < cutoff
                    )
                )
                await session.commit()
                return cast(CursorResult, result).rowcount

        return await self._executor.run(_purge())
