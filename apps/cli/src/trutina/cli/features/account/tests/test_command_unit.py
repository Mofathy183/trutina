from collections.abc import Iterator

import pytest
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition import CliState, app
from trutina.cli.shared.ui import console
from trutina.shared.errors import AppError, ErrorCode
from typer.testing import CliRunner

from tests.factories import make_chart_of_accounts
from tests.factories.cli import make_fake_cli_context


@pytest.fixture
def empty_cli_state() -> Iterator[CliState]:
    """CliState backed by a genuinely empty chart of accounts.

    fake_cli_state (tests/fixtures/cli.py) is NOT empty -- it seeds from
    chart_of_accounts, which defaults to a single "Cash"/"1001" account.
    Command tests that exercise the empty-chart path (create into an
    empty chart, `list` with no accounts) must use this fixture instead,
    matching the same fix already applied in test_handler.py.
    """
    context = make_fake_cli_context(chart=make_chart_of_accounts(accounts=[]))
    with start_blocking_portal(backend="asyncio") as portal:
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)


def _invoke(
    runner: CliRunner, state: CliState, args: list[str], input: str | None = None
):
    """Invoke the CLI app with a fake CliState and capture console output.

    Returns a (result, captured_output) pair so tests can assert on
    both the exit code (from CliRunner) and the Rich-rendered content
    (from console.capture(), independent of CliRunner's own stream
    redirection -- see module docstring).
    """
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


@pytest.mark.unit
class TestCreateCommandFlagMode:
    def test_creates_account_and_exits_zero(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner,
            empty_cli_state,
            [
                "account",
                "create",
                "--code",
                "2001",
                "--name",
                "Bank",
                "--category",
                "asset",
            ],
        )

        assert result.exit_code == 0
        assert "2001" in output
        assert "Bank" in output

    def test_persists_account_through_the_real_service(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        _invoke(
            cli_runner,
            empty_cli_state,
            [
                "account",
                "create",
                "--code",
                "2001",
                "--name",
                "Bank",
                "--category",
                "asset",
            ],
        )

        service = empty_cli_state.portal.call(
            empty_cli_state.context.get_account_service
        )
        fetched = empty_cli_state.portal.call(service.get_account, "2001")
        assert fetched.name == "Bank"

    def test_category_is_case_insensitive(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, _ = _invoke(
            cli_runner,
            empty_cli_state,
            [
                "account",
                "create",
                "--code",
                "2001",
                "--name",
                "Bank",
                "--category",
                "ASSET",
            ],
        )

        assert result.exit_code == 0

    def test_invalid_category_exits_with_usage_error(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, _ = _invoke(
            cli_runner,
            empty_cli_state,
            [
                "account",
                "create",
                "--code",
                "2001",
                "--name",
                "Bank",
                "--category",
                "Nonsense",
            ],
        )

        assert result.exit_code == 2

    def test_partial_flags_exits_with_usage_error(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, _ = _invoke(
            cli_runner,
            empty_cli_state,
            ["account", "create", "--code", "2001"],
        )

        assert result.exit_code == 2

    def test_duplicate_code_renders_error_panel_and_exits_one(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            [
                "account",
                "create",
                "--code",
                "1001",
                "--name",
                "Petty Cash",
                "--category",
                "asset",
            ],
        )

        assert result.exit_code == 1
        assert "Validation Error" in output or "account.duplicate_code" in output

    def test_invalid_code_renders_error_panel_and_exits_one(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner,
            empty_cli_state,
            [
                "account",
                "create",
                "--code",
                "sdgi",
                "--name",
                "Bank",
                "--category",
                "asset",
            ],
        )

        assert result.exit_code == 1
        assert "account.invalid_code" in output

        service = empty_cli_state.portal.call(
            empty_cli_state.context.get_account_service
        )
        with pytest.raises(AppError) as exc_info:
            empty_cli_state.portal.call(service.get_account, "sdgi")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.unit
class TestCreateCommandInteractiveMode:
    def test_prompts_for_all_fields_and_creates_account(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner,
            empty_cli_state,
            ["account", "create"],
            input="2001\nBank\n1\n",
        )

        assert result.exit_code == 0
        assert "2001" in output
        assert "Bank" in output


@pytest.mark.unit
class TestGetCommand:
    def test_finds_account_by_code_argument(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner, fake_cli_state_with_account, ["account", "get", "1001"]
        )

        assert result.exit_code == 0
        assert "1001" in output
        assert "Cash" in output

    def test_finds_account_by_name_argument(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner, fake_cli_state_with_account, ["account", "get", "Cash"]
        )

        assert result.exit_code == 0
        assert "1001" in output

    def test_prompts_for_identifier_when_omitted(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner, fake_cli_state_with_account, ["account", "get"], input="1001\n"
        )

        assert result.exit_code == 0
        assert "1001" in output

    def test_unknown_identifier_renders_error_panel_and_exits_one(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "get", "Nonexistent"],
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output


@pytest.mark.unit
class TestListCommand:
    def test_lists_seeded_accounts(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner, fake_cli_state_with_account, ["account", "list"]
        )

        assert result.exit_code == 0
        assert "1001" in output
        assert "Cash" in output

    def test_shows_empty_state_when_no_accounts(
        self, cli_runner: CliRunner, empty_cli_state: CliState
    ):
        result, output = _invoke(cli_runner, empty_cli_state, ["account", "list"])

        assert result.exit_code == 0
        assert "No accounts found." in output


@pytest.mark.unit
class TestUpdateCommandFlagMode:
    def test_updates_name_and_exits_zero(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "update", "1001", "--name", "Main Cash"],
        )

        assert result.exit_code == 0
        assert "Main Cash" in output

    def test_updates_by_name_identifier(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "update", "Cash", "--name", "Main Cash"],
        )

        assert result.exit_code == 0
        assert "Main Cash" in output

    def test_unknown_identifier_renders_error_panel_and_exits_one(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "update", "Nonexistent", "--name", "New Name"],
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output

    def test_persists_updated_account_through_the_real_service(
        self,
        cli_runner: CliRunner,
        fake_cli_state_with_account: CliState,
    ):
        _invoke(
            cli_runner,
            fake_cli_state_with_account,
            [
                "account",
                "update",
                "1001",
                "--name",
                "Main Cash",
            ],
        )

        service = fake_cli_state_with_account.portal.call(
            fake_cli_state_with_account.context.get_account_service
        )
        fetched = fake_cli_state_with_account.portal.call(
            service.get_account,
            "1001",
        )

        assert fetched.name == "Main Cash"


@pytest.mark.unit
class TestUpdateCommandInteractiveMode:
    def test_prompts_seeded_with_current_values(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        # Field prompts default to the current name/category, so pressing
        # Enter on both keeps them unchanged; only a real keystroke on
        # the category selection prompt is needed to pick option 1.
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "update", "1001"],
            input="\n1\n",
        )

        assert result.exit_code == 0
        assert "Cash" in output


@pytest.mark.unit
class TestDeleteCommand:
    def test_deletes_with_yes_flag_and_skips_confirmation(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "delete", "1001", "--yes"],
        )

        assert result.exit_code == 0
        assert "Cash" in output
        assert "deleted" in output

    def test_deletes_when_confirmed_interactively(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "delete", "1001"],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "deleted" in output

    def test_aborts_and_exits_zero_when_declined(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "delete", "1001"],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Aborted" in output

    def test_does_not_delete_the_account_when_declined(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "delete", "1001"],
            input="n\n",
        )

        service = fake_cli_state_with_account.portal.call(
            fake_cli_state_with_account.context.get_account_service
        )
        fetched = fake_cli_state_with_account.portal.call(service.get_account, "1001")
        assert fetched.code == "1001"

    def test_unknown_identifier_renders_error_panel_and_exits_one(
        self, cli_runner: CliRunner, fake_cli_state_with_account: CliState
    ):
        result, output = _invoke(
            cli_runner,
            fake_cli_state_with_account,
            ["account", "delete", "Nonexistent", "--yes"],
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output

    def test_removes_account_through_the_real_service(
        self,
        cli_runner: CliRunner,
        fake_cli_state_with_account: CliState,
    ):
        _invoke(
            cli_runner,
            fake_cli_state_with_account,
            [
                "account",
                "delete",
                "1001",
                "--yes",
            ],
        )

        service = fake_cli_state_with_account.portal.call(
            fake_cli_state_with_account.context.get_account_service
        )

        with pytest.raises(AppError) as exc_info:
            fake_cli_state_with_account.portal.call(
                service.get_account,
                "1001",
            )

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
