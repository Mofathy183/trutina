"""
Command-layer error boundary for the Trutina CLI.

Wraps a single service-layer call site (invoked via AppState.call())
and translates AppError / ValidationAppError into rendered Rich panels
plus a clean typer.Exit, so command.py bodies never handle exception
formatting or exit codes themselves.

This module is the only place that combines the pure error-formatting
functions in cli/shared/formatters/error.py with actual terminal output
(via cli/shared/ui/console) and the CLI's exit-code contract. It sits
above shared/errors/, shared/formatters/, and shared/ui/ rather than
inside any one of them, since it depends on all three.

Logging: this is also the single place a CLI command's failure is
logged -- the CLI's equivalent of the API's `_log_failure()` in
`api/shared/errors/handlers.py`. Exactly one "command.failed" line is
emitted per caught exception, so one failure never produces two log
entries. STORAGE_UNAVAILABLE, STORAGE_TIMEOUT, and UNKNOWN_ERROR log at
ERROR with a traceback attached, since those are the codes that should
page or be counted as incidents; every other, expected domain error
(validation, not found, conflict) logs at INFO. The correlation id
itself is never read or attached here directly -- it is picked up
automatically by the logging pipeline's own context-variable processor,
bound for the surrounding command by `main.py::run()` or
`shell/dispatch.py`.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic import ValidationError
from trutina.cli.shared.formatters.error import (
    build_error_panels,
    format_app_error,
    format_validation_app_error,
    format_validation_errors,
)
from trutina.cli.shared.ui import console
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError

logger = logging.getLogger(__name__)

# Codes that should page or be counted as incidents -- everything else
# is an expected domain outcome (bad input, not found, conflict) and
# logs at INFO instead.
_ERROR_LEVEL_CODES = {
    ErrorCode.STORAGE_UNAVAILABLE,
    ErrorCode.STORAGE_TIMEOUT,
    ErrorCode.UNKNOWN_ERROR,
}


def _log_failure(code: ErrorCode, *, cause: BaseException | None = None) -> None:
    """Log exactly one "command.failed" line for a caught command failure.

    Args:
        code: The ErrorCode identifying what failed.
        cause: The original exception to attach as a traceback, for
            codes in `_ERROR_LEVEL_CODES`. Ignored for every other
            code -- an expected domain error doesn't need a traceback
            attached to an INFO line.
    """
    is_incident = code in _ERROR_LEVEL_CODES
    logger.log(
        logging.ERROR if is_incident else logging.INFO,
        "command.failed",
        extra={"context": {"error_code": code.value}},
        exc_info=cause if is_incident else None,
    )


@contextmanager
def error_boundary() -> Iterator[None]:
    """Render service-layer errors as panels and exit(1) instead of propagating.

    Scopes exactly the one state.call(...) invocation that can raise
    AppError or ValidationAppError. ValidationAppError is caught first
    since it is a subclass of AppError, and is formatted through
    format_validation_app_error() so each FieldViolation renders as its
    own panel; a bare AppError renders as a single panel via
    format_app_error(). Both paths end in typer.Exit(code=1) so the
    command process exits cleanly rather than dumping a raw traceback.

    Usage:

        with error_boundary():
            account_vm = state.call(create_account_handler, state.context, dto)

    Raises:
        typer.Exit: Code 1, if the wrapped block raises AppError or
            ValidationAppError. The error has already been rendered to
            the console before this is raised.
    """
    try:
        yield
    except ValidationAppError as exc:
        _log_failure(exc.code)
        for p in build_error_panels(format_validation_app_error(exc)):
            console.print(p)
        raise typer.Exit(code=1) from None
    except AppError as exc:
        _log_failure(exc.code, cause=exc.cause)
        for p in build_error_panels([format_app_error(exc)]):
            console.print(p)
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        _log_failure(ErrorCode.VALIDATION_ERROR, cause=exc)
        for p in build_error_panels(format_validation_errors(exc)):
            console.print(p)
        raise typer.Exit(code=1) from None
