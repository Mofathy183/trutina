"""Integration tests for the posting CLI commands against real MongoDB.

portal.call(...) is synchronous -- it blocks the calling thread until
the portal's own event loop completes the work and returns the plain
result directly, not a coroutine. Every call site below is therefore
plain, unawaited portal.call(...), matching how CliState.call() and
command.py themselves invoke it. Fixtures/tests here are plain `def`,
not `async def` -- there is nothing to await once portal.call() is used
correctly.

portal.call(func, *args) accepts no keyword arguments, so the journal
service call that needs the keyword-only ``actor`` is wrapped in
functools.partial.

Assumption flagged: state.portal.call(state.context.get_journal_service)
/ get_posting_service() is assumed to resolve real Mongo-backed services
identically whether the CliContext was built for fake or real repos --
this mirrors the confirmed lazy-accessor contract in CliContext but the
exact accessor names on CliContext were not directly confirmed in the
files available for this task.
"""

import functools

import pytest
from trutina.cli.features.posting.command import app
from trutina.cli.shared.ui import console
from trutina.core.account.schemas.account import AccountCategory

from tests.factories import (
    TEST_ACTOR,
    make_create_account_input,
    make_create_journal_input,
)


def _invoke(runner, state, args, input=None):
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


@pytest.fixture
def seeded_real_state(real_cli_state):
    """Seeds two accounts and one unposted journal entry through the
    real, Mongo-backed services -- not through the CLI -- so posting
    commands under test have real persisted data to act on.

    Plain (non-async) fixture: every service resolution and service
    call below goes through portal.call(), which blocks synchronously
    and returns the plain result -- there is nothing to await here.
    """
    account_service = real_cli_state.portal.call(
        real_cli_state.context.get_account_service
    )
    journal_service = real_cli_state.portal.call(
        real_cli_state.context.get_journal_service
    )

    real_cli_state.portal.call(
        account_service.create_account,
        make_create_account_input(code="1001", name="Cash"),
    )
    real_cli_state.portal.call(
        account_service.create_account,
        make_create_account_input(
            code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
        ),
    )
    real_cli_state.portal.call(
        functools.partial(
            journal_service.create_journal_entry,
            make_create_journal_input(),
            actor=TEST_ACTOR,
        )
    )

    return real_cli_state


@pytest.mark.integration
class TestPostCommandIntegration:
    def test_posts_journal_entry_against_real_mongo(
        self, cli_runner, seeded_real_state
    ):
        result, output = _invoke(cli_runner, seeded_real_state, ["post", "1"])

        assert result.exit_code == 0
        assert "Cash" in output
        assert "Sales Revenue" in output

    def test_duplicate_post_fails_against_real_persistence(
        self, cli_runner, seeded_real_state
    ):
        _invoke(cli_runner, seeded_real_state, ["post", "1"])

        result, output = _invoke(cli_runner, seeded_real_state, ["post", "1"])

        assert result.exit_code == 1
        assert "posting.already_posted" in output or "Validation Error" in output


@pytest.mark.integration
class TestPostingRoundTripIntegration:
    def test_post_then_get_by_account_then_get_by_journal(
        self, cli_runner, seeded_real_state
    ):
        post_result, _ = _invoke(cli_runner, seeded_real_state, ["post", "1"])
        assert post_result.exit_code == 0

        by_account_result, by_account_output = _invoke(
            cli_runner, seeded_real_state, ["get-by-account", "Cash"]
        )
        by_journal_result, by_journal_output = _invoke(
            cli_runner, seeded_real_state, ["get-by-journal", "1"]
        )

        assert by_account_result.exit_code == 0
        assert "Cash" in by_account_output

        assert by_journal_result.exit_code == 0
        assert "Cash" in by_journal_output
        assert "Sales Revenue" in by_journal_output


@pytest.mark.integration
class TestEmptyStateIntegration:
    def test_get_by_account_empty_on_fresh_database(self, cli_runner, real_cli_state):
        result, output = _invoke(cli_runner, real_cli_state, ["get-by-account", "Cash"])

        assert result.exit_code == 0
        assert "No postings found" in output
