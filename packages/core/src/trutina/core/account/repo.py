"""Repository contract for the account feature.

Defines the persistence boundary used by AccountService. All account
storage operations pass through this contract, regardless of the
underlying storage technology.

Implementations must remain asynchronous, must not contain business
rules, and must translate storage-specific failures into AppError
instances before they cross this boundary.

Exception Contract
------------------

Concrete implementations must translate storage-specific failures into
AppError before they cross the repository boundary.

Services depend only on AppError and must never be coupled to storage
libraries, database drivers, or transport-specific exceptions.

The exact translation strategy is implementation-specific.
"""

from abc import ABC, abstractmethod

from .schemas.account import Account


class AccountRepo(ABC):
    """Persistence contract for Account records.

    Implementations are responsible for storing and retrieving Account
    domain models while preserving chart-level uniqueness guarantees.

    Repository methods must:

    - Remain asynchronous.
    - Avoid business-rule enforcement.
    - Return None on lookup misses where documented.
    - Translate storage-specific failures into AppError.
    - Remain independent of CLI, Rich, and Typer concerns.

    Application-level uniqueness checks performed by AccountService are a
    user-experience optimization. Implementations must still protect
    account uniqueness at the persistence layer to prevent race conditions.
    """

    @abstractmethod
    async def create(self, account: Account, *, created_by: str) -> None:
        """Persist a new account.

        The account must not already exist. Implementations must
        translate a storage-level duplicate-key violation into
        AppError.conflict() before it leaves this method.

        Args:
            account: A fully validated domain Account.
            created_by: Opaque identifier of the caller performing the
                write, already checked as non-blank by AccountService.
                Implementations must accept it; whether and where it is
                stored is implementation-specific.

        Raises:
            AppError: DUPLICATE_ACCOUNT_CODE or DUPLICATE_ACCOUNT_NAME if
                the storage layer detects a duplicate (defense-in-depth
                against races that slip past the application-layer
                existence checks).
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def update(self, account: Account, *, created_by: str) -> None:
        """Overwrite an existing account record.

        Locates the record by ``account.code`` and replaces it in full.
        Implementations must translate a storage-level duplicate-key
        violation (e.g. a renamed account colliding with an existing
        name) into AppError.conflict() before it leaves this method.

        Args:
            account: A fully validated domain Account carrying the
                updated field values. The code is treated as the
                immutable lookup key.
            created_by: Opaque identifier of the caller performing this
                update (the writer of this change, not the account's
                original creator), already checked as non-blank by
                AccountService.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account with that code exists.
            AppError: DUPLICATE_ACCOUNT_NAME if the updated name collides
                with another account at the storage layer.
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def exists_by_code(self, code: str) -> bool:
        """Return whether an account with the supplied code exists.

        Used by the service layer when validating chart-level uniqueness
        before creating a new account.

        Args:
            code: The account code to test.

        Returns:
            True if an account with that code exists; otherwise False.

        Raises:
            AppError: STORAGE_UNAVAILABLE if account storage cannot be reached.
        """
        ...

    @abstractmethod
    async def exists_by_name(self, name: str) -> bool:
        """Return True if any account has this name.

        Used by the service layer as an application-level uniqueness
        pre-check before create or name-changing update. Comparison must
        follow the chart's canonical case-insensitive account-name lookup
        rules rather than the display-cased stored value.

        Args:
            name: The account name to test, matched case-insensitively.

        Returns:
            True if any account name matches, False otherwise.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Account | None:
        """Fetch a single account by its code.

        Args:
            code: The account code to look up.

        Returns:
            The matching Account, or None if no account has that code.
            None is a valid return value, not an error condition — the
            service decides whether to raise AppError.not_found().

        Raises:
            AppError: With code STORAGE_UNAVAILABLE if the backend
                cannot be reached.
        """
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Account | None:
        """Fetch a single account by name, case-insensitively.

        Args:
            name: The account name to look up.

        Returns:
            The matching Account, or None if no account matches.
            None is a valid return value, not an error condition.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def list_all(self) -> list[Account]:
        """Return all persisted accounts.

        Returns:
            Every account currently present in the chart.

        Raises:
            AppError: STORAGE_UNAVAILABLE if account storage cannot be reached.
        """
        ...

    @abstractmethod
    async def delete_by_code(self, code: str, *, created_by: str) -> None:
        """Remove an account by its code.

        Args:
            code: The account code to delete.
            created_by: Opaque identifier of the caller performing this
                deletion, already checked as non-blank by AccountService.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account with that code exists.
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...
