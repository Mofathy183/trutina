"""Concrete MongoDB implementation of the AccountRepo contract.

MongoAccountRepo bridges the accounting domain and MongoDB by translating
validated Account domain models into AccountDocument persistence models
and reconstructing them on retrieval. It performs no business validation,
uniqueness pre-checking, or accounting rule enforcement—those remain the
responsibility of AccountService. Its infrastructure responsibility is to
persist data and ensure storage-specific failures are translated into
AppError before crossing the repository boundary.

Query strategy
--------------
- code is the primary business identifier for all operations, matching the
    public AccountRepo contract.
- name_key (never the raw account name) is used for all name-based
    lookups. The uq_account_name_key unique index provides efficient,
    case-insensitive lookups without requiring collection-level collation.
- _id remains an internal MongoDB implementation detail. It never appears
    in repository contracts or domain models.

Mapping boundary
----------------
_to_document() is the single source of truth for converting a validated
Account into its persistence representation. Both create() and update()
use this mapping. During updates, the existing document is loaded only to
preserve persistence-managed metadata (_id and created_at) before the
replacement write.

DuplicateKeyError handling
--------------------------
DuplicateKeyError is intentionally allowed to bypass the generic MongoDB
error translator so repositories can convert uniqueness violations into
the appropriate domain AppError with business context. Every write method
delegates duplicate-key translation to _on_duplicate(), which inspects
the violated MongoDB index to determine which business uniqueness
constraint failed.

save() vs replace()
-------------------
Beanie's Document.save() performs an upsert, which could silently recreate
a previously deleted account during an update. Document.replace()
performs a replacement without upsert and raises DocumentNotFound if the
target document no longer exists. update() intentionally uses replace() to
preserve the AccountRepo contract.
"""

from datetime import UTC, datetime

from beanie.exceptions import DocumentNotFound
from pymongo.errors import DuplicateKeyError
from trutina.core.account.repo import AccountRepo
from trutina.core.account.schemas import Account
from trutina.infrastructure.mongo.account.document import AccountDocument
from trutina.infrastructure.mongo.error_translation import violated_index
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.errors import AppError, ErrorCode
from trutina.shared.rule import account_lookup_key


class MongoAccountRepo(AccountRepo):
    """Beanie-backed implementation of the AccountRepo persistence contract.

    MongoAccountRepo fulfills the AccountRepo interface by translating
    between validated Account domain objects and MongoDB persistence
    documents. It intentionally contains no accounting rules or business
    validation. All storage-specific failures are translated into
    AppError before crossing the repository boundary, ensuring callers
    remain independent of MongoDB and Beanie implementation details.

    Every database operation is executed through MongoExecutor so MongoDB
    error translation is applied consistently across all repository
    methods.

    Callers must ensure init_beanie() has been executed with
    AccountDocument registered before constructing this repository.

    Args:
        executor: Infrastructure collaborator responsible for executing
            Beanie operations with consistent MongoDB error translation.
    """

    def __init__(self, executor: MongoExecutor) -> None:
        self._executor = executor

    async def create(self, account: Account) -> None:
        """Persist a validated account as a new MongoDB document.

        Args:
            account: Validated Account domain model to persist.

        Raises:
            AppError: DUPLICATE_ACCOUNT_CODE if an existing account uses
                the same business code.
            AppError: DUPLICATE_ACCOUNT_NAME if another account already
                uses the same canonical name.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot complete the write.
        """
        doc = self._to_document(account)
        try:
            await self._executor.run(doc.insert())
        except DuplicateKeyError as exc:
            raise self._on_duplicate(exc, account) from exc

    async def update(self, account: Account) -> None:
        """Replace an existing account while preserving persistence metadata.

        Loads the current document to preserve persistence-managed fields
        (_id and created_at), rebuilds the document through the single
        mapping boundary, and replaces the stored document without
        performing an upsert.

        Two database round-trips are intentional: one retrieves immutable
        persistence metadata, and the second performs the replacement
        atomically.

        Args:
            account: Updated validated Account domain model.

        Raises:
            AppError: UNKNOWN_ACCOUNT if the account does not exist or is
                deleted concurrently before replacement.
            AppError: DUPLICATE_ACCOUNT_NAME if the updated canonical
                name conflicts with another account.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot complete the operation.
        """
        existing = await self._executor.run(
            AccountDocument.find_one(AccountDocument.code == account.code)
        )

        if existing is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=account.code,
            )

        updated_doc = self._to_document(account)
        updated_doc.id = existing.id
        updated_doc.created_at = existing.created_at

        try:
            await self._executor.run(updated_doc.replace())
        except DuplicateKeyError as exc:
            raise self._on_duplicate(exc, account) from exc
        except DocumentNotFound as exc:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=account.code,
            ) from exc

    async def delete_by_code(self, code: str) -> None:
        """Delete an account identified by its business code.

        Performs a single atomic delete operation. The deletion result is
        inspected directly to determine whether an account existed,
        avoiding a time-of-check/time-of-use race between separate lookup
        and delete operations.

        Args:
            code: Business identifier of the account to delete.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account exists with the given
                code.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot complete the operation.
        """
        result = await self._executor.run(
            AccountDocument.find(AccountDocument.code == code).delete()
        )

        if result is None or result.deleted_count == 0:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=code,
            )

    async def exists_by_code(self, code: str) -> bool:
        """Determine whether an account exists for a business code.

        Args:
            code: Business identifier to check.

        Returns:
            True if an account with the given code exists; otherwise
            False.
        """
        return await self._executor.run(
            AccountDocument.find(AccountDocument.code == code).exists()
        )

    async def exists_by_name(self, name: str) -> bool:
        """Determine whether an account exists for a canonical name.

        The supplied name is normalized using account_lookup_key() so the
        lookup follows the same case-insensitive uniqueness rules enforced
        by the Account domain model.

        Args:
            name: Account name to check.

        Returns:
            True if a matching account exists; otherwise False.
        """
        key = account_lookup_key(name)
        return await self._executor.run(
            AccountDocument.find(AccountDocument.name_key == key).exists()
        )

    async def get_by_code(self, code: str) -> Account | None:
        """Retrieve an account by its business code.

        Args:
            code: Business identifier of the account.

        Returns:
            The reconstructed Account if found; otherwise None.
        """
        doc = await self._executor.run(
            AccountDocument.find_one(AccountDocument.code == code)
        )
        return self._to_domain(doc) if doc else None

    async def get_by_name(self, name: str) -> Account | None:
        """Retrieve an account by its canonical name.

        The supplied name is normalized before lookup so retrieval follows
        the same case-insensitive semantics used for uniqueness
        enforcement.

        Args:
            name: Account name to retrieve.

        Returns:
            The reconstructed Account if found; otherwise None.
        """
        key = account_lookup_key(name)
        doc = await self._executor.run(
            AccountDocument.find_one(AccountDocument.name_key == key)
        )
        return self._to_domain(doc) if doc else None

    async def list_all(self) -> list[Account]:
        """Return every account ordered by ascending business code.

        The repository guarantees deterministic ordering regardless of
        MongoDB's underlying storage order.

        Returns:
            All persisted accounts sorted by business code.
        """
        docs = await self._executor.run(AccountDocument.find().sort("+code").to_list())
        return [self._to_domain(doc) for doc in docs]

    @staticmethod
    def _to_document(account: Account) -> AccountDocument:
        """Map a validated Account to its MongoDB persistence model.

        This method is the single mapping boundary between the accounting
        domain and the persistence layer. Every field written to MongoDB
        originates here.

        The normalized lookup key is derived from the canonical account
        name, updated_at is refreshed for every write, created_at is
        managed separately by persistence, and normal_balance is omitted
        because it is derived from the account category rather than
        stored.

        Args:
            account: Validated Account domain model.

        Returns:
            The corresponding AccountDocument ready for persistence.
        """
        return AccountDocument(
            code=account.code,
            name=account.name,
            name_key=account_lookup_key(account.name),
            category=account.category,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _to_domain(doc: AccountDocument) -> Account:
        """Reconstruct an Account domain model from persisted data.

        Domain validation executes again during reconstruction so account
        invariants remain enforced regardless of stored data. Derived
        values such as normal_balance are recomputed from the account
        category instead of being loaded from persistence.

        Args:
            doc: Persisted MongoDB account document.

        Returns:
            The reconstructed Account domain model.
        """
        return Account(
            code=doc.code,
            name=doc.name,
            category=doc.category,
        )

    def _on_duplicate(self, exc: DuplicateKeyError, account: Account) -> AppError:
        """Translate a storage uniqueness violation into a domain conflict.

        Inspects the violated MongoDB index to determine which business
        uniqueness constraint failed and converts it into the appropriate
        AppError. Unexpected indexes are treated as infrastructure
        translation failures rather than normal application errors.

        Args:
            exc: Duplicate key exception raised by MongoDB.
            account: Account involved in the failed write.

        Returns:
            The corresponding domain AppError.
        """
        field = violated_index(exc)
        match field:
            case "code":
                return AppError.conflict(
                    code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
                    resource="account",
                    field_name="code",
                    value=account.code,
                )
            case "name_key":
                return AppError.conflict(
                    code=ErrorCode.DUPLICATE_ACCOUNT_NAME,
                    resource="account",
                    field_name="name",
                    value=account.name,
                )
            case _:
                return AppError.unknown(cause=exc)
