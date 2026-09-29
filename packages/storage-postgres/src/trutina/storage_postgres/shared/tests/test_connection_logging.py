import logging

import pytest
from trutina.storage_postgres.shared import connect, disconnect


class _RecordCollector(logging.Handler):
    """Collects LogRecords via a directly-attached handler instead of
    pytest's caplog fixture.

    caplog was found to intermittently miss records emitted from an
    `async def` test under this project's session-scoped asyncio loop
    (`asyncio_default_test_loop_scope = session` in pytest.ini) -- the
    log call itself was confirmed firing (test_engine_is_created_with_
    hide_parameters, which shares the same connect() call, passes), but
    caplog.records came back empty. Attaching a handler directly to the
    root logger sidesteps whatever timing interaction between pytest's
    LogCaptureHandler and the session-scoped runner was causing that,
    since it has no dependency on pytest-asyncio's internals.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def log_records():
    """Attach a plain logging.Handler to the root logger for one test.

    Restores the root logger's previous level and removes the handler
    on exit, so this never leaks into other tests -- mirroring the
    cleanup discipline of tests/fixtures/logging.py's autouse reset
    fixture for trutina-observability's own installed handler.
    """
    handler = _RecordCollector()
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


@pytest.mark.integration
class TestConnectLoggingNeverLeaksCredentials:
    async def test_db_connected_context_has_no_uri_key(
        self, test_settings, log_records
    ):
        connection = await connect(test_settings.postgres)
        try:
            record = next(
                r for r in log_records.records if r.getMessage() == "db.connected"
            )
            assert "uri" not in record.context
        finally:
            await disconnect(connection)

    async def test_db_connected_context_contains_no_credential_substring(
        self, test_settings, log_records
    ):
        connection = await connect(test_settings.postgres)
        try:
            record = next(
                r for r in log_records.records if r.getMessage() == "db.connected"
            )
            serialized = str(record.context)
            assert "@" not in serialized
            assert "postgresql" not in serialized
        finally:
            await disconnect(connection)

    async def test_engine_is_created_with_hide_parameters(self, test_settings):
        connection = await connect(test_settings.postgres)
        try:
            assert connection.engine.sync_engine.hide_parameters is True
        finally:
            await disconnect(connection)
