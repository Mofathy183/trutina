"""Integration tests for the created_by migration's upgrade and downgrade.

Steps the real migration history down to the revision before
a3f1c9d2b7e4 and back up, asserting the columns disappear and return.
Always restores head in a ``finally`` block, so the rest of the session
sees the full schema even if an assertion fails.
"""

import argparse
import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

PREVIOUS_REVISION = "7e1b970f05a7"


def _config() -> Config:
    # .../packages/storage-postgres/src/trutina/storage_postgres/shared/tests/<this file>
    # parents: 0=tests 1=shared 2=storage_postgres 3=trutina 4=src 5=storage-postgres
    package_root = Path(__file__).resolve().parents[5]
    cfg = Config(
        str(package_root / "alembic.ini"),
        cmd_opts=argparse.Namespace(x=["db=test"]),
    )
    cfg.set_main_option("script_location", str(package_root / "alembic"))
    return cfg


async def _created_by_present(engine) -> dict[str, bool]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {
                table: "created_by"
                in {col["name"] for col in inspect(sync_conn).get_columns(table)}
                for table in ("journal_entries", "postings")
            }
        )


@pytest.mark.integration
class TestCreatedByMigration:
    async def test_downgrade_removes_and_upgrade_restores_columns(
        self, schema_init, postgres_connection
    ):
        cfg = _config()
        loop = asyncio.get_event_loop()
        engine = postgres_connection.engine

        try:
            await loop.run_in_executor(
                None, lambda: command.downgrade(cfg, PREVIOUS_REVISION)
            )
            after_downgrade = await _created_by_present(engine)
        finally:
            await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))

        after_upgrade = await _created_by_present(engine)

        assert after_downgrade == {"journal_entries": False, "postings": False}
        assert after_upgrade == {"journal_entries": True, "postings": True}
