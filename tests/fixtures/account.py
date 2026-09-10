from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition.state import CliState
from trutina.core.account import AccountRepo
from trutina.core.account.schemas import Account, AccountCategory, ChartOfAccounts
from trutina.storage_mongo.account import AccountDocument, MongoAccountRepo
from trutina.storage_mongo.shared import MongoExecutor

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_fake_account_repo,
    make_fake_cli_context,
)
from tests.fakes import FakeAccountRepo


@pytest.fixture
def account() -> Account:
    return make_account()


@pytest.fixture
def chart_of_accounts() -> ChartOfAccounts:
    return make_chart_of_accounts()


@pytest.fixture
def cash_account() -> Account:
    return make_account(code="1001", name="Cash", category=AccountCategory.ASSET)


@pytest.fixture
def revenue_account() -> Account:
    return make_account(
        code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
    )


@pytest.fixture
def mongo_account_repo(clean_db) -> AccountRepo:
    """A MongoAccountRepo instance backed by the clean test database.

    Declares clean_db as a dependency to guarantee:
    1. Beanie is initialized (clean_db depends on beanie_init).
    2. The database is empty before the test runs.

    Returns the abstract AccountRepo type so integration tests are written
    against the contract rather than the implementation. Tests that need
    to verify implementation-specific internals can type-narrow inline.
    """
    return MongoAccountRepo(MongoExecutor())


@pytest.fixture
def stub_account_document_settings(monkeypatch):
    """Let AccountDocument's constructor succeed without init_beanie().

    Document.__init__ unconditionally calls self.get_pymongo_collection(),
    which raises CollectionWasNotInitialized unless init_beanie() has
    registered the model (see beanie/odm/documents.py:1162). _to_document()
    never performs I/O — it only builds the object — so a stub settings
    object is sufficient; we don't need a real collection behind it.

    This relies on Beanie's internal get_settings()/pymongo_collection
    shape and may need revisiting on a Beanie upgrade.
    """
    monkeypatch.setattr(
        AccountDocument,
        "get_settings",
        classmethod(lambda cls: SimpleNamespace(pymongo_collection=None)),
    )


@pytest.fixture
def seeded_account_repo() -> FakeAccountRepo:
    """A FakeAccountRepo pre-populated with one known account.

    Named and scoped specifically for account command tests that need
    an existing account to `get`/`update`/`delete` — as distinct from
    `chart_of_accounts`, which exists for journal-line resolution and
    happens to double for this purpose today. Keeping this named
    separately means a future change to what `chart_of_accounts` seeds
    for journal tests can't silently break account command tests.
    """
    return make_fake_account_repo(
        chart=make_chart_of_accounts(accounts=[make_account(code="1001", name="Cash")])
    )


@pytest.fixture
def fake_cli_state_with_account(
    seeded_account_repo: FakeAccountRepo,
) -> Iterator[CliState]:
    """fake_cli_state, but pre-seeded with one known account.

    Use for `get`/`update`/`delete` command tests. `create` tests should
    use plain `fake_cli_state` since they exercise the empty-chart path.
    """
    context = make_fake_cli_context(account_repo=seeded_account_repo)
    with start_blocking_portal(backend="asyncio") as portal:
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)
