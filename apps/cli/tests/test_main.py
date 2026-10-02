from unittest.mock import MagicMock

import pytest
from trutina.cli import main as main_module
from trutina.cli.composition.app import app

GROUPS = {"account", "journal", "posting"}
FLAT_COMMANDS = {"trial-balance"}


@pytest.mark.unit
class TestKnownCommands:
    def test_derives_registered_group_and_flat_command_names(self):
        assert main_module._known_commands(app) == GROUPS | FLAT_COMMANDS

    def test_includes_flat_command_registered_without_a_group(self):
        assert "trial-balance" in main_module._known_commands(app)

    def test_uses_explicit_command_name(self):
        app_mock = MagicMock()
        app_mock.registered_groups = []
        app_mock.registered_commands = [_fake_command("trial-balance")]

        assert main_module._known_commands(app_mock) == {"trial-balance"}

    def test_derives_name_from_callback_when_command_name_is_unset(self):
        def trial_balance():
            pass

        app_mock = MagicMock()
        app_mock.registered_groups = []
        app_mock.registered_commands = [
            _fake_command(None, callback=trial_balance),
        ]

        assert main_module._known_commands(app_mock) == {"trial-balance"}

    def test_skips_command_with_neither_name_nor_callback(self):
        app_mock = MagicMock()
        app_mock.registered_groups = []
        app_mock.registered_commands = [_fake_command(None, callback=None)]

        assert main_module._known_commands(app_mock) == set()

    def test_skips_group_without_a_name(self):
        app_mock = MagicMock()
        app_mock.registered_groups = [_fake_group(None), _fake_group("account")]
        app_mock.registered_commands = []

        assert main_module._known_commands(app_mock) == {"account"}


@pytest.mark.unit
class TestHelpFlags:
    def test_derives_help_flags_from_context_settings(self):
        assert main_module._help_flags(app) == {"-h", "--help"}


@pytest.mark.unit
class TestShouldEnterShell:
    def test_bare_invocation_enters_shell(self):
        assert main_module._should_enter_shell([], app) is True

    def test_long_help_flag_does_not_enter_shell(self):
        assert main_module._should_enter_shell(["--help"], app) is False

    def test_short_help_flag_does_not_enter_shell(self):
        assert main_module._should_enter_shell(["-h"], app) is False

    def test_unknown_token_enters_shell(self):
        assert main_module._should_enter_shell(["frobnicate"], app) is True

    @pytest.mark.parametrize("command", sorted(GROUPS))
    def test_known_group_dispatches_normally(self, command):
        assert main_module._should_enter_shell([command, "list"], app) is False

    @pytest.mark.parametrize("command", sorted(GROUPS))
    def test_known_group_with_help_flag_still_dispatches_normally(self, command):
        # e.g. `account --help` -- Typer/Click handles this itself once
        # inside that command's own parsing; it must not be intercepted
        # here as if it were the top-level help flag.
        assert main_module._should_enter_shell([command, "--help"], app) is False

    def test_flat_command_dispatches_normally(self):
        assert main_module._should_enter_shell(["trial-balance"], app) is False

    def test_flat_command_with_option_dispatches_normally(self):
        argv = ["trial-balance", "--as-of", "2025-06-30"]

        assert main_module._should_enter_shell(argv, app) is False

    def test_flat_command_with_help_flag_still_dispatches_normally(self):
        assert (
            main_module._should_enter_shell(["trial-balance", "--help"], app) is False
        )

    @pytest.mark.parametrize("name", sorted(GROUPS | FLAT_COMMANDS))
    def test_every_registered_name_dispatches_normally(self, name):
        assert main_module._should_enter_shell([name], app) is False

    def test_guard_covers_every_name_the_app_registers(self):
        # Regression guard: a future group or flat command must never fall
        # through to the shell. Reads the real app, so it needs no edit
        # when a command is added.
        for name in main_module._known_commands(app):
            assert main_module._should_enter_shell([name], app) is False, name


def _fake_context():
    context = MagicMock()

    async def fake_aclose():
        return None

    context.aclose = fake_aclose
    return context


def _fake_group(name: str | None) -> MagicMock:
    group = MagicMock()
    group.name = name
    return group


def _fake_command(name: str | None, *, callback=None) -> MagicMock:
    command = MagicMock()
    command.name = name
    command.callback = callback
    return command


@pytest.mark.unit
class TestRunDispatch:
    def test_enters_shell_for_bare_invocation(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr("sys.argv", ["trutina-cli"])

        main_module.run(_fake_context())

        run_shell_mock.assert_called_once()
        app_mock.assert_not_called()

    def test_dispatches_to_typer_for_known_command(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        app_mock.registered_groups = [
            _fake_group("account"),
            _fake_group("journal"),
            _fake_group("posting"),
        ]
        app_mock.registered_commands = []
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr("sys.argv", ["trutina-cli", "account", "list"])

        main_module.run(_fake_context())

        app_mock.assert_called_once()
        run_shell_mock.assert_not_called()

    def test_dispatches_to_typer_for_flat_command(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        app_mock.registered_groups = [_fake_group("account")]
        app_mock.registered_commands = [_fake_command("trial-balance")]
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr("sys.argv", ["trutina-cli", "trial-balance"])

        main_module.run(_fake_context())

        app_mock.assert_called_once()
        run_shell_mock.assert_not_called()

    def test_dispatches_to_typer_for_flat_command_with_option(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        app_mock.registered_groups = []
        app_mock.registered_commands = [_fake_command("trial-balance")]
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr(
            "sys.argv", ["trutina-cli", "trial-balance", "--as-of", "2025-06-30"]
        )

        main_module.run(_fake_context())

        app_mock.assert_called_once()
        run_shell_mock.assert_not_called()

    def test_enters_shell_for_unknown_token(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        app_mock.registered_groups = [_fake_group("account")]
        app_mock.registered_commands = [_fake_command("trial-balance")]
        app_mock.info.context_settings = {"help_option_names": ["-h", "--help"]}
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr("sys.argv", ["trutina-cli", "frobnicate"])

        main_module.run(_fake_context())

        run_shell_mock.assert_called_once()
        app_mock.assert_not_called()

    def test_dispatches_to_typer_for_top_level_help_flag(self, monkeypatch):
        run_shell_mock = MagicMock()
        app_mock = MagicMock()
        app_mock.registered_groups = []
        app_mock.registered_commands = []
        app_mock.info.context_settings = {"help_option_names": ["-h", "--help"]}
        monkeypatch.setattr(main_module, "run_shell", run_shell_mock)
        monkeypatch.setattr(main_module, "app", app_mock)
        monkeypatch.setattr("sys.argv", ["trutina-cli", "--help"])

        main_module.run(_fake_context())

        app_mock.assert_called_once()
        run_shell_mock.assert_not_called()
