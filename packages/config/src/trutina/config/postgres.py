"""PostgreSQL connection settings.

Defines PostgresSettings, the nested configuration group consumed by
trutina-storage-postgres's connect(). A plain pydantic BaseModel, never
its own BaseSettings, so it can only ever be constructed as part of
Settings/TestSettings's own env-prefix and dotenv-file resolution --
never independently from the environment.
"""

from pydantic import BaseModel, Field


class PostgresSettings(BaseModel):
    """PostgreSQL connection settings for trutina-storage-postgres.

    Every field maps to a create_async_engine() keyword in
    trutina.storage_postgres.shared.connection.connect(). This class
    describes connection shape only -- it performs no I/O and verifies
    no connectivity itself; that guarantee belongs to connect().

    Attributes:
        uri: SQLAlchemy async connection URI in the form
            postgresql+asyncpg://user:pass@host:port/db. The database
            name lives in the URI path -- a single DSN fully describes
            the connection target for asyncpg, so there is no separate
            db field to split out.
        connect_timeout_s: Max seconds to wait for a new connection
            before raising, passed to asyncpg as
            connect_args={"timeout": ...}. Deliberately named in
            seconds, not milliseconds, to match asyncpg's own `timeout`
            unit -- do not assume millisecond granularity when reading
            or setting this from an env var.
        pool_size: Minimum number of connections SQLAlchemy's pool keeps
            open.
        max_overflow: Additional connections allowed above pool_size
            under load, closed again once idle.
        pool_pre_ping: When True, SQLAlchemy issues a lightweight
            liveness check on a pooled connection before handing it to a
            caller, so a connection silently killed by the server (idle
            timeout, restart, failover) is detected and replaced instead
            of surfacing as a confusing mid-query failure.
    """

    uri: str = Field(
        default="postgresql+asyncpg://localhost:5432/trutina",
        description="SQLAlchemy async connection URI (postgresql+asyncpg://...).",
    )
    connect_timeout_s: float = Field(
        default=5.0,
        description="Max seconds to wait for a new connection before raising.",
    )
    pool_size: int = Field(
        default=1,
        description="Minimum number of connections kept open in the pool.",
    )
    max_overflow: int = Field(
        default=10,
        description="Additional connections allowed above pool_size under load.",
    )
    pool_pre_ping: bool = Field(
        default=True,
        description=(
            "Test each pooled connection with a lightweight query before "
            "handing it out, so a connection killed by the server is "
            "detected and replaced rather than surfacing as a query failure."
        ),
    )
