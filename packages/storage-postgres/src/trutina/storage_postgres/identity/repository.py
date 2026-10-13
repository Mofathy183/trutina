"""Concrete UserRepo implementation backed by PostgreSQL.

Contains no business rules. Email is normalized by the `User` model
before it reaches this module, and again here for lookups, with the
same `normalize_email()` function. `created_at` is stamped by the
database; a value on the passed `User` is ignored.
"""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.authentication import User, UserRepo, normalize_email
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.shared.execution import (
    PostgresExecutor,
    violated_constraint,
)

from .model import UserModel


class PostgresUserRepo(UserRepo):
    """UserRepo implementation backed by a PostgreSQL users table.

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

    async def create(self, user: User) -> None:
        """Persist a new user row.

        Raises:
            AppError: DUPLICATE_USER_EMAIL if the unique constraint on
                `email` rejects the insert. STORAGE_UNAVAILABLE or
                STORAGE_TIMEOUT for infrastructure failures.
        """

        async def _create() -> None:
            async with self._session_factory() as session:
                session.add(
                    UserModel(
                        id=user.id,
                        email=user.email,
                        password_hash=user.password_hash,
                        is_active=user.is_active,
                    )
                )
                await session.commit()

        try:
            await self._executor.run(_create())
        except IntegrityError as exc:
            raise self._on_duplicate(exc) from exc

    async def get_by_id(self, user_id: UUID) -> User | None:
        async def _get() -> UserModel | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                return result.scalar_one_or_none()

        model = await self._executor.run(_get())
        return self._to_domain(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        key = normalize_email(email)

        async def _get() -> UserModel | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.email == key)
                )
                return result.scalar_one_or_none()

        model = await self._executor.run(_get())
        return self._to_domain(model) if model is not None else None

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        """Replace a user's stored password hash.

        Raises:
            AppError: UNKNOWN_USER if no row has this id.
        """
        await self._update_one(user_id, password_hash=password_hash)

    async def set_active(self, user_id: UUID, is_active: bool) -> None:
        """Activate or deactivate a user.

        Raises:
            AppError: UNKNOWN_USER if no row has this id.
        """
        await self._update_one(user_id, is_active=is_active)

    async def _update_one(self, user_id: UUID, **values: object) -> None:
        async def _update() -> bool:
            async with self._session_factory() as session:
                result = await session.execute(
                    update(UserModel)
                    .where(UserModel.id == user_id)
                    .values(**values)
                    .returning(UserModel.id)
                )
                found = result.scalar_one_or_none() is not None
                await session.commit()
                return found

        if not await self._executor.run(_update()):
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_USER,
                resource="user",
                identifier=str(user_id),
            )

    @staticmethod
    def _on_duplicate(exc: IntegrityError) -> AppError:
        """Translate a unique-constraint violation into a domain conflict.

        The context carries only `resource` and `field`, never the
        email value: AppError.context reaches logs and the API catalog
        interpolates it, so an address there would write personal data
        into every failure line.

        Returns:
            DUPLICATE_USER_EMAIL when `uq_users_email` was violated;
            AppError.unknown() otherwise.
        """
        if violated_constraint(exc) == "uq_users_email":
            return AppError(
                code=ErrorCode.DUPLICATE_USER_EMAIL,
                context={"resource": "user", "field": "email"},
            )
        return AppError.unknown(cause=exc)

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        """Reconstruct a validated User from a persisted row.

        Builds a real User so its invariants are re-checked on every
        read. `created_at` comes from the database.
        """
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
        )
