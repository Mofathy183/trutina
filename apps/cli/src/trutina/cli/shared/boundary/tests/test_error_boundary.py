import importlib
from unittest.mock import MagicMock

import pytest
import typer
from pydantic import BaseModel, Field, ValidationError
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
)

error_boundary_module = importlib.import_module(
    "trutina.cli.shared.boundary.error_boundary"
)
from trutina.cli.shared.boundary.error_boundary import error_boundary  # noqa: E402


class _DummyModel(BaseModel):
    """Minimal model used only to produce a real pydantic.ValidationError,
    independent of any domain schema — keeps this file decoupled from
    account/journal/posting DTOs.
    """

    value: str = Field(min_length=5)


def _raw_validation_error() -> ValidationError:
    try:
        _DummyModel(value="ab")
    except ValidationError as exc:
        return exc
    raise AssertionError("Expected ValidationError was not raised")


def _app_error() -> AppError:
    return AppError.not_found(
        code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
    )


def _validation_app_error() -> ValidationAppError:
    return ValidationAppError(
        code=ErrorCode.VALIDATION_ERROR,
        errors=[
            FieldViolation(code=ErrorCode.UNKNOWN_ERROR, field="name", value="???"),
        ],
    )


@pytest.mark.unit
class TestErrorBoundarySuccessPath:
    def test_yields_without_raising_when_block_succeeds(self):
        with error_boundary():
            result = 1 + 1

        assert result == 2

    def test_does_not_print_anything_on_success(self, monkeypatch):
        printed = MagicMock()
        monkeypatch.setattr(error_boundary_module.console, "print", printed)

        with error_boundary():
            pass

        printed.assert_not_called()


@pytest.mark.unit
class TestErrorBoundaryValidationAppError:
    def test_exits_with_code_one(self, monkeypatch):
        monkeypatch.setattr(
            error_boundary_module, "format_validation_app_error", lambda exc: []
        )
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with pytest.raises(typer.Exit) as exc_info:
            with error_boundary():
                raise _validation_app_error()

        assert exc_info.value.exit_code == 1

    def test_routes_through_format_validation_app_error_not_format_app_error(
        self, monkeypatch
    ):
        format_validation_app_error = MagicMock(return_value=["formatted"])
        format_app_error = MagicMock()
        monkeypatch.setattr(
            error_boundary_module,
            "format_validation_app_error",
            format_validation_app_error,
        )
        monkeypatch.setattr(error_boundary_module, "format_app_error", format_app_error)
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        exc = _validation_app_error()
        with pytest.raises(typer.Exit):
            with error_boundary():
                raise exc

        format_validation_app_error.assert_called_once_with(exc)
        format_app_error.assert_not_called()

    def test_builds_and_prints_one_panel_per_field_violation(self, monkeypatch):
        formatted = ["violation_one", "violation_two"]
        panels = ["panel_one", "panel_two"]
        monkeypatch.setattr(
            error_boundary_module, "format_validation_app_error", lambda exc: formatted
        )
        build_error_panels = MagicMock(return_value=panels)
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", build_error_panels
        )
        printed = MagicMock()
        monkeypatch.setattr(error_boundary_module.console, "print", printed)

        with pytest.raises(typer.Exit):
            with error_boundary():
                raise _validation_app_error()

        build_error_panels.assert_called_once_with(formatted)
        assert printed.call_args_list == [((panels[0],),), ((panels[1],),)]

    def test_exit_suppresses_original_traceback_chain(self, monkeypatch):
        monkeypatch.setattr(
            error_boundary_module, "format_validation_app_error", lambda exc: []
        )
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with pytest.raises(typer.Exit) as exc_info:
            with error_boundary():
                raise _validation_app_error()

        assert exc_info.value.__cause__ is None


@pytest.mark.unit
class TestErrorBoundaryAppError:
    def test_exits_with_code_one(self, monkeypatch):
        monkeypatch.setattr(error_boundary_module, "format_app_error", lambda exc: "x")
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with pytest.raises(typer.Exit) as exc_info:
            with error_boundary():
                raise _app_error()

        assert exc_info.value.exit_code == 1

    def test_calls_format_app_error_with_the_raised_error(self, monkeypatch):
        format_app_error = MagicMock(return_value="formatted")
        monkeypatch.setattr(error_boundary_module, "format_app_error", format_app_error)
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        exc = _app_error()
        with pytest.raises(typer.Exit):
            with error_boundary():
                raise exc

        format_app_error.assert_called_once_with(exc)

    def test_wraps_the_single_formatted_error_in_a_list_for_build_error_panels(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            error_boundary_module, "format_app_error", lambda exc: "formatted"
        )
        build_error_panels = MagicMock(return_value=["panel"])
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", build_error_panels
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with pytest.raises(typer.Exit):
            with error_boundary():
                raise _app_error()

        build_error_panels.assert_called_once_with(["formatted"])

    def test_prints_the_built_panel(self, monkeypatch):
        monkeypatch.setattr(error_boundary_module, "format_app_error", lambda exc: "x")
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: ["panel"]
        )
        printed = MagicMock()
        monkeypatch.setattr(error_boundary_module.console, "print", printed)

        with pytest.raises(typer.Exit):
            with error_boundary():
                raise _app_error()

        printed.assert_called_once_with("panel")


@pytest.mark.unit
class TestErrorBoundaryRawPydanticValidationError:
    def test_exits_with_code_one(self, monkeypatch):
        monkeypatch.setattr(
            error_boundary_module, "format_validation_errors", lambda exc: []
        )
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with pytest.raises(typer.Exit) as exc_info:
            with error_boundary():
                raise _raw_validation_error()

        assert exc_info.value.exit_code == 1

    def test_routes_through_format_validation_errors(self, monkeypatch):
        format_validation_errors = MagicMock(return_value=["formatted"])
        monkeypatch.setattr(
            error_boundary_module, "format_validation_errors", format_validation_errors
        )
        monkeypatch.setattr(
            error_boundary_module, "build_error_panels", lambda errs: []
        )
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        exc = _raw_validation_error()
        with pytest.raises(typer.Exit):
            with error_boundary():
                raise exc

        format_validation_errors.assert_called_once_with(exc)


@pytest.mark.unit
class TestErrorBoundaryUnrelatedExceptions:
    def test_propagates_exceptions_outside_its_contract_unchanged(self):
        with pytest.raises(KeyError):
            with error_boundary():
                raise KeyError("not an AppError")

    def test_does_not_print_anything_for_an_unrelated_exception(self, monkeypatch):
        printed = MagicMock()
        monkeypatch.setattr(error_boundary_module.console, "print", printed)

        with pytest.raises(KeyError):
            with error_boundary():
                raise KeyError("boom")

        printed.assert_not_called()


@pytest.mark.unit
class TestErrorBoundaryAuthFailureLogging:
    @pytest.mark.parametrize(
        "code", [ErrorCode.AUTH_INVALID_CREDENTIALS, ErrorCode.AUTH_THROTTLED]
    )
    def test_logs_one_info_line_not_an_incident(self, code, monkeypatch, caplog):
        monkeypatch.setattr(error_boundary_module.console, "print", MagicMock())

        with caplog.at_level("INFO"):
            with pytest.raises(typer.Exit):
                with error_boundary():
                    raise AppError(code=code)

        records = [r for r in caplog.records if r.message == "command.failed"]
        assert len(records) == 1
        assert records[0].levelname == "INFO"
