"""Test fixtures for the CLI layer, unit and integration tier."""

from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from anyio.from_thread import start_blocking_portal
from trutina.cli.composition import CliContext, CliState
from trutina.config import TestSettings
from typer.testing import CliRunner

from tests.factories import make_fake_cli_context


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer's CliRunner — shared across every CLI test, unit or integration."""
    return CliRunner()


@pytest.fixture
def fake_cli_context(chart_of_accounts) -> CliContext:
    """Unit-tier context: every repo is a Fake*Repo, zero I/O possible."""
    return make_fake_cli_context(chart=chart_of_accounts)


@pytest.fixture
def fake_cli_state(fake_cli_context: CliContext) -> Iterator[CliState]:
    """Unit-tier CliState: fake_cli_context paired with a real portal.

    No Mongo involved, so there's no loop-binding hazard.
    """
    with start_blocking_portal(backend="asyncio") as portal:
        state = CliState(context=fake_cli_context, portal=portal)
        try:
            yield state
        finally:
            portal.call(fake_cli_context.aclose)


@pytest_asyncio.fixture
async def real_cli_context(test_settings, clean_pg_db) -> AsyncGenerator[CliContext]:
    """Integration-tier context for direct `await`-based CliContext tests
    ONLY (accessor caching, aclose() idempotency, override precedence,
    OperationalError -> AppError.storage_unavailable()).
    """
    context = CliContext(settings=test_settings)
    try:
        yield context
    finally:
        await context.aclose()


@pytest_asyncio.fixture
async def real_cli_state(
    test_settings: TestSettings,
    clean_pg_db,
    postgres_connection,
) -> AsyncGenerator[CliState]:
    """Integration-tier CliState: real PostgreSQL, entirely portal-owned.

    Because Typer command dispatch is synchronous, the CliContext built
    here only ever gets used from inside the portal's own thread and
    event loop (via state.call()), so its lazy `_get_connection()` opens
    its own PostgreSQL engine bound to that portal's loop. That engine
    is scoped entirely to this fixture's `PostgresConnection` instance
    -- there is no class-level or module-level registration step for it
    to corrupt, so no re-initialization step is needed after the portal
    closes.
    """
    context = CliContext(settings=test_settings)
    with start_blocking_portal(backend="asyncio") as portal:
        state = CliState(context=context, portal=portal)
        try:
            yield state
        finally:
            portal.call(context.aclose)
