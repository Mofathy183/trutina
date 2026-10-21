import pytest
from pydantic import BaseModel, Field, ValidationError
from rich.panel import Panel
from trutina.cli.shared.errors import ERRORS, FIELD_LABELS, HINTS
from trutina.cli.shared.formatters import (
    FormattedError,
    build_error_panels,
    format_app_error,
    format_validation_app_error,
    format_validation_errors,
)
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
)


@pytest.mark.unit
class TestFormatValidationErrors:
    def test_formats_known_pydantic_error(self):
        class Model(BaseModel):
            name: str = Field(min_length=2)

        with pytest.raises(ValidationError) as exc_info:
            Model(name="A")

        formatted = format_validation_errors(exc_info.value)

        assert len(formatted) == 1

        error = formatted[0]

        assert error.field == "name"
        assert error.code == ErrorCode.STRING_TOO_SHORT
        assert error.message == ERRORS[ErrorCode.STRING_TOO_SHORT].message
        assert error.hint == HINTS[ErrorCode.STRING_TOO_SHORT]

    def test_formats_multiple_validation_errors_in_order(self):
        class Model(BaseModel):
            name: str = Field(min_length=2)
            age: int = Field(gt=0)

        with pytest.raises(ValidationError) as exc_info:
            Model(name="A", age=0)

        formatted = format_validation_errors(exc_info.value)

        assert len(formatted) == 2

        assert formatted[0].field == "name"
        assert formatted[0].code == ErrorCode.STRING_TOO_SHORT

        assert formatted[1].field == "age"
        assert formatted[1].code == ErrorCode.GREATER_THAN

    def test_falls_back_to_unknown_field_when_location_is_empty(self, monkeypatch):
        class Model(BaseModel):
            name: str = Field(min_length=2)

        with pytest.raises(ValidationError) as exc_info:
            Model(name="A")

        errors = exc_info.value.errors()
        errors[0]["loc"] = ()

        monkeypatch.setattr(exc_info.value, "errors", lambda: errors)

        formatted = format_validation_errors(exc_info.value)

        assert formatted[0].field == "unknown"

    def test_falls_back_to_unknown_error_when_error_type_is_unknown(self, monkeypatch):
        class Model(BaseModel):
            name: str = Field(min_length=2)

        with pytest.raises(ValidationError) as exc_info:
            Model(name="A")

        errors = exc_info.value.errors()
        errors[0]["type"] = "completely_unknown"

        monkeypatch.setattr(exc_info.value, "errors", lambda: errors)

        formatted = format_validation_errors(exc_info.value)

        assert formatted[0].code == ErrorCode.UNKNOWN_ERROR
        assert formatted[0].message == ERRORS[ErrorCode.UNKNOWN_ERROR].message
        assert formatted[0].hint == HINTS[ErrorCode.UNKNOWN_ERROR]


@pytest.mark.unit
class TestFormatAppError:
    def test_formats_not_found_error(self):
        error = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT,
            resource="account",
            identifier="9999",
        )

        formatted = format_app_error(error)

        assert formatted.field == FIELD_LABELS[ErrorCode.UNKNOWN_ACCOUNT]
        assert formatted.code == ErrorCode.UNKNOWN_ACCOUNT
        assert formatted.message == ERRORS[ErrorCode.UNKNOWN_ACCOUNT].message
        assert formatted.hint == HINTS[ErrorCode.UNKNOWN_ACCOUNT]

    def test_prefers_field_from_context(self):
        error = AppError.conflict(
            code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
            resource="account",
            field_name="code",
            value="1001",
        )

        formatted = format_app_error(error)

        assert formatted.field == "code"

    def test_falls_back_to_unknown_catalog_entry(self):
        error = AppError.unknown()

        formatted = format_app_error(error)

        assert formatted.code == ErrorCode.UNKNOWN_ERROR
        assert formatted.message == ERRORS[ErrorCode.UNKNOWN_ERROR].message
        assert formatted.hint == HINTS[ErrorCode.UNKNOWN_ERROR]

    def test_invalid_credentials_names_no_single_field(self):
        error = AppError(code=ErrorCode.AUTH_INVALID_CREDENTIALS)

        formatted = format_app_error(error)

        assert formatted.field == FIELD_LABELS[ErrorCode.AUTH_INVALID_CREDENTIALS]
        assert formatted.field not in {"email", "password"}
        assert formatted.message == ERRORS[ErrorCode.AUTH_INVALID_CREDENTIALS].message
        assert formatted.hint == HINTS[ErrorCode.AUTH_INVALID_CREDENTIALS]

    def test_throttled_renders_catalog_text_and_ignores_retry_context(self):
        error = AppError(
            code=ErrorCode.AUTH_THROTTLED, context={"retry_after_seconds": "42"}
        )

        formatted = format_app_error(error)

        assert formatted.field == "unknown"
        assert formatted.message == ERRORS[ErrorCode.AUTH_THROTTLED].message
        assert "42" not in formatted.message + formatted.hint


@pytest.mark.unit
class TestFormatValidationAppError:
    def test_formats_validation_app_error(self):
        error = ValidationAppError(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[
                FieldViolation(
                    field="name",
                    code=ErrorCode.STRING_TOO_SHORT,
                    value="A",
                )
            ],
        )

        formatted = format_validation_app_error(error)

        assert len(formatted) == 1

        violation = formatted[0]

        assert violation.field == "name"
        assert violation.code == ErrorCode.STRING_TOO_SHORT
        assert violation.message == ERRORS[ErrorCode.STRING_TOO_SHORT].message
        assert violation.hint == HINTS[ErrorCode.STRING_TOO_SHORT]

    def test_restores_domain_error_code_from_violation_value(self):
        error = ValidationAppError(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[
                FieldViolation(
                    field="name",
                    code=ErrorCode.UNKNOWN_ERROR,
                    value=ErrorCode.INVALID_ACCOUNT_NAME,
                )
            ],
        )

        formatted = format_validation_app_error(error)

        assert len(formatted) == 1

        violation = formatted[0]

        assert violation.field == "name"
        assert violation.code == ErrorCode.INVALID_ACCOUNT_NAME
        assert violation.message == ERRORS[ErrorCode.INVALID_ACCOUNT_NAME].message
        assert violation.hint == HINTS[ErrorCode.INVALID_ACCOUNT_NAME]

    def test_falls_back_to_unknown_error_when_value_is_not_known_error_code(self):
        error = ValidationAppError(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[
                FieldViolation(
                    field="name",
                    code=ErrorCode.UNKNOWN_ERROR,
                    value="not.a.real.error.code",
                )
            ],
        )

        formatted = format_validation_app_error(error)

        assert len(formatted) == 1

        violation = formatted[0]

        assert violation.code == ErrorCode.UNKNOWN_ERROR
        assert violation.message == ERRORS[ErrorCode.UNKNOWN_ERROR].message
        assert violation.hint == HINTS[ErrorCode.UNKNOWN_ERROR]

    def test_formats_multiple_field_violations_in_order(self):
        error = ValidationAppError(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[
                FieldViolation(
                    field="name",
                    code=ErrorCode.STRING_TOO_SHORT,
                    value="A",
                ),
                FieldViolation(
                    field="category",
                    code=ErrorCode.UNKNOWN_ERROR,
                    value=ErrorCode.INVALID_ACCOUNT_NAME,
                ),
            ],
        )

        formatted = format_validation_app_error(error)

        assert len(formatted) == 2

        assert formatted[0].field == "name"
        assert formatted[0].code == ErrorCode.STRING_TOO_SHORT

        assert formatted[1].field == "category"
        assert formatted[1].code == ErrorCode.INVALID_ACCOUNT_NAME


@pytest.mark.unit
class TestBuildErrorPanels:
    def test_returns_one_panel_per_formatted_error(self):
        errors = [
            FormattedError(
                field="name",
                message="Name is invalid.",
                code="account.invalid_name",
                hint="Use only letters and spaces.",
            ),
            FormattedError(
                field="code",
                message="Code already exists.",
                code="account.duplicate_code",
                hint="Choose another code.",
            ),
        ]

        panels = build_error_panels(errors)

        assert len(panels) == 2
        assert all(isinstance(panel, Panel) for panel in panels)

    def test_returns_empty_list_when_no_errors_are_given(self):
        assert build_error_panels([]) == []

    def test_panel_contains_formatted_error_content(self):
        error = FormattedError(
            field="name",
            message="Invalid name.",
            code="account.invalid_name",
            hint="Use letters only.",
        )

        panel = build_error_panels([error])[0]

        assert isinstance(panel, Panel)
        assert panel.title == "Validation Error"
