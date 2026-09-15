"""Test fixtures for PostgreSQL infrastructure integration tests.

session_scoped postgres_connection is created once per test session,
mirroring mongo_connection's shape in tests/fixtures/mongo.py. schema_init
applies the real Alembic migration history once per session, so a
migration that doesn't actually reproduce model.py fails here instead of
surfacing as a surprise the first time someone runs `alembic upgrade head`
against a real environment. clean_pg_db truncates all tables before each
test, preserving schema and indexes.
"""

import asyncio
from pathlib import Path

import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from trutina.config import TestSettings
from trutina.storage_postgres.account.repository import PostgresAccountRepo
from trutina.storage_postgres.journal import PostgresJournalRepo
from trutina.storage_postgres.posting import PostgresPostingRepo
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


@pytest_asyncio.fixture(scope="session")
async def postgres_connection(test_settings: TestSettings):
    """Open a verified PostgreSQL connection for the entire test session.

    Teardown disposes the engine once, after the final test in the
    session runs.
    """
    connection = await connect(test_settings.postgres)

    yield connection

    await disconnect(connection)


@pytest_asyncio.fixture(scope="session")
async def schema_init(postgres_connection, test_settings):
    """Apply the real Alembic migration history once per test session.

    command.upgrade() is synchronous alembic machinery calling back into
    an async env.py that itself calls asyncio.run() -- calling it directly
    from this already-running event loop would raise "asyncio.run()
    cannot be called from a running event loop", so it's dispatched to a
    thread executor instead, giving env.py's asyncio.run() a fresh loop.
    """
    package_root = Path(__file__).resolve().parents[2] / "packages" / "storage-postgres"
    cfg = Config(str(package_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(package_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", test_settings.postgres.uri)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))
    yield


@pytest_asyncio.fixture
async def clean_pg_db(schema_init, postgres_connection):
    """Truncate every table before each test, preserving schema and indexes.

    RESTART IDENTITY resets bigint IDENTITY sequences (accounts.id,
    journal_entries.journal_number, etc.) so tests can assert on specific
    id/journal_number values without depending on prior test ordering.
    CASCADE is required because journal_lines/postings hold a RESTRICT
    foreign key to journal_entries -- without it, truncating
    journal_entries alone would fail with a foreign-key violation.
    """
    async with postgres_connection.engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE accounts, journal_entries, journal_lines, postings "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture
async def postgres_account_repo(clean_pg_db, postgres_connection):
    """A PostgresAccountRepo backed by the clean test database."""

    return PostgresAccountRepo(postgres_connection.session_factory, PostgresExecutor())


@pytest_asyncio.fixture
async def postgres_journal_repo(clean_pg_db, postgres_connection):
    """A PostgresJournalRepo backed by the clean test database."""

    return PostgresJournalRepo(postgres_connection.session_factory, PostgresExecutor())


@pytest_asyncio.fixture
async def postgres_posting_repo(clean_pg_db, postgres_connection):
    """A PostgresPostingRepo backed by the clean test database."""

    return PostgresPostingRepo(postgres_connection.session_factory, PostgresExecutor())
