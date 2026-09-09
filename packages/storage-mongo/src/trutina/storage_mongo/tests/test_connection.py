from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import ConnectionFailure
from trutina.config import MongoSettings
from trutina.infrastructure.mongo import MongoConnection, connect, disconnect


@pytest.mark.unit
class TestConnect:
    @patch("trutina.infrastructure.mongo.connection.AsyncMongoClient")
    async def test_returns_connection_when_ping_succeeds(
        self,
        client_cls,
    ):
        client = MagicMock()

        client.admin.command = AsyncMock()
        client.get_database.return_value = "db"

        client_cls.return_value = client

        connection = await connect(
            MongoSettings(
                uri="mongodb://localhost:27017",
                db="trutina",
            )
        )

        client.admin.command.assert_awaited_once_with("ping")

        assert connection.client is client
        assert connection.db == "db"

    @patch("trutina.infrastructure.mongo.connection.AsyncMongoClient")
    async def test_closes_client_when_ping_fails(
        self,
        client_cls,
    ):
        client = MagicMock()

        client.admin.command = AsyncMock(side_effect=ConnectionFailure("boom"))
        client.close = AsyncMock()

        client_cls.return_value = client

        with pytest.raises(ConnectionFailure):
            await connect(MongoSettings())

        client.close.assert_awaited_once()


@pytest.mark.unit
class TestDisconnect:
    async def test_closes_client(self):
        client = AsyncMock()

        connection = MongoConnection(
            client=client,
            db=MagicMock(),
        )

        await disconnect(connection)

        client.close.assert_awaited_once()
