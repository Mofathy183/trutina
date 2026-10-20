"""A rejected credential never reaches CLI output, FormattedError or logs."""

import logging

import pytest
import typer
from pydantic import ValidationError
from trutina.cli.shared.boundary.error_boundary import error_boundary
from trutina.cli.shared.formatters import (
    build_error_panels,
    format_validation_app_error,
    format_validation_errors,
)
from trutina.cli.shared.ui import console
from trutina.shared.errors import ValidationAppError

from tests.factories.secret import (
    SECRET_SENTINEL,
    SecretProbe,
    make_secret_probe_payload,
)


def _validation_error() -> ValidationError:
    try:
        SecretProbe.model_validate(make_secret_probe_payload())
    except ValidationError as exc:
        return exc
    raise AssertionError("Expected ValidationError was not raised")


def _render(panels) -> str:
    with console.capture() as capture:
        for panel in panels:
            console.print(panel)
    return capture.get()


@pytest.mark.unit
class TestFormattersNeverCarryCredentials:
    def test_raw_validation_error_panels_omit_the_sentinel(self):
        formatted = format_validation_errors(_validation_error())

        assert SECRET_SENTINEL not in _render(build_error_panels(formatted))
        assert SECRET_SENTINEL not in repr(formatted)

    def test_validation_app_error_panels_omit_the_sentinel(self):
        exc = ValidationAppError.validation(_validation_error())

        formatted = format_validation_app_error(exc)

        assert SECRET_SENTINEL not in _render(build_error_panels(formatted))
        assert SECRET_SENTINEL not in repr(exc)

    def test_panels_still_name_the_failed_fields(self):
        formatted = format_validation_errors(_validation_error())

        assert {f.field for f in formatted} >= {"email", "new_password"}

    def test_probe_validation_error_text_hides_input(self):
        assert SECRET_SENTINEL not in str(_validation_error())


@pytest.mark.unit
class TestErrorBoundaryNeverLeaksCredentials:
    @pytest.mark.parametrize("via_service", [False, True])
    def test_output_and_logs_omit_the_sentinel(self, caplog, via_service):
        with caplog.at_level(logging.DEBUG), console.capture() as capture:
            with pytest.raises(typer.Exit):
                with error_boundary():
                    try:
                        SecretProbe.model_validate(make_secret_probe_payload())
                    except ValidationError as exc:
                        if not via_service:
                            raise
                        raise ValidationAppError.validation(exc) from exc

        assert SECRET_SENTINEL not in capture.get()
        assert caplog.records
        for record in caplog.records:
            assert SECRET_SENTINEL not in record.getMessage()
            assert SECRET_SENTINEL not in str(record.__dict__)
