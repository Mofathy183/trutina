"""Concrete SessionRepo implementation backed by PostgreSQL.

Contains no policy: lifetimes, when a touch is due and the retention
cutoff belong to the session service, which passes finished values in.
Every method opens its own short session and holds no connection while
any other work happens (ADR 0002); no method nests a second session.

Nothing in this module logs, and no error it raises carries a token
hash: the hash is a stored lookup secret.
"""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import (
    CursorResult,
    DateTime,
    delete,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Executable
from trutina.authentication import (
    AccessState,
    ClientKind,
    SessionRecord,
    SessionRepo,
    ValidSession,
)
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.identity import UserModel
from trutina.storage_postgres.shared.execution import (
    PostgresExecutor,
    violated_constraint,
)

from .model import SessionModel


def _utc(value: datetime):
    """Bind a time as timestamptz.

    A bare datetime inside func.greatest() would be typed as a timestamp
    without time zone, which asyncpg rejects for an aware value.
    """
    return literal(value, DateTime(timezone=True))


class PostgresSessionRepo(SessionRepo):
    """SessionRepo implementation backed by a PostgreSQL sessions table.

    Every write is one UPDATE or DELETE statement with no read-modify-
    write, so concurrent callers cannot interleave between a check and
    its change.

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

    async def create(self, record: SessionRecord) -> None:
        """Insert a new session row.

        Raises:
            AppError: UNKNOWN_ERROR for a duplicate token hash or an
                unknown user, with only `resource` and `constraint` in
                its context and no cause. STORAGE_UNAVAILABLE or
                STORAGE_TIMEOUT for infrastructure failures.
        """

        async def _create() -> None:
            async with self._session_factory() as session:
                session.add(
                    SessionModel(
                        token_hash=record.token_hash,
                        user_id=record.user_id,
                        client_kind=record.client_kind.value,
                        created_at=record.created_at,
                        last_used_at=record.last_used_at,
                        authenticated_at=record.authenticated_at,
                        idle_expires_at=record.idle_expires_at,
                        absolute_expires_at=record.absolute_expires_at,
                        revoked_at=record.revoked_at,
                    )
                )
                await session.commit()

        # The error is raised after the except block, not inside it, so
        # the IntegrityError is not chained onto it through __context__:
        # the driver's message can contain the stored token hash.
        error: AppError | None = None
        try:
            await self._executor.run(_create())
        except IntegrityError as exc:
            error = self._on_integrity_error(exc)
        if error is not None:
            raise error

    async def get_valid(
        self,
        token_hash: str,
        *,
        client_kind: ClientKind,
        now: datetime,
    ) -> ValidSession | None:
        async def _get() -> tuple[SessionModel, bool] | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SessionModel, UserModel.is_active)
                    .join(UserModel, UserModel.id == SessionModel.user_id)
                    .where(
                        SessionModel.token_hash == token_hash,
                        SessionModel.client_kind == client_kind.value,
                        SessionModel.revoked_at.is_(None),
                        SessionModel.idle_expires_at > now,
                        SessionModel.absolute_expires_at > now,
                        UserModel.is_active.is_(True),
                    )
                )
                row = result.one_or_none()
                return None if row is None else (row[0], row[1])

        found = await self._executor.run(_get())
        if found is None:
            return None
        model, is_active = found
        return ValidSession(
            session=self._to_record(model),
            access=AccessState(is_active=is_active),
        )

    async def touch(
        self,
        token_hash: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
    ) -> None:
        await self._execute(
            update(SessionModel)
            .where(
                SessionModel.token_hash == token_hash,
                SessionModel.revoked_at.is_(None),
            )
            .values(
                last_used_at=func.greatest(SessionModel.last_used_at, _utc(now)),
                idle_expires_at=func.greatest(
                    SessionModel.idle_expires_at, _utc(idle_expires_at)
                ),
            )
            .execution_options(synchronize_session=False)
        )

    async def mark_reauthenticated(self, token_hash: str, *, now: datetime) -> None:
        await self._execute(
            update(SessionModel)
            .where(
                SessionModel.token_hash == token_hash,
                SessionModel.revoked_at.is_(None),
            )
            .values(
                authenticated_at=func.greatest(SessionModel.authenticated_at, _utc(now))
            )
            .execution_options(synchronize_session=False)
        )

    async def revoke(self, token_hash: str, *, now: datetime) -> None:
        await self._execute(
            update(SessionModel)
            .where(
                SessionModel.token_hash == token_hash,
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> None:
        await self._execute(
            update(SessionModel)
            .where(
                SessionModel.user_id == user_id,
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )

    async def purge_before(self, cutoff: datetime) -> int:
        async def _purge() -> int:
            async with self._session_factory() as session:
                # A session died at the earliest of its three end times, so
                # it died before the cutoff when any one of them did. A null
                # revoked_at never matches.
                result = await session.execute(
                    delete(SessionModel)
                    .where(
                        or_(
                            SessionModel.revoked_at < cutoff,
                            SessionModel.idle_expires_at < cutoff,
                            SessionModel.absolute_expires_at < cutoff,
                        )
                    )
                    .execution_options(synchronize_session=False)
                )
                await session.commit()
                return cast(CursorResult, result).rowcount

        return await self._executor.run(_purge())

    async def _execute(self, statement: Executable) -> None:
        async def _run() -> None:
            async with self._session_factory() as session:
                await session.execute(statement)
                await session.commit()

        await self._executor.run(_run())

    @staticmethod
    def _on_integrity_error(exc: IntegrityError) -> AppError:
        """Translate a rejected insert into a value-free AppError.

        A duplicate token hash and a missing user are both defects, not
        domain outcomes, so the code is UNKNOWN_ERROR. The context names
        the violated constraint (`uq_sessions_token_hash` or
        `fk_sessions_user_id_users`) so an operator can tell them apart.
        The driver exception is deliberately not attached as the cause,
        because its text can include the stored value and the cause
        reaches the failure log.

        Returns:
            An AppError with UNKNOWN_ERROR; `constraint` is "unknown"
            when the driver names none.
        """
        return AppError(
            code=ErrorCode.UNKNOWN_ERROR,
            context={
                "resource": "session",
                "constraint": violated_constraint(exc) or "unknown",
            },
        )

    @staticmethod
    def _to_record(model: SessionModel) -> SessionRecord:
        """Reconstruct the contract's SessionRecord from a persisted row."""
        return SessionRecord(
            token_hash=model.token_hash,
            user_id=model.user_id,
            client_kind=ClientKind(model.client_kind),
            created_at=model.created_at,
            last_used_at=model.last_used_at,
            authenticated_at=model.authenticated_at,
            idle_expires_at=model.idle_expires_at,
            absolute_expires_at=model.absolute_expires_at,
            revoked_at=model.revoked_at,
        )
