from trutina.core.account import AccountRepo
from trutina.core.account.schemas import Account, ChartOfAccounts
from trutina.shared.errors import AppError, ErrorCode
from trutina.shared.rule import account_lookup_key


class FakeAccountRepo(AccountRepo):
    """In-memory AccountRepo for AccountService unit tests.

    This fake behaves according to the AccountRepo contract and provides
    lightweight inspection hooks for assertions.

    Inspection hooks record successful writes only. Each ``created_by_on_*``
    list is index-aligned with the hook beside it (``created_by_on_create``
    with ``created_accounts``, and so on), holds one value per successful
    call, and stays empty for a call that raised. The fake does not store
    ``created_by`` anywhere else, and it does not check for duplicate
    codes or names on ``create``.

    It does not simulate ``audit_events``; the audit row is a PostgreSQL
    adapter behavior, covered in ``account/tests/test_audit_integration.py``.
    """

    def __init__(
        self,
        chart: ChartOfAccounts | None = None,
    ) -> None:
        self._accounts: dict[str, Account] = {}

        self.created_accounts: list[Account] = []
        self.updated_accounts: list[Account] = []
        self.deleted_codes: list[str] = []

        self.created_by_on_create: list[str] = []
        self.created_by_on_update: list[str] = []
        self.created_by_on_delete: list[str] = []

        if chart is not None:
            for account in chart.accounts:
                self._accounts[account.code] = account

    async def create(self, account: Account, *, created_by: str) -> None:
        self.created_accounts.append(account)
        self.created_by_on_create.append(created_by)
        self._accounts[account.code] = account

    async def update(self, account: Account, *, created_by: str) -> None:
        if account.code not in self._accounts:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=account.code,
            )

        self.updated_accounts.append(account)
        self.created_by_on_update.append(created_by)
        self._accounts[account.code] = account

    async def exists_by_code(self, code: str) -> bool:
        return code in self._accounts

    async def exists_by_name(self, name: str) -> bool:
        lookup = account_lookup_key(name)

        return any(
            account_lookup_key(account.name) == lookup
            for account in self._accounts.values()
        )

    async def get_by_code(self, code: str) -> Account | None:
        return self._accounts.get(code)

    async def get_by_name(self, name: str) -> Account | None:
        lookup = account_lookup_key(name)

        for account in self._accounts.values():
            if account_lookup_key(account.name) == lookup:
                return account

        return None

    async def list_all(self) -> list[Account]:
        return list[Account](self._accounts.values())

    async def delete_by_code(self, code: str, *, created_by: str) -> None:
        if code not in self._accounts:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT,
                resource="account",
                identifier=code,
            )

        self.deleted_codes.append(code)
        self.created_by_on_delete.append(created_by)

        del self._accounts[code]
