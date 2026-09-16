import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.shared.execution.executor import PostgresExecutor


class _FakePostgresError(Exception):
    """Stands in for an asyncpg PostgresError.

    Real asyncpg exceptions (UniqueViolationError, etc.) populate
    constraint_name from Postgres's own error response fields. This fake
    carries just that one attribute, since it's the only thing
    violated_constraint() reads.
    """

    def __init__(self, constraint_name: str | None = None) -> None:
        super().__init__("simulated postgres error")
        self.constraint_name = constraint_name


@pytest.mark.unit
class TestPostgresExecutor:
    async def test_returns_coroutine_result(self):
        async def coro():
            return 42

        executor = PostgresExecutor()

        result = await executor.run(coro())

        assert result == 42

    async def test_translates_postgres_errors(self):
        executor = PostgresExecutor()
        cause = OperationalError(
            "simulated statement",
            {},
            _FakePostgresError(),
        )

        async def coro():
            raise cause

        with pytest.raises(AppError) as exc_info:
            await executor.run(coro())

        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE
        assert exc_info.value.cause is cause

    async def test_propagates_integrity_error_unchanged(self):
        executor = PostgresExecutor()
        cause = IntegrityError(
            "simulated statement",
            {},
            _FakePostgresError("uq_accounts_code"),
        )

        async def coro():
            raise cause

        with pytest.raises(type(cause)) as exc_info:
            await executor.run(coro())

        assert exc_info.value is cause
