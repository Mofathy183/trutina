import pytest
from trutina.cli.composition import CliState, app
from trutina.cli.shared.ui import console
from typer.testing import CliRunner


def _invoke(
    runner: CliRunner, state: CliState, args: list[str], input: str | None = None
):
    """Invoke the CLI app against a real CliState, capturing console output.

    Mirrors test_command.py's _invoke() helper exactly: asserts rely on
    result.exit_code (CliRunner, capture-independent) and on
    console.capture() for Rich-rendered content, since
    trutina.cli.shared.ui.console is a module-level singleton with no
    confirmed guarantee it writes through whatever stream CliRunner has
    redirected.
    """
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


def _create(runner: CliRunner, state: CliState, code: str, name: str, category: str):
    """Seed one account through the real CLI create command."""
    return _invoke(
        runner,
        state,
        ["account", "create", "--code", code, "--name", name, "--category", category],
    )


@pytest.mark.integration
class TestCreateCommand:
    async def test_creates_account_and_persists_to_postgres(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        assert result.exit_code == 0
        assert "1001" in output
        assert "Cash" in output

        verify_result, verify_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert verify_result.exit_code == 0
        assert "Cash" in verify_output

    async def test_duplicate_code_raises_through_real_postgres_unique_index(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _create(
            cli_runner, real_cli_state, "1001", "Petty Cash", "asset"
        )

        assert result.exit_code == 1
        assert "account.duplicate_code" in output or "Validation Error" in output


@pytest.mark.integration
class TestGetCommand:
    async def test_finds_account_by_code_after_real_round_trip(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(cli_runner, real_cli_state, ["account", "get", "1001"])

        assert result.exit_code == 0
        assert "1001" in output
        assert "Cash" in output

    async def test_unknown_identifier_exits_one(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "Nonexistent"]
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output


@pytest.mark.integration
class TestListCommand:
    async def test_lists_accounts_created_via_the_cli(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")
        _create(cli_runner, real_cli_state, "4001", "Sales Revenue", "revenue")

        result, output = _invoke(cli_runner, real_cli_state, ["account", "list"])

        assert result.exit_code == 0
        assert "1001" in output
        assert "4001" in output

    async def test_shows_empty_state_on_a_fresh_database(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(cli_runner, real_cli_state, ["account", "list"])

        assert result.exit_code == 0
        assert "No accounts found." in output


@pytest.mark.integration
class TestUpdateCommand:
    async def test_updates_name_and_persists_the_change(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "1001", "--name", "Main Cash"],
        )

        assert result.exit_code == 0
        assert "Main Cash" in output

        verify_result, verify_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert verify_result.exit_code == 0
        assert "Main Cash" in verify_output

    async def test_unknown_identifier_exits_one(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "Nonexistent", "--name", "New Name"],
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output


@pytest.mark.integration
class TestDeleteCommand:
    async def test_deletes_and_removes_from_postgres(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner, real_cli_state, ["account", "delete", "1001", "--yes"]
        )

        assert result.exit_code == 0
        assert "deleted" in output

        verify_result, verify_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert verify_result.exit_code == 1
        assert "account.unknown" in verify_output or "Validation Error" in verify_output

    async def test_unknown_identifier_exits_one(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        result, output = _invoke(
            cli_runner, real_cli_state, ["account", "delete", "Nonexistent", "--yes"]
        )

        assert result.exit_code == 1
        assert "account.unknown" in output or "Validation Error" in output


@pytest.mark.integration
class TestCrossCommandWorkflow:
    async def test_create_get_update_delete_round_trip_through_real_postgres(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        create_result, _ = _create(cli_runner, real_cli_state, "1001", "Cash", "asset")
        assert create_result.exit_code == 0

        get_result, get_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert get_result.exit_code == 0
        assert "Cash" in get_output

        update_result, update_output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "1001", "--name", "Main Cash"],
        )
        assert update_result.exit_code == 0
        assert "Main Cash" in update_output

        reget_result, reget_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert reget_result.exit_code == 0
        assert "Main Cash" in reget_output

        delete_result, delete_output = _invoke(
            cli_runner, real_cli_state, ["account", "delete", "1001", "--yes"]
        )
        assert delete_result.exit_code == 0
        assert "deleted" in delete_output

        final_get_result, _ = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert final_get_result.exit_code == 1


@pytest.mark.integration
class TestCreateCommandDomainValidation:
    async def test_invalid_account_name_raises_validation_error(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        """Proves the ValidationAppError branch of error_boundary() — every
        other failure test in this file exercises AppError instead.
        """
        result, output = _create(cli_runner, real_cli_state, "1001", "???", "asset")

        assert result.exit_code == 1
        assert "Validation Error" in output or "invalid_name" in output


@pytest.mark.integration
class TestCreateCommandDuplicateName:
    async def test_duplicate_name_with_different_code_raises_conflict(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _create(cli_runner, real_cli_state, "2001", "Cash", "asset")

        assert result.exit_code == 1
        assert "account.duplicate_name" in output or "Validation Error" in output


@pytest.mark.integration
class TestIdentifierResolutionByName:
    async def test_get_resolves_by_account_name(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(cli_runner, real_cli_state, ["account", "get", "Cash"])

        assert result.exit_code == 0
        assert "1001" in output

    async def test_update_resolves_by_account_name(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "Cash", "--name", "Main Cash"],
        )

        assert result.exit_code == 0
        assert "Main Cash" in output

    async def test_delete_resolves_by_account_name(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner, real_cli_state, ["account", "delete", "Cash", "--yes"]
        )

        assert result.exit_code == 0
        assert "deleted" in output


@pytest.mark.integration
class TestUpdateCommandPartialFields:
    async def test_updates_only_category_leaving_name_unchanged(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "1001", "--category", "expense"],
        )

        assert result.exit_code == 0
        assert "Cash" in output

        _, verify_output = _invoke(
            cli_runner, real_cli_state, ["account", "get", "1001"]
        )
        assert "Cash" in verify_output

    async def test_updates_name_and_category_together(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            [
                "account",
                "update",
                "1001",
                "--name",
                "Main Cash",
                "--category",
                "liability",
            ],
        )

        assert result.exit_code == 0
        assert "Main Cash" in output

    async def test_duplicate_name_on_rename_raises_conflict(
        self, cli_runner: CliRunner, real_cli_state: CliState
    ):
        _create(cli_runner, real_cli_state, "1001", "Cash", "asset")
        _create(cli_runner, real_cli_state, "2001", "Bank", "asset")

        result, output = _invoke(
            cli_runner,
            real_cli_state,
            ["account", "update", "2001", "--name", "Cash"],
        )

        assert result.exit_code == 1
        assert "account.duplicate_name" in output or "Validation Error" in output
