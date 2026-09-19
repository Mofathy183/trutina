"""In-memory TrialBalanceRepo implementation for TrialBalanceService unit tests.

Unlike FakeAccountRepo/FakeJournalRepo/FakePostingRepo, this fake has
nothing to store -- TrialBalanceRepo is read-only, so there is no
save/create counterpart to fake. It is seeded once, at construction,
with the entries it should return.

``calls`` records every ``as_of_date`` argument the fake was invoked
with, in call order -- this is the inspection hook tests use to assert
that TrialBalanceService actually forwards the caller's as_of_date to
the repository rather than dropping or defaulting it silently.
"""

from datetime import datetime

from trutina.core.trial_balance.repo import TrialBalanceRepo
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry


class FakeTrialBalanceRepo(TrialBalanceRepo):
    """In-memory TrialBalanceRepo for TrialBalanceService unit tests.

    Behaves according to the TrialBalanceRepo contract: returns exactly
    the entries it was seeded with, regardless of the as_of_date
    passed in -- this fake does not simulate date filtering, since
    that behavior is Postgres-adapter-specific and is covered by
    PostgresTrialBalanceRepo's own integration tests instead.

    Attributes:
        calls: Every as_of_date argument passed to
            get_account_balances, in call order. Empty until the first
            call.
    """

    def __init__(self, entries: list[AccountBalanceEntry] | None = None) -> None:
        self._entries: list[AccountBalanceEntry] = (
            list[AccountBalanceEntry](entries) if entries is not None else []
        )
        self.calls: list[datetime | None] = []

    async def get_account_balances(
        self,
        as_of_date: datetime | None = None,
    ) -> list[AccountBalanceEntry]:
        self.calls.append(as_of_date)
        return list[AccountBalanceEntry](self._entries)
