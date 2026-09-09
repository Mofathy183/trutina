import pytest
from pymongo.errors import (
    ConnectionFailure,
    DuplicateKeyError,
    ServerSelectionTimeoutError,
    WriteError,
)
from trutina.infrastructure.mongo.error_translation import (
    translate_mongo_errors,
    violated_index,
)
from trutina.shared.errors import AppError, ErrorCode


def _make_duplicate_key_error(
    key_pattern: dict[str, int] | None = None,
) -> DuplicateKeyError:
    details = (
        {
            "keyPattern": key_pattern,
            "keyValue": {},
            "errmsg": "E11000 duplicate key error",
            "code": 11000,
            "codeName": "DuplicateKey",
        }
        if key_pattern is not None
        else None
    )

    return DuplicateKeyError(
        "E11000 duplicate key error",
        details=details,
    )


@pytest.mark.unit
class TestViolatedIndex:
    def test_returns_first_field_from_key_pattern(self):
        exc = _make_duplicate_key_error(
            {"name_key": 1, "code": 1},
        )

        result = violated_index(exc)

        assert result == "name_key"

    def test_returns_none_when_key_pattern_is_empty(self):
        exc = _make_duplicate_key_error({})

        result = violated_index(exc)

        assert result is None

    def test_returns_none_when_details_are_missing(self):
        exc = _make_duplicate_key_error()

        result = violated_index(exc)

        assert result is None

    def test_returns_none_when_key_pattern_is_missing(self):
        exc = DuplicateKeyError(
            "E11000 duplicate key error",
            details={},
        )

        result = violated_index(exc)

        assert result is None


@pytest.mark.unit
class TestTranslateMongoErrors:
    async def test_raises_storage_timeout_when_server_selection_times_out(self):
        cause = ServerSelectionTimeoutError("timed out")

        with pytest.raises(AppError) as exc_info:
            async with translate_mongo_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.STORAGE_TIMEOUT
        assert exc_info.value.cause is cause

    async def test_raises_storage_unavailable_when_connection_fails(self):
        cause = ConnectionFailure("connection refused")

        with pytest.raises(AppError) as exc_info:
            async with translate_mongo_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE
        assert exc_info.value.cause is cause

    async def test_raises_unknown_error_when_pymongo_error_occurs(self):
        cause = WriteError("write failed")

        with pytest.raises(AppError) as exc_info:
            async with translate_mongo_errors():
                raise cause

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert exc_info.value.cause is cause

    async def test_propagates_non_mongo_exceptions_unchanged(self):
        cause = ValueError("not a mongo error")

        with pytest.raises(ValueError) as exc_info:
            async with translate_mongo_errors():
                raise cause

        assert exc_info.value is cause

    async def test_does_not_raise_when_no_exception_occurs(self):
        result = []

        async with translate_mongo_errors():
            result.append(1)

        assert result == [1]
