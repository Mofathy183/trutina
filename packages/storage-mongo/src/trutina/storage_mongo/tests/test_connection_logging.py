import logging

import pytest
from trutina.storage_mongo import connect, disconnect


@pytest.mark.integration
class TestConnectLoggingNeverLeaksCredentials:
    async def test_db_connected_context_has_no_uri_key(self, test_settings, caplog):
        with caplog.at_level(logging.INFO):
            connection = await connect(test_settings.mongo)
        try:
            record = next(r for r in caplog.records if r.message == "db.connected")
            assert "uri" not in record.context
        finally:
            await disconnect(connection)

    async def test_db_connected_context_contains_no_credential_substring(
        self, test_settings, caplog
    ):
        with caplog.at_level(logging.INFO):
            connection = await connect(test_settings.mongo)
        try:
            record = next(r for r in caplog.records if r.message == "db.connected")
            serialized = str(record.context)
            assert "@" not in serialized
            assert "mongodb://" not in serialized
        finally:
            await disconnect(connection)
