import pytest
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
)


@pytest.mark.unit
class TestAppError:
    def test_makes_context_read_only(self):
        error = AppError(
            code=ErrorCode.UNKNOWN_ACCOUNT,
            context={"identifier": "1000"},
        )

        with pytest.raises(TypeError):
            error.context["identifier"] = "2000"  # ty:ignore[invalid-assignment]

    def test_copies_context_mapping(self):
        context = {"identifier": "1000"}

        error = AppError(
            code=ErrorCode.UNKNOWN_ACCOUNT,
            context=context,
        )

        context["identifier"] = "2000"

        assert error.context["identifier"] == "1000"

    def test_converts_context_to_read_only_mapping(self):
        error = AppError(
            code=ErrorCode.UNKNOWN_ACCOUNT,
            context={"identifier": "1000"},
        )

        with pytest.raises(TypeError):
            error.context["identifier"] = "2000"  # ty:ignore[invalid-assignment]

    def test_not_found_creates_expected_context(self):
        error = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT,
            resource="account",
            identifier="1000",
        )

        assert error.code == ErrorCode.UNKNOWN_ACCOUNT
        assert error.context == {
            "resource": "account",
            "identifier": "1000",
        }

    def test_conflict_creates_expected_context(self):
        error = AppError.conflict(
            code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
            resource="account",
            field_name="code",
            value="1000",
        )

        assert error.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
        assert error.context == {
            "resource": "account",
            "field": "code",
            "value": "1000",
        }

    def test_unknown_returns_unknown_error(self):
        error = AppError.unknown()

        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert error.cause is None

    def test_unknown_preserves_cause(self):
        cause = ValueError("boom")

        error = AppError.unknown(cause)

        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert error.cause is cause

    def test_storage_unavailable_returns_storage_unavailable_error(self):
        error = AppError.storage_unavailable()

        assert error.code == ErrorCode.STORAGE_UNAVAILABLE
        assert error.cause is None

    def test_storage_unavailable_preserves_cause(self):
        cause = ConnectionError("connection failed")

        error = AppError.storage_unavailable(cause)

        assert error.code == ErrorCode.STORAGE_UNAVAILABLE
        assert error.cause is cause

    def test_storage_timeout_returns_storage_timeout_error(self):
        error = AppError.storage_timeout()

        assert error.code == ErrorCode.STORAGE_TIMEOUT
        assert error.context == {}
        assert error.cause is None

    def test_storage_timeout_preserves_cause(self):
        cause = TimeoutError("timed out")

        error = AppError.storage_timeout(cause)

        assert error.code == ErrorCode.STORAGE_TIMEOUT
        assert error.cause is cause


@pytest.mark.unit
class TestValidationAppError:
    def test_accepts_field_violations(self):
        violation = FieldViolation(
            code=ErrorCode.REQUIRED_FIELD,
            field="name",
            value="",
        )

        error = ValidationAppError(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[violation],
        )

        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.errors == [violation]

    def test_validation_translates_pydantic_errors(self, monkeypatch):
        translated = [
            FieldViolation(
                code=ErrorCode.UNKNOWN_ERROR,
                field="name",
                value="account.invalid_name",
            )
        ]

        called = False

        def fake_get_field_violations(exc):
            nonlocal called
            called = True
            return translated

        monkeypatch.setattr(
            "trutina.shared.errors.translators.get_field_violations",
            fake_get_field_violations,
        )

        exc = object()

        error = ValidationAppError.validation(exc)  # ty:ignore[invalid-argument-type]

        assert called is True
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.errors == translated

    def test_required_field_builds_one_required_field_violation(self):
        error = ValidationAppError.required_field("actor", "   ")

        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.errors == [
            FieldViolation(code=ErrorCode.REQUIRED_FIELD, field="actor", value="   ")
        ]

    def test_required_field_does_not_downgrade_to_unknown_error(self):
        error = ValidationAppError.required_field("actor", "")

        assert [v.code for v in error.errors] == [ErrorCode.REQUIRED_FIELD]
        assert ErrorCode.UNKNOWN_ERROR not in {v.code for v in error.errors}
