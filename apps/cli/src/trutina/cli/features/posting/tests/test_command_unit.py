from functools import partial

import pytest
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition.state import CliState
from trutina.cli.features.posting.command import app
from trutina.cli.shared.ui import console
from trutina.core.account.schemas.account import AccountCategory
from trutina.shared.errors import ErrorCode

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_fake_journal_repo,
    make_fake_posting_repo,
    make_journal_entry,
)
from tests.factories.actor import TEST_ACTOR
from tests.factories.cli import make_fake_cli_context


def _invoke(runner, state, args, input=None):
    """Invoke a command capturing output through the shared console,
    since cli.shared.ui.console is a module-level singleton with no
    confirmed guarantee it writes through CliRunner's own redirected
    stream. Mirrors the confirmed helper shape from the testing prompt.
    """
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


def _simple_chart():
    return make_chart_of_accounts(
        accounts=[
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET),
            make_account(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        ]
    )


@pytest.fixture
def posting_cli_state():
    """A portal-wrapped CliState wired to fakes, pre-seeded with one
    unposted journal entry (#1). Local to this test file -- no shared
    fixture currently provides a "posting-ready" seeded state.
    """
    journal_repo = make_fake_journal_repo()
    posting_repo = make_fake_posting_repo()

    with start_blocking_portal(backend="asyncio") as portal:
        entry = make_journal_entry(journal_number=1)
        portal.call(partial(journal_repo.save, entry, created_by=TEST_ACTOR))

        context = make_fake_cli_context(
            journal_repo=journal_repo,
            posting_repo=posting_repo,
            chart=_simple_chart(),
        )
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)


@pytest.fixture
def empty_cli_state():
    with start_blocking_portal(backend="asyncio") as portal:
        context = make_fake_cli_context(chart=_simple_chart())
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)


@pytest.mark.unit
class TestPostCommandFlagMode:
    def test_posts_journal_entry(self, cli_runner, posting_cli_state):
        result, output = _invoke(cli_runner, posting_cli_state, ["post", "1"])

        assert result.exit_code == 0
        assert "Postings for Journal Entry #1" in output
        assert "Cash" in output
        assert "Sales Revenue" in output

    def test_raises_error_for_unknown_journal_number(
        self, cli_runner, posting_cli_state
    ):
        result, output = _invoke(cli_runner, posting_cli_state, ["post", "999"])

        assert result.exit_code == 1
        assert (
            ErrorCode.UNKNOWN_JOURNAL_ENTRY.value in output
            or "Validation Error" in output
        )

    def test_raises_error_when_already_posted(self, cli_runner, posting_cli_state):
        _invoke(cli_runner, posting_cli_state, ["post", "1"])

        result, output = _invoke(cli_runner, posting_cli_state, ["post", "1"])

        assert result.exit_code == 1
        assert (
            ErrorCode.JOURNAL_ALREADY_POSTED.value in output
            or "Validation Error" in output
        )

    def test_bad_journal_number_argument_is_usage_error(
        self, cli_runner, posting_cli_state
    ):
        result, _output = _invoke(
            cli_runner, posting_cli_state, ["post", "not-a-number"]
        )

        assert result.exit_code == 2


@pytest.mark.unit
class TestPostCommandInteractiveMode:
    def test_prompts_for_journal_number(self, cli_runner, posting_cli_state):
        result, output = _invoke(cli_runner, posting_cli_state, ["post"], input="1\n")

        assert result.exit_code == 0
        assert "Postings for Journal Entry #1" in output


@pytest.mark.unit
class TestGetByAccountCommand:
    def test_returns_postings_after_posting(self, cli_runner, posting_cli_state):
        _invoke(cli_runner, posting_cli_state, ["post", "1"])

        result, output = _invoke(
            cli_runner, posting_cli_state, ["get-by-account", "Cash"]
        )

        assert result.exit_code == 0
        assert "Cash" in output

    def test_empty_when_no_postings_exist(self, cli_runner, empty_cli_state):
        result, output = _invoke(
            cli_runner, empty_cli_state, ["get-by-account", "Cash"]
        )

        assert result.exit_code == 0
        assert "No postings found" in output

    def test_interactive_mode_prompts_for_account(self, cli_runner, posting_cli_state):
        _invoke(cli_runner, posting_cli_state, ["post", "1"])

        result, output = _invoke(
            cli_runner, posting_cli_state, ["get-by-account"], input="Cash\n"
        )

        assert result.exit_code == 0
        assert "Cash" in output


@pytest.mark.unit
class TestGetByJournalCommand:
    def test_returns_postings_after_posting(self, cli_runner, posting_cli_state):
        _invoke(cli_runner, posting_cli_state, ["post", "1"])

        result, output = _invoke(cli_runner, posting_cli_state, ["get-by-journal", "1"])

        assert result.exit_code == 0
        assert "Cash" in output
        assert "Sales Revenue" in output

    def test_empty_when_journal_number_not_posted(self, cli_runner, posting_cli_state):
        result, output = _invoke(cli_runner, posting_cli_state, ["get-by-journal", "1"])

        assert result.exit_code == 0
        assert "No postings found" in output

    def test_interactive_mode_prompts_for_journal_number(
        self, cli_runner, posting_cli_state
    ):
        _invoke(cli_runner, posting_cli_state, ["post", "1"])

        result, output = _invoke(
            cli_runner, posting_cli_state, ["get-by-journal"], input="1\n"
        )

        assert result.exit_code == 0
        assert "Cash" in output
