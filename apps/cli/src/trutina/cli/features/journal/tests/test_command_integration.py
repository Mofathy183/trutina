import pytest
from trutina.cli.composition import CliState, app
from trutina.cli.shared.ui import console
from typer.testing import CliRunner


def _invoke(
    runner: CliRunner, state: CliState, args: list[str], input: str | None = None
):
    """Invoke the CLI app against a real CliState, capturing console output.

    Mirrors the account integration tests' _invoke() helper exactly.
    """
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


def _seed_accounts(runner: CliRunner, state: CliState) -> None:
    """Seed the Cash/Sales Revenue accounts every journal test in this
    file depends on, through the real CLI `account create` command --
    not by reaching into a repo directly, since this file tests the
    CLI surface end to end.
    """
    runner.invoke(
        app,
        [
            "account",
            "create",
            "--code",
            "1001",
            "--name",
            "Cash",
            "--category",
            "asset",
        ],
        obj=state,
    )
    runner.invoke(
        app,
        [
            "account",
            "create",
            "--code",
            "4001",
            "--name",
            "Sales Revenue",
            "--category",
            "revenue",
        ],
        obj=state,
    )


def _create_entry(runner: CliRunner, state: CliState):
    return _invoke(
        runner,
        state,
        [
            "journal",
            "create",
            "--line",
            "Cash:100:0",
            "--line",
            "Sales Revenue:0:100",
        ],
    )


@pytest.mark.integration
class TestCreateCommand:
    async def test_creates_entry_and_persists_to_postgres(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _seed_accounts(cli_runner, real_cli_state)

        result, output = _create_entry(cli_runner, real_cli_state)

        assert result.exit_code == 0
        assert "Cash" in output
        assert "Sales Revenue" in output

        verify_result, verify_output = _invoke(
            cli_runner, real_cli_state, ["journal", "get", "1"]
        )
        assert verify_result.exit_code == 0
        assert "Cash" in verify_output

    async def test_unknown_account_raises_through_real_account_service(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        """No accounts seeded here -- every account reference is
        unresolvable against the real chart, proving JournalService's
        account validation runs against a real AccountService/postgres
        chart, not a fake.
        """
        result, output = _invoke(
            cli_runner,
            real_cli_state,
            [
                "journal",
                "create",
                "--line",
                "Cash:100:0",
                "--line",
                "Sales Revenue:0:100",
            ],
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output

    async def test_unbalanced_entry_raises_validation_error(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _seed_accounts(cli_runner, real_cli_state)

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            [
                "journal",
                "create",
                "--line",
                "Cash:100:0",
                "--line",
                "Sales Revenue:0:50",
            ],
        )

        assert result.exit_code == 1
        assert "Validation Error" in output or "journal.unbalanced" in output


@pytest.mark.integration
class TestGetCommand:
    async def test_finds_entry_after_real_round_trip(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _seed_accounts(cli_runner, real_cli_state)
        _create_entry(cli_runner, real_cli_state)

        result, output = _invoke(cli_runner, real_cli_state, ["journal", "get", "1"])

        assert result.exit_code == 0
        assert "#  1" in output

    async def test_unknown_journal_number_exits_one(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(cli_runner, real_cli_state, ["journal", "get", "999"])

        assert result.exit_code == 1
        assert "journal.unknown_entry" in output or "Validation Error" in output


@pytest.mark.integration
class TestListCommand:
    async def test_lists_entries_created_via_the_cli(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _seed_accounts(cli_runner, real_cli_state)
        _create_entry(cli_runner, real_cli_state)
        _create_entry(cli_runner, real_cli_state)

        result, output = _invoke(cli_runner, real_cli_state, ["journal", "list"])

        assert result.exit_code == 0
        assert "1" in output
        assert "2" in output

    async def test_shows_empty_state_on_a_fresh_database(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(cli_runner, real_cli_state, ["journal", "list"])

        assert result.exit_code == 0
        assert "No journal entries found." in output


@pytest.mark.integration
class TestCrossCommandWorkflow:
    async def test_create_get_list_round_trip_through_real_postgres(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _seed_accounts(cli_runner, real_cli_state)

        create_result, create_output = _create_entry(cli_runner, real_cli_state)
        assert create_result.exit_code == 0
        assert "#  1" in create_output

        get_result, get_output = _invoke(
            cli_runner, real_cli_state, ["journal", "get", "1"]
        )
        assert get_result.exit_code == 0
        assert "Cash" in get_output

        list_result, list_output = _invoke(
            cli_runner, real_cli_state, ["journal", "list"]
        )
        assert list_result.exit_code == 0
        assert "1" in list_output
