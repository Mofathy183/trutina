"""Delete sessions that died before a cutoff.

A session is dead when it is revoked, idle-expired or absolute-expired.
There is no scheduler in this project; run this by hand or from cron.
Retention is policy chosen here, not by the repository.

Usage:
    uv run python tools/purge-sessions.py [--older-than-days 7]

Reads PostgreSQL settings from the environment (TRUTINA_POSTGRES__URI).
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from trutina.config import Settings
from trutina.storage_postgres.session import PostgresSessionRepo
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


async def _run(older_than_days: float) -> int:
    connection = await connect(Settings().postgres)
    try:
        repo = PostgresSessionRepo(connection.session_factory, PostgresExecutor())
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        return await repo.purge_before(cutoff)
    finally:
        await disconnect(connection)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--older-than-days", type=float, default=7.0)
    args = parser.parse_args()
    removed = asyncio.run(_run(args.older_than_days))
    print(f"Removed {removed} dead session row(s).")


if __name__ == "__main__":
    main()
