"""Concrete AccountRepo implementation backed by PostgreSQL.

Implements the AccountRepo persistence contract using SQLAlchemy async
sessions. Contains no business rules of its own -- uniqueness pre-checks
and cross-account validation are AccountService's responsibility; this
module only maps between Account domain objects and AccountModel rows
and translates storage-level conflicts into AppError.

name_key is a plain column on AccountModel, not a database-computed one.
This repository is the only place that ever produces it, via
account_lookup_key(), on every insert and every update -- so the unique
index backing it can never disagree with the case-insensitive rule the
rest of the domain uses to decide what counts as a duplicate name.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.core.account.repo import AccountRepo
from trutina.core.account.schemas.account import Account, AccountCategory
from trutina.shared.errors import AppError, ErrorCode
from trutina.shared.rule import account_lookup_key
from trutina.storage_postgres.audit import AuditAction, AuditEventModel
from trutina.storage_postgres.shared.execution import (
    PostgresExecutor,
    violated_constraint,
)

from .model import AccountModel

_AUDIT_ENTITY = "account"


def _audit_row(action: AuditAction, code: str, actor: str) -> AuditEventModel:
    """Build the audit row recorded alongside one account write."""
    return AuditEventModel(
        entity=_AUDIT_ENTITY,
        entity_key=code,
        action=action.value,
        actor=actor,
    )


class PostgresAccountRepo(AccountRepo):
    """AccountRepo implementation backed by a PostgreSQL accounts table.

    Every write recomputes name_key immediately before the row is
    flushed, so a rename can never leave the lookup key stale.

    Attributes:
        _session_factory: Produces a new AsyncSession bound to the
            configured engine, one per operation.
        _executor: Routes every database operation through
            translate_postgres_errors() so infrastructure failures
            surface as AppError before they cross this repository's
            boundary.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        executor: PostgresExecutor,
    ) -> None:
        """Initialize the repository with its session factory and executor.

        Args:
            session_factory: Bound to an already-verified engine; this
                repository never opens a connection itself.
            executor: Wraps every operation this repository performs.
        """
        self._session_factory = session_factory
        self._executor = executor

    async def create(self, account: Account, *, created_by: str) -> None:
        """Persist a new account row and its audit row in one transaction.

        ``created_by`` is stored as the actor of one ``audit_events`` row
        written in the same transaction, so the account and its audit
        row either both persist or neither does.

        Raises:
            AppError: DUPLICATE_ACCOUNT_CODE or DUPLICATE_ACCOUNT_NAME if
                the unique constraint on `code` or `name_key` rejects the
                insert. UNKNOWN_ERROR if the audit insert is rejected.
                STORAGE_UNAVAILABLE/STORAGE_TIMEOUT for infrastructure
                failures.
        """

        async def _create() -> None:
            async with self._session_factory() as session:
                session.add(
                    AccountModel(
                        code=account.code,
                        name=account.name,
                        name_key=account_lookup_key(account.name),
                        category=account.category.value,
                    )
                )
                session.add(_audit_row(AuditAction.CREATE, account.code, created_by))
                await session.commit()

        try:
            await self._executor.run(_create())
        except IntegrityError as exc:
            raise self._on_duplicate(exc, account.code, account.name) from exc

    async def update(self, account: Account, *, created_by: str) -> None:
        """Overwrite an existing account row and record the change.

        Writes one ``audit_events`` row for every successful call, even
        when the submitted values equal the stored ones, in the same
        transaction. A call that raises writes none. ``created_by`` is
        the writer of this change, not the account's original creator.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no row has this code.
                DUPLICATE_ACCOUNT_NAME if the updated name collides with
                another account's name_key. UNKNOWN_ERROR if the audit
                insert is rejected.
        """

        async def _update() -> AccountModel | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel).where(AccountModel.code == account.code)
                )
                existing = result.scalar_one_or_none()
                if existing is None:
                    return None
                existing.name = account.name
                existing.name_key = account_lookup_key(account.name)
                existing.category = account.category.value
                session.add(_audit_row(AuditAction.UPDATE, account.code, created_by))
                await session.commit()
                return existing

        try:
            updated = await self._executor.run(_update())
        except IntegrityError as exc:
            raise self._on_duplicate(exc, account.code, account.name) from exc

        if updated is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=account.code,
            )

    async def exists_by_code(self, code: str) -> bool:
        async def _exists() -> bool:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel.id).where(AccountModel.code == code)
                )
                return result.scalar_one_or_none() is not None

        return await self._executor.run(_exists())

    async def exists_by_name(self, name: str) -> bool:
        key = account_lookup_key(name)

        async def _exists() -> bool:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel.id).where(AccountModel.name_key == key)
                )
                return result.scalar_one_or_none() is not None

        return await self._executor.run(_exists())

    async def get_by_code(self, code: str) -> Account | None:
        async def _get() -> AccountModel | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel).where(AccountModel.code == code)
                )
                return result.scalar_one_or_none()

        model = await self._executor.run(_get())
        return self._to_domain(model) if model is not None else None

    async def get_by_name(self, name: str) -> Account | None:
        key = account_lookup_key(name)

        async def _get() -> AccountModel | None:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel).where(AccountModel.name_key == key)
                )
                return result.scalar_one_or_none()

        model = await self._executor.run(_get())
        return self._to_domain(model) if model is not None else None

    async def list_all(self) -> list[Account]:
        async def _list() -> list[AccountModel]:
            async with self._session_factory() as session:
                result = await session.execute(select(AccountModel))
                return list[AccountModel](result.scalars().all())

        models = await self._executor.run(_list())
        return [self._to_domain(model) for model in models]

    async def delete_by_code(self, code: str, *, created_by: str) -> None:
        """Remove the account row with this code and record the deletion.

        The ``audit_events`` row is written in the same transaction as
        the delete, so a failed audit insert leaves the account in place.
        ``created_by`` is the caller performing the deletion.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no row has this code.
                UNKNOWN_ERROR if the audit insert is rejected.
        """

        async def _delete() -> bool:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AccountModel).where(AccountModel.code == code)
                )
                existing = result.scalar_one_or_none()
                if existing is None:
                    return False
                await session.delete(existing)
                session.add(_audit_row(AuditAction.DELETE, code, created_by))
                await session.commit()
                return True

        try:
            deleted = await self._executor.run(_delete())
        except IntegrityError as exc:
            raise AppError.unknown(cause=exc) from exc

        if not deleted:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=code,
            )

    @staticmethod
    def _on_duplicate(exc: IntegrityError, code: str, name: str) -> AppError:
        """Translate a unique-constraint violation into a domain conflict.

        AccountModel.code and AccountModel.name_key are declared with
        unique=True. Under the shared naming convention SQLAlchemy realizes each
        as a named UNIQUE constraint, uq_accounts_code and uq_accounts_name_key,
        and PostgreSQL reports a violation through the constraint_name field
        that violated_constraint() reads.

        Args:
            exc: The IntegrityError raised by the failed insert/update.
            code: The account code that was being written.
            name: The account name that was being written.

        Returns:
            AppError.conflict() with DUPLICATE_ACCOUNT_CODE or
            DUPLICATE_ACCOUNT_NAME when the violated constraint is recognized;
            AppError.unknown() otherwise, which is also what a rejected
            audit_events insert produces, so an unrecognized constraint fails
            loudly instead of misreporting which field conflicted.
        """
        constraint = violated_constraint(exc)

        if constraint == "uq_accounts_code":
            return AppError.conflict(
                code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
                resource="account",
                field_name="code",
                value=code,
            )

        if constraint == "uq_accounts_name_key":
            return AppError.conflict(
                code=ErrorCode.DUPLICATE_ACCOUNT_NAME,
                resource="account",
                field_name="name",
                value=name,
            )

        return AppError.unknown(cause=exc)

    @staticmethod
    def _to_domain(model: AccountModel) -> Account:
        """Reconstruct a validated Account from a persisted row.

        Constructs a real Account rather than bypassing validation, so
        every invariant Account enforces is re-checked on every read --
        storage corruption surfaces as a validation error here, not
        silently downstream.

        Args:
            model: The persisted row.

        Returns:
            A validated Account domain object.
        """
        return Account(
            code=model.code,
            name=model.name,
            category=AccountCategory(model.category),
        )
