import pytest
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.shared.execution.error_translation import (
    translate_postgres_errors,
    violated_constraint,
)


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


class _FakeAsyncpgCause(Exception):
    """Mimics the original asyncpg.PostgresError asyncpg attaches via __cause__."""

    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("simulated asyncpg constraint violation")
        self.constraint_name = constraint_name


class _FakeOrigError(Exception):
    """Mimics SQLAlchemy's translated asyncpg wrapper — no constraint_name of its own."""

    def __init__(self) -> None:
        super().__init__("simulated postgres constraint violation")


@pytest.mark.unit
class TestViolatedConstraint:
    def test_returns_constraint_name_from_chained_cause(self):
        orig = _FakeOrigError()
        orig.__cause__ = _FakeAsyncpgCause("uq_accounts_code")
        exc = IntegrityError("stmt", {}, orig)
        assert violated_constraint(exc) == "uq_accounts_code"

    def test_returns_none_when_neither_orig_nor_cause_has_constraint_name(self):
        exc = IntegrityError("stmt", {}, _FakeOrigError())
        assert violated_constraint(exc) is None


@pytest.mark.unit
class TestTranslatePostgresErrors:
    async def test_propagates_integrity_error_unchanged(self):
        cause = IntegrityError(
            "simulated statement",
            {},
            _FakePostgresError("uq_accounts_code"),
        )

        with pytest.raises(type(cause)) as exc_info:
            async with translate_postgres_errors():
                raise cause

        assert exc_info.value is cause

    async def test_raises_storage_unavailable_when_operational_error_occurs(self):
        cause = OperationalError(
            "simulated statement",
            {},
            _FakePostgresError(),
        )

        with pytest.raises(AppError) as exc_info:
            async with translate_postgres_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE
        assert exc_info.value.cause is cause

    async def test_raises_storage_timeout_when_a_timeout_occurs(self):
        cause = TimeoutError("connection timed out")

        with pytest.raises(AppError) as exc_info:
            async with translate_postgres_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.STORAGE_TIMEOUT
        assert exc_info.value.cause is cause

    async def test_raises_unknown_error_for_other_sqlalchemy_errors(self):
        cause = SQLAlchemyError("some other failure")

        with pytest.raises(AppError) as exc_info:
            async with translate_postgres_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert exc_info.value.cause is cause

    async def test_propagates_non_sqlalchemy_exceptions_unchanged(self):
        cause = ValueError("not a sqlalchemy error")

        with pytest.raises(ValueError) as exc_info:
            async with translate_postgres_errors():
                raise cause

        assert exc_info.value is cause

    async def test_does_not_raise_when_no_exception_occurs(self):
        result = []

        async with translate_postgres_errors():
            result.append(1)

        assert result == [1]
