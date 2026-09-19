from trutina.cli.composition.context import CliContext
from trutina.config import TestSettings
from trutina.core.account import AccountRepo
from trutina.core.account.schemas import ChartOfAccounts
from trutina.core.journal import JournalRepo
from trutina.core.posting import PostingRepo
from trutina.core.trial_balance import TrialBalanceRepo

from tests.factories.account import make_fake_account_repo
from tests.factories.journal import make_fake_journal_repo
from tests.factories.posting import make_fake_posting_repo
from tests.factories.trial_balance import make_fake_trial_balance_repo


def make_fake_cli_context(
    *,
    account_repo: AccountRepo | None = None,
    journal_repo: JournalRepo | None = None,
    posting_repo: PostingRepo | None = None,
    trial_balance_repo: TrialBalanceRepo | None = None,
    chart: ChartOfAccounts | None = None,
) -> CliContext:
    """Build a CliContext wired entirely to Fake*Repo instances.

    Every repository defaults to its Fake* implementation, so a context
    returned by this factory can never open a PostgreSQL connection.

    Args:
        account_repo: Explicit AccountRepo to inject. Defaults to a
            fresh FakeAccountRepo seeded with `chart`.
        journal_repo: Explicit JournalRepo to inject. Defaults to a
            fresh FakeJournalRepo.
        posting_repo: Explicit PostingRepo to inject. Defaults to a
            fresh FakePostingRepo.
        trial_balance_repo: Explicit TrialBalanceRepo to inject.
            Defaults to a fresh, empty FakeTrialBalanceRepo. Unlike
            posting_repo, this fake has no aggregation link to
            whatever gets posted through posting_repo in the same
            test -- FakeTrialBalanceRepo only ever returns the rows it
            was seeded with at construction (see
            tests/fakes/trial_balance_repo.py's own docstring). Pass an
            explicitly seeded FakeTrialBalanceRepo when a test needs
            populated trial-balance output.
        chart: Optional ChartOfAccounts used to seed the default
            FakeAccountRepo. Ignored when `account_repo` is supplied
            directly.

    Returns:
        A CliContext with every repository faked, safe for unit tests.
    """
    return CliContext(
        settings=TestSettings(),
        account_repo=account_repo or make_fake_account_repo(chart=chart),
        journal_repo=journal_repo or make_fake_journal_repo(),
        posting_repo=posting_repo or make_fake_posting_repo(),
        trial_balance_repo=trial_balance_repo or make_fake_trial_balance_repo(),
    )
