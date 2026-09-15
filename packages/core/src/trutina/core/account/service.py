"""
Service layer for the account feature.

AccountService coordinates account-related workflows and serves as the
only entry point for creating, updating, retrieving, listing, resolving,
and deleting accounts.

Responsibilities:

- Construct domain Account models from service DTOs.
- Enforce chart-level uniqueness rules.
- Coordinate persistence through AccountRepo.
- Translate domain validation failures into ValidationAppError.
- Return stable ViewModels to callers.

CLI commands and API routes depend only on this service and the
DTO contracts defined in dtos.py. They never interact directly with
Account, ChartOfAccounts, or repository implementations.
"""

from collections.abc import Awaitable, Callable

from pydantic import ValidationError
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    ValidationAppError,
)

from .dtos import (
    AccountViewModel,
    ChartOfAccountsViewModel,
    CreateAccountInput,
    UpdateAccountInput,
)
from .repo import AccountRepo
from .schemas.account import Account
from .schemas.chart import ChartOfAccounts

AccountPostingsCheck = Callable[[str], Awaitable[bool]]
"""A predicate: given an account name, returns True if any posting
references it.

Defined as a bare callable rather than a Protocol class because it is a
single-method capability with no state of its own -- AccountService
depends on this signature, never on what supplies it. This keeps
AccountService free of any import from the posting feature while still
letting delete_account() enforce the safeguard when a caller wires one
in.
"""


class AccountService:
    """Coordinates account-management workflows.

    AccountService is responsible for enforcing chart-level business rules
    that involve more than a single Account instance, including uniqueness
    checks and account-resolution workflows. Persistence is delegated to the
    configured AccountRepo implementation.

    Attributes:
        _repo: The persistence boundary for individual accounts.
        _has_postings: Optional predicate used by delete_account() to
            enforce the posting-history safeguard. When None, deletion
            performs no posting check -- the caller has chosen not to
            wire one in, not a failure of the service.
    """

    def __init__(
        self,
        repo: AccountRepo,
        has_postings: AccountPostingsCheck | None = None,
    ) -> None:
        """Initialize the service with an injected repository.

        Args:
            repo: Repository implementation used for account persistence.
            has_postings: Optional predicate checking whether an account
                name has any associated postings. AccountService never
                imports posting types directly -- callers that want the
                posting-history delete safeguard enforced must supply
                this closure themselves, typically bound to a
                PostingRepo.get_by_account() call at the composition
                root. Omitting it preserves the existing
                existence-check-only delete behavior.
        """
        self._repo = repo
        self._has_postings = has_postings

    async def create_account(self, dto: CreateAccountInput) -> AccountViewModel:
        """Validate and persist a new account.

        Checks for duplicate code and duplicate name via targeted
        existence queries before constructing the domain object or
        writing anything. If both checks pass, builds the domain Account
        (which validates its own structural invariants) and persists it.

        TOCTOU note: the existence checks and write are not atomic.
        Under concurrent load, two requests can both pass the existence
        checks before either writes. Storage-layer unique indexes are the
        authoritative guard for that window — the repository
        adapter translates DuplicateKeyError to AppError.conflict(), which
        propagates unchanged from here.

        Args:
            dto: Raw account creation input.

        Returns:
            The view model of the newly created account.

        Raises:
            AppError: DUPLICATE_ACCOUNT_CODE if an account with the same
                code already exists, or DUPLICATE_ACCOUNT_NAME if the name
                matches an existing account name. Also raised by the repo
                adapter if the storage layer catches a race that slipped
                past the existence checks above.
            ValidationAppError: If the account fields are structurally
                invalid (malformed name, etc.).
        """
        if await self._repo.exists_by_code(dto.code):
            raise AppError.conflict(
                code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
                resource="account",
                field_name="code",
                value=dto.code,
            )

        if await self._repo.exists_by_name(dto.name):
            raise AppError.conflict(
                code=ErrorCode.DUPLICATE_ACCOUNT_NAME,
                resource="account",
                field_name="name",
                value=dto.name,
            )

        try:
            account = Account(
                code=dto.code,
                name=dto.name,
                category=dto.category,
            )
        except ValidationError as exc:
            raise ValidationAppError.validation(exc) from exc

        await self._repo.create(account)

        return self._to_view_model(account)

    async def update_account(self, dto: UpdateAccountInput) -> AccountViewModel:
        """Apply a partial update to an existing account.

        Loads the current account and applies only the values explicitly
        provided by the caller.
        then runs a uniqueness pre-check for any changed name
        before persisting the updated record.

        Args:
            dto: Partial update input. Only fields explicitly set on
                the DTO are applied; omitted fields retain their current
                values.

        Returns:
            The view model of the updated account.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account with dto.code exists.
                DUPLICATE_ACCOUNT_NAME if the new name matches an existing
                account name, or the same code if the storage layer
                catches a race.
            ValidationAppError: If the merged field values fail domain
                validation.
        """
        existing = await self._repo.get_by_code(dto.code)

        if existing is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=dto.code,
            )

        new_name = dto.name if dto.name is not None else existing.name
        new_category = dto.category if dto.category is not None else existing.category

        # Only check name uniqueness if the name is actually changing.
        if new_name != existing.name and await self._repo.exists_by_name(new_name):
            raise AppError.conflict(
                code=ErrorCode.DUPLICATE_ACCOUNT_NAME,
                resource="account",
                field_name="name",
                value=new_name,
            )

        try:
            updated = Account(
                code=existing.code,
                name=new_name,
                category=new_category,
            )
        except ValidationError as exc:
            raise ValidationAppError.validation(exc) from exc

        await self._repo.update(updated)

        return self._to_view_model(updated)

    async def get_account(self, code: str) -> AccountViewModel:
        """Fetch a single account by its code.

        Args:
            code: The account code to look up.

        Returns:
            The view model for the matching account.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account has that code.
        """
        account = await self._repo.get_by_code(code)

        if account is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=code,
            )

        return self._to_view_model(account)

    async def get_chart(self) -> ChartOfAccounts:
        """Build the current chart of accounts as a single snapshot.

        Callers that need to resolve more than one account reference in
        the same logical operation — e.g. validating every line of a
        journal entry — must call this once and resolve all references
        against the same ChartOfAccounts instance. Calling
        resolve_account() in a loop instead would rebuild the chart from
        a fresh repo.list_all() on every call, and two of those calls are
        not guaranteed to see the same snapshot of the account data.

        Returns:
            A ChartOfAccounts built from every persisted account.
        """
        existing = await self._repo.list_all()
        return ChartOfAccounts(accounts=existing)

    async def resolve_account(self, reference: str) -> AccountViewModel:
        """Resolve a single journal-line account reference to an account.

        For resolving one reference at a time, e.g. a CLI lookup command.
        Callers that need to resolve multiple references as part of one
        logical operation (such as validating all lines of a journal
        entry) should call get_chart() once instead, to guarantee every
        reference resolves against the same snapshot of the chart.

        Args:
            reference: The account name as written on a journal line.

        Returns:
            The view model for the matching account.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account name matches the
                reference.
        """
        chart = await self.get_chart()
        account = chart.get_by_name(reference)

        if account is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=reference,
            )

        return self._to_view_model(account)

    async def list_accounts(self) -> ChartOfAccountsViewModel:
        """Fetch every account as a single chart view model.

        Unlike get_chart(), which returns the domain ChartOfAccounts for
        internal resolution use, this returns the service output contract view
        model.

        Returns:
            A ChartOfAccountsViewModel containing every persisted
            account.
        """
        accounts = await self._repo.list_all()

        return ChartOfAccountsViewModel(
            accounts=[self._to_view_model(account) for account in accounts]
        )

    async def delete_account(self, code: str) -> None:
        """Remove an account by its code.

        Verifies the account exists, then -- if a has_postings predicate
        was supplied at construction -- verifies the account has no
        associated ledger postings before removing it from persistence.
        Without a supplied predicate, this performs an existence check
        only, matching the previously documented behavior.

        Args:
            code: The account code to delete.

        Raises:
            AppError: UNKNOWN_ACCOUNT if no account with that code exists.
            AppError: ACCOUNT_HAS_POSTINGS if a has_postings predicate is
                configured and reports postings exist for this account.
        """
        existing = await self._repo.get_by_code(code)

        if existing is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=code,
            )

        if self._has_postings is not None and await self._has_postings(existing.name):
            raise AppError.conflict(
                code=ErrorCode.ACCOUNT_HAS_POSTINGS,
                resource="account",
                field_name="code",
                value=code,
            )

        await self._repo.delete_by_code(code)

    @staticmethod
    def _to_view_model(account: Account) -> AccountViewModel:
        """Build an AccountViewModel from a domain Account.

        Args:
            account: The validated domain Account.

        Returns:
            The read-only view model for this account.
        """
        return AccountViewModel(
            code=account.code,
            name=account.name,
            category=account.category,
            normal_balance=account.normal_balance,
        )
