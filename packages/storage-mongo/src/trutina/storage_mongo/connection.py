"""MongoDB connection lifecycle helpers.

Provides the application's MongoDB connection bootstrap and shutdown
functions. This module sits at the infrastructure boundary and is used
by the concrete MongoDB account repository and the MongoDB test
fixtures without introducing database concerns into services, domain
models, or CLI code.

Logging: connect() logs "db.connected" once the ping succeeds, and
disconnect() logs "db.disconnected". Neither log line carries
mongo.uri -- only non-secret settings (db name, timeouts, pool size)
-- since the URI can embed credentials directly
(mongodb://user:pass@host). This module imports nothing from
trutina.observability or structlog -- only logging.getLogger(__name__),
consistent with every other emitter in the workspace.
"""

import logging
from dataclasses import dataclass

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure
from trutina.config import MongoSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MongoConnection:
    """Verified MongoDB connection resources.

    Bundles the MongoDB client and the selected database into a single
    immutable value object so callers can pass persistence resources
    together after connectivity has been successfully verified.

    Attributes:
        client: Connected MongoDB client instance.
        db: Database selected from the configured MongoDB deployment.
    """

    client: AsyncMongoClient
    db: AsyncDatabase


async def connect(mongo: MongoSettings) -> MongoConnection:
    """Create and verify a MongoDB connection.

    Establishes a MongoDB client, verifies connectivity with a ping
    operation, and returns the client together with the configured
    database. If connectivity verification fails, the client is closed
    before the original exception is re-raised.

    On success, logs "db.connected" with non-secret settings only --
    the database name and connection/pool parameters, never mongo.uri,
    which can embed credentials directly in the connection string.

    Args:
        mongo: MongoDB configuration values.

    Returns:
        A verified MongoDB connection bundle containing both the client
        and the configured database.

    Raises:
        ConnectionFailure: If the MongoDB server cannot be reached or
            does not respond successfully to the connectivity check.
    """
    client = AsyncMongoClient(
        mongo.uri,
        serverSelectionTimeoutMS=mongo.server_selection_timeout_ms,
        minPoolSize=mongo.min_pool_size,
        retryWrites=mongo.retry_writes,
        retryReads=mongo.retry_reads,
    )

    try:
        await client.admin.command("ping")
    except ConnectionFailure:
        await client.close()
        raise

    db = client.get_database(mongo.db)

    logger.info(
        "db.connected",
        extra={
            "context": {
                "backend": "mongo",
                "db": mongo.db,
                "min_pool_size": mongo.min_pool_size,
                "server_selection_timeout_ms": mongo.server_selection_timeout_ms,
            }
        },
    )

    return MongoConnection(
        client=client,
        db=db,
    )


async def disconnect(connection: MongoConnection) -> None:
    """Release MongoDB connection resources.

    Closes the underlying MongoDB client associated with the supplied
    connection bundle. Logs "db.disconnected" after the client closes.

    Args:
        connection: Connection resources previously created by
            ``connect()``.
    """
    await connection.client.close()

    logger.info("db.disconnected", extra={"context": {"backend": "mongo"}})
