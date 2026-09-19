"""Fixtures wiring real feature services to real PostgreSQL repositories.

These exist solely for service-integration tests under
``modules/*/tests/test_service_integration.py``. Unlike the unit-test
fixtures in ``tests/fixtures/{account,journal,posting}.py`` (which inject
``Fake*Repo`` instances), this module wires each service to its concrete
PostgreSQL adapter, mirroring the production dependency graph:

    AccountService -> PostgresAccountRepo
    JournalService -> PostgresJournalRepo, AccountService
    PostingService -> PostgresPostingRepo, JournalService
    TrialBalanceService -> PostgresTrialBalanceRepo

``services`` depends on ``postgres_account_repo``, ``postgres_journal_repo``,
and ``postgres_posting_repo`` -- all three depend on ``clean_pg_db``, so
requesting all three together does not collide: ``clean_pg_db`` truncates
every table once per test regardless of how many repo fixtures pull it in.

``trial_balance_service`` is deliberately a separate fixture, not folded
into ``services``'s tuple, because TrialBalanceService has no peer-service
dependency to wire (unlike JournalService/PostingService) -- it only needs
its own repo. Keeping it separate also avoids widening ``services``'s
return shape for every existing caller of that fixture.
"""

import pytest
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.core.trial_balance import TrialBalanceService

from tests.factories import make_create_account_input


@pytest.fixture
def services(postgres_account_repo, postgres_journal_repo, postgres_posting_repo):
    """Real services wired to real PostgreSQL repositories.

    Returns a ``(account_service, journal_service, posting_service)`` tuple
    so tests can compose whichever subset of the workflow they need without
    repeating the wiring inline.
    """
    account_service = AccountService(postgres_account_repo)
    journal_service = JournalService(
        repo=postgres_journal_repo,
        account_service=account_service,
    )
    posting_service = PostingService(
        repo=postgres_posting_repo,
        journal_service=journal_service,
    )
    return account_service, journal_service, posting_service


@pytest.fixture
def trial_balance_service(postgres_trial_balance_repo):
    """A real TrialBalanceService wired to a real PostgresTrialBalanceRepo.

    Separate from ``services`` -- see module docstring for why. Depends
    on ``postgres_trial_balance_repo`` (``tests/fixtures/postgres.py``),
    which shares the same ``clean_pg_db``/``postgres_connection`` chain
    every other Postgres-backed fixture in this test session uses, so
    combining this fixture with ``services`` in the same test observes
    one consistent, already-truncated database.
    """
    return TrialBalanceService(postgres_trial_balance_repo)


@pytest.fixture
async def simple_accounts(services):
    """Seed the two accounts that the default journal/posting factories expect.

    ``make_create_journal_input()`` (and therefore ``make_debit_line()`` /
    ``make_credit_line()``) defaults to "Cash" and "Sales Revenue" -- this
    fixture creates exactly those two accounts through the real
    ``AccountService`` so journal/posting workflow tests can rely on the
    default factory input without re-seeding the chart in every test.

    Returns the wired ``AccountService`` for tests that need to make
    additional assertions against it.
    """
    account_service, _journal_service, _posting_service = services

    await account_service.create_account(
        make_create_account_input(code="1001", name="Cash")
    )
    await account_service.create_account(
        make_create_account_input(
            code="4001",
            name="Sales Revenue",
            category=AccountCategory.REVENUE,
        )
    )

    return account_service
