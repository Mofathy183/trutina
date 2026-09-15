"""Alembic environment script for trutina-storage-postgres.

Resolves the database URL from trutina-config rather than a hardcoded
value in alembic.ini, so migration history is always generated and
applied against the same connection every other part of the workspace
uses. All four feature model.py modules are imported for their side
effect of registering tables on the one shared Base.metadata -- Phase
2's single-registry design (see shared/model.py) is what lets
autogenerate diff against exactly one target instead of four.
"""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from trutina.config import Settings, TestSettings
from trutina.storage_postgres.account import (
    AccountModel,  # noqa: F401
)
from trutina.storage_postgres.journal import (
    JournalEntryModel,  # noqa: F401
    JournalLineModel,  # noqa: F401
)
from trutina.storage_postgres.posting import (
    PostingModel,  # noqa: F401
)
from trutina.storage_postgres.shared import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


_REPO_ROOT = Path(__file__).resolve().parents[3]
os.chdir(_REPO_ROOT)

target_metadata = Base.metadata


def get_url() -> str:
    """Resolve the database URL to run migrations against.

    `-x db=test` switches to TestSettings' TRUTINA_TEST_POSTGRES__URI --
    this is how CI runs `alembic upgrade head` against the test database
    without a second alembic.ini or a duplicated connection string.
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("db") == "test":
        return TestSettings().postgres.uri
    return Settings().postgres.uri


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
