"""Delete login-attempt rows older than a cutoff.

There is no scheduler in this project; run this by hand or from cron.
Throttling (M2.7) also purges opportunistically, so this is housekeeping,
not a correctness requirement.

Usage:
    uv run python tools/purge-login-attempts.py [--older-than-hours 24]

Reads PostgreSQL settings from the environment (TRUTINA_POSTGRES__URI).
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from trutina.config import Settings
from trutina.storage_postgres.login_attempt import PostgresLoginAttemptRepo
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


async def _run(older_than_hours: float) -> int:
    connection = await connect(Settings().postgres)
    try:
        repo = PostgresLoginAttemptRepo(connection.session_factory, PostgresExecutor())
        cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
        return await repo.purge_before(cutoff)
    finally:
        await disconnect(connection)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--older-than-hours", type=float, default=24.0)
    args = parser.parse_args()
    removed = asyncio.run(_run(args.older_than_hours))
    print(f"Removed {removed} login attempt row(s).")


if __name__ == "__main__":
    main()
