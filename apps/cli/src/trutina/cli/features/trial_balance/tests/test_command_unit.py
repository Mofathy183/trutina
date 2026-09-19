from decimal import Decimal

import pytest
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition.app import app
from trutina.cli.composition.state import CliState
from trutina.cli.shared.ui import console

from tests.factories import (
    make_account_balance_entry,
    make_fake_cli_context,
    make_fake_trial_balance_repo,
)


def _invoke(runner, state, args, input=None):
    """Invoke a command capturing output through the shared console,
    mirroring posting's own _invoke() helper -- cli.shared.ui.console
    is a module-level singleton with no confirmed guarantee it writes
    through CliRunner's own redirected stream.
    """
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


@pytest.fixture
def trial_balance_cli_state():
    """A portal-wrapped CliState pre-seeded with two AccountBalanceEntry
    rows in a FakeTrialBalanceRepo. Local to this test file -- no
    shared fixture currently provides a "trial-balance-ready" seeded
    state, and FakeTrialBalanceRepo must be seeded directly at
    construction (it does not aggregate from posted journal entries the
    way PostgresTrialBalanceRepo does -- see
    tests/fakes/trial_balance_repo.py's own docstring).
    """
    repo = make_fake_trial_balance_repo(
        entries=[
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("100"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("100"),
            ),
        ]
    )
    with start_blocking_portal(backend="asyncio") as portal:
        context = make_fake_cli_context(trial_balance_repo=repo)
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)


@pytest.fixture
def empty_trial_balance_cli_state():
    with start_blocking_portal(backend="asyncio") as portal:
        context = make_fake_cli_context()
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)


@pytest.mark.unit
class TestTrialBalanceCommand:
    def test_shows_populated_trial_balance(self, cli_runner, trial_balance_cli_state):
        result, output = _invoke(cli_runner, trial_balance_cli_state, ["trial-balance"])

        assert result.exit_code == 0
        assert "Cash" in output
        assert "Sales Revenue" in output
        assert "Balanced: Yes" in output

    def test_shows_no_postings_found_on_empty_ledger(
        self, cli_runner, empty_trial_balance_cli_state
    ):
        result, output = _invoke(
            cli_runner, empty_trial_balance_cli_state, ["trial-balance"]
        )

        assert result.exit_code == 0
        assert "No postings found" in output

    def test_accepts_as_of_flag(self, cli_runner, trial_balance_cli_state):
        result, _output = _invoke(
            cli_runner,
            trial_balance_cli_state,
            ["trial-balance", "--as-of", "2025-01-01"],
        )

        assert result.exit_code == 0

    def test_rejects_invalid_as_of_date(self, cli_runner, trial_balance_cli_state):
        result, _output = _invoke(
            cli_runner,
            trial_balance_cli_state,
            ["trial-balance", "--as-of", "not-a-date"],
        )

        assert result.exit_code == 2

    def test_registered_as_a_flat_top_level_command(
        self, cli_runner, trial_balance_cli_state
    ):
        """Confirms trial-balance is reachable directly off the root
        app (no "trial-balance <subcommand>" group indirection), per
        the Trial Balance Feature Plan ADR's Phase 5 decision.

        Typer/Click's own --help text is written via click.echo, not
        through cli.shared.ui.console, so this asserts on
        result.output (CliRunner's captured stdout) rather than the
        console.capture() helper _invoke() otherwise uses.
        """
        result = cli_runner.invoke(app, ["--help"], obj=trial_balance_cli_state)

        assert result.exit_code == 0
        assert "trial-balance" in result.output
