from decimal import Decimal

from trutina.core.trial_balance import TrialBalanceService
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry

from tests.fakes import FakeTrialBalanceRepo


def make_account_balance_entry(
    account: str = "Cash",
    debit_total: Decimal = Decimal("100"),
    credit_total: Decimal = Decimal("0"),
) -> AccountBalanceEntry:
    return AccountBalanceEntry(
        account=account,
        debit_total=debit_total,
        credit_total=credit_total,
    )


def make_fake_trial_balance_repo(
    entries: list[AccountBalanceEntry] | None = None,
) -> FakeTrialBalanceRepo:
    return FakeTrialBalanceRepo(entries=entries)


def make_trial_balance_service(
    entries: list[AccountBalanceEntry] | None = None,
) -> tuple[TrialBalanceService, FakeTrialBalanceRepo]:
    repo = make_fake_trial_balance_repo(entries=entries)
    service = TrialBalanceService(repo)
    return service, repo
