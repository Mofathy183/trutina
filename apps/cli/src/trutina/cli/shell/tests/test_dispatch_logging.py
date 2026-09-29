"""Correlation-id acceptance tests for shell dispatch.

Phase 4's hard acceptance test: two commands dispatched through the
same shell session must not share a correlation id, and the id bound
around one command's app(...) call must not leak to the next. Mirrors
apps/api/.../test_app_logging.py's role for the API -- this is the CLI
side of the same guarantee.

Does NOT re-verify parse_line()/dispatch()'s own argv/warning behavior
(see test_dispatch.py) or configure_logging()/correlation_scope()
themselves (see trutina-observability's own test suite).
"""

import pytest
from trutina.cli.shell.dispatch import dispatch, run_help
from trutina.observability.correlation import get_correlation_id


@pytest.mark.unit
class TestDispatchCorrelation:
    def test_id_is_not_bound_outside_a_dispatched_line(self, fake_cli_state):
        dispatch(fake_cli_state, ["account", "list"])

        assert get_correlation_id() is None

    def test_two_dispatched_commands_get_different_ids(
        self, fake_cli_state, monkeypatch
    ):
        seen: list[str | None] = []

        import trutina.cli.shell.dispatch as dispatch_module

        real_app = dispatch_module.app

        def _recording_app(*args, **kwargs):
            seen.append(get_correlation_id())
            return real_app(*args, **kwargs)

        monkeypatch.setattr(dispatch_module, "app", _recording_app)

        dispatch(fake_cli_state, ["account", "list"])
        dispatch(fake_cli_state, ["account", "list"])

        assert len(seen) == 2
        assert seen[0] is not None
        assert seen[1] is not None
        assert seen[0] != seen[1]


@pytest.mark.unit
class TestRunHelpCorrelation:
    def test_id_is_not_bound_outside_run_help(self, fake_cli_state):
        run_help(fake_cli_state, [])

        assert get_correlation_id() is None

    def test_two_help_calls_get_different_ids(self, fake_cli_state, monkeypatch):
        seen: list[str | None] = []

        import trutina.cli.shell.dispatch as dispatch_module

        real_app = dispatch_module.app

        def _recording_app(*args, **kwargs):
            seen.append(get_correlation_id())
            return real_app(*args, **kwargs)

        monkeypatch.setattr(dispatch_module, "app", _recording_app)

        run_help(fake_cli_state, [])
        run_help(fake_cli_state, ["account"])

        assert len(seen) == 2
        assert seen[0] != seen[1]
