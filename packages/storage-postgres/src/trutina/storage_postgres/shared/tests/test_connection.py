from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError
from trutina.config import PostgresSettings
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.shared.connection import (
    PostgresConnection,
    _is_timeout,
    connect,
    disconnect,
)


def _make_engine(*, ping_error: Exception | None = None) -> MagicMock:
    conn = AsyncMock()
    if ping_error is not None:
        conn.execute.side_effect = ping_error
    connect_cm = MagicMock()
    connect_cm.__aenter__ = AsyncMock(return_value=conn)
    connect_cm.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = connect_cm
    engine.dispose = AsyncMock()
    return engine


def _operational_error(cause: BaseException | None = None) -> OperationalError:
    exc = OperationalError("SELECT 1", {}, Exception("boom"))
    if cause is not None:
        exc.__cause__ = cause
    return exc


@pytest.mark.unit
class TestConnect:
    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_returns_connection_when_ping_succeeds(self, create_engine):
        engine = _make_engine()
        create_engine.return_value = engine

        connection = await connect(PostgresSettings())

        assert connection.engine is engine

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_executes_select_1_to_verify_connectivity(self, create_engine):
        engine = _make_engine()
        create_engine.return_value = engine

        await connect(PostgresSettings())

        conn = engine.connect.return_value.__aenter__.return_value
        conn.execute.assert_awaited_once()

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_passes_settings_through_to_create_async_engine(self, create_engine):
        engine = _make_engine()
        create_engine.return_value = engine
        settings = PostgresSettings(
            uri="postgresql+asyncpg://x:y@host:5432/db",
            connect_timeout_s=9.0,
            pool_size=3,
            max_overflow=7,
            pool_pre_ping=False,
        )

        await connect(settings)

        _, kwargs = create_engine.call_args
        assert kwargs["pool_size"] == 3
        assert kwargs["max_overflow"] == 7
        assert kwargs["pool_pre_ping"] is False
        assert kwargs["connect_args"] == {"timeout": 9.0}


@pytest.mark.unit
class TestConnectErrorTranslation:
    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_raises_storage_unavailable_when_connection_is_refused(
        self, create_engine
    ):
        cause = ConnectionRefusedError("refused")
        engine = _make_engine(ping_error=_operational_error(cause=cause))
        create_engine.return_value = engine

        with pytest.raises(AppError) as exc_info:
            await connect(PostgresSettings())

        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_raises_storage_timeout_when_cause_chain_has_a_timeout(
        self, create_engine
    ):
        cause = TimeoutError("connect timed out")
        engine = _make_engine(ping_error=_operational_error(cause=cause))
        create_engine.return_value = engine

        with pytest.raises(AppError) as exc_info:
            await connect(PostgresSettings())

        assert exc_info.value.code == ErrorCode.STORAGE_TIMEOUT

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_raises_storage_timeout_when_timeout_is_nested_deeper_in_the_chain(
        self, create_engine
    ):
        innermost = TimeoutError("asyncio wait_for expired")
        middle = Exception("driver-level wrapper")
        middle.__cause__ = innermost
        engine = _make_engine(ping_error=_operational_error(cause=middle))
        create_engine.return_value = engine

        with pytest.raises(AppError) as exc_info:
            await connect(PostgresSettings())

        assert exc_info.value.code == ErrorCode.STORAGE_TIMEOUT

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_preserves_the_original_exception_as_cause(self, create_engine):
        original = _operational_error(cause=ConnectionRefusedError("refused"))
        engine = _make_engine(ping_error=original)
        create_engine.return_value = engine

        with pytest.raises(AppError) as exc_info:
            await connect(PostgresSettings())

        assert exc_info.value.cause is original

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_disposes_engine_when_ping_fails(self, create_engine):
        engine = _make_engine(ping_error=_operational_error())
        create_engine.return_value = engine

        with pytest.raises(AppError):
            await connect(PostgresSettings())

        engine.dispose.assert_awaited_once()

    @patch("trutina.storage_postgres.shared.connection.create_async_engine")
    async def test_disposes_engine_before_raising_on_timeout(self, create_engine):
        engine = _make_engine(
            ping_error=_operational_error(cause=TimeoutError("expired"))
        )
        create_engine.return_value = engine

        with pytest.raises(AppError):
            await connect(PostgresSettings())

        engine.dispose.assert_awaited_once()


@pytest.mark.unit
class TestIsTimeout:
    def test_returns_true_when_cause_is_a_timeout_error(self):
        exc = _operational_error(cause=TimeoutError("expired"))

        assert _is_timeout(exc) is True

    def test_returns_true_for_asyncio_timeout_error_since_it_subclasses_timeout_error(
        self,
    ):
        exc = _operational_error(cause=TimeoutError("expired"))

        assert _is_timeout(exc) is True

    def test_returns_false_when_cause_is_unrelated(self):
        exc = _operational_error(cause=ConnectionRefusedError("refused"))

        assert _is_timeout(exc) is False

    def test_returns_false_when_there_is_no_cause_at_all(self):
        exc = OperationalError("SELECT 1", {}, Exception("boom"))

        assert _is_timeout(exc) is False

    def test_walks_multiple_levels_of_chained_causes(self):
        timeout = TimeoutError("expired")
        wrapper_one = Exception("layer one")
        wrapper_one.__cause__ = timeout
        wrapper_two = Exception("layer two")
        wrapper_two.__cause__ = wrapper_one
        exc = _operational_error(cause=wrapper_two)

        assert _is_timeout(exc) is True

    def test_does_not_loop_forever_on_a_short_non_timeout_chain(self):
        wrapper = Exception("no timeout anywhere")
        wrapper.__cause__ = None
        exc = _operational_error(cause=wrapper)

        assert _is_timeout(exc) is False


@pytest.mark.unit
class TestDisconnect:
    async def test_disposes_engine(self):
        engine = AsyncMock()
        connection = PostgresConnection(engine=engine, session_factory=MagicMock())

        await disconnect(connection)

        engine.dispose.assert_awaited_once()
