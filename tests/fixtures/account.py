from collections.abc import Iterator

import pytest
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition.state import CliState
from trutina.core.account.schemas import Account, AccountCategory, ChartOfAccounts

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
