"""Declarative exception-to-response translation for the Trutina API.

register_exception_handlers(app) is the API's equivalent of
cli/shared/error_boundary.py -- the single place uncaught domain and
validation exceptions become a stable JSON response. The CLI needs an
imperative wrapper because Typer/Click has no built-in mechanism to
intercept exceptions from a command body; FastAPI already dispatches
uncaught exceptions to registered handlers for every route, so this
module is wired once, in composition (see api/composition/app.py),
rather than repeated per-router or per-handler.

Typing note
-----------
Starlette's `add_exception_handler(exc_class, handler)` requires every
registered handler to be callable as `(Request, Exception) -> Response`
-- that's the contract the *dispatcher* commits to, regardless of which
exception class the handler is registered under. Every handler below
is therefore typed against the base `Exception` and immediately
narrows with `assert isinstance(...)`. Starlette's exception middleware
looks up the handler by walking the *raised* exception's MRO against
the *registered* class, so e.g. `_handle_validation_app_error` is only
ever invoked when `exc` really is a `ValidationAppError`.

Domain-code recovery note
--------------------------
`get_field_violations()` (trutina.shared.errors.translators) currently
downgrades every domain-raised ErrorCode to `ErrorCode.UNKNOWN_ERROR` on
`FieldViolation.code` -- the real code survives only as a string on
`FieldViolation.value`. Left unhandled, every field-level validation
message here would read "An unexpected error occurred" instead of the
real domain message (e.g. "The account name is not valid."). This is
the same problem the CLI's own formatters/error.py must already work
around. `_resolve_violation_entry()` below restores the real code from
`.value` before doing the catalog lookup. If `get_field_violations()` is
ever fixed at the source, this function becomes a harmless no-op and can
be simplified, but it should not be removed silently -- confirm the
source fix first.

Serialization note
-------------------
Every response body is emitted via `.model_dump(mode="json")`, not the
bare `.model_dump()`, because `BaseResponse.timestamp` is a `datetime`
and Starlette's `JSONResponse` has no default encoder for non-JSON
types.

Exception Contract
-------------------
- ValidationAppError: 422 by default (per ERROR_CATALOG), `details`
    populated from ValidationAppError.errors (list[FieldViolation]).
- AppError (every other subclass, and the base class itself): status,
    message, and hint resolved from ERROR_CATALOG by `.code`, with
    `exc.context` interpolated into both templates.
- pydantic.ValidationError: raised when a mapper constructs a domain
    object or Input DTO directly from already-schema-valid request data
    and a domain validator rejects it. Uses the same recovery path as
    ValidationAppError.
- RequestValidationError: FastAPI's transport-level failure, raised
    before any router body runs. Never reached the domain layer, so it
    gets the non-domain error_code "request.invalid".
- Anything else: caught by a final catch-all `Exception` handler so no
    response ever escapes this app without the standard envelope shape.
    The real exception is never echoed into the response body.

Logging: not yet wired. Each handler below is the intended insertion
point (see the `# LOGGING:` comments) -- add it when ready, especially
on `_handle_app_error` (STORAGE_*/UNKNOWN_ERROR) and the catch-all.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
    get_field_violations,
)

from .catalog import DEFAULT_ERROR_ENTRY, ERROR_CATALOG, ErrorCatalogEntry
from .schemas import ErrorResponse, FieldErrorDetail, ValidationErrorResponse

# Location prefixes FastAPI/Starlette use for RequestValidationError
# entries, depending on where in the request the failing value came
# from. Stripped so a request-level field path (e.g. "query.page_size")
# reads the same shape as a domain field path (e.g. "lines.0.account"),
# rather than leaking transport-internal prefixes into the response.
_REQUEST_LOCATION_PREFIXES = {"body", "query", "path", "header"}

# Storage-related codes get a Retry-After header alongside the standard
# body, so well-behaved clients know exactly what to do instead of
# only reading "retry later" in prose.
_RETRYABLE_CODES = {ErrorCode.STORAGE_UNAVAILABLE, ErrorCode.STORAGE_TIMEOUT}
_RETRY_AFTER_SECONDS = "5"


def _fill(template: str, context: dict[str, str]) -> str:
    """Fill a required message template from AppError.context.

    Returns the template unchanged if it references a placeholder key
    missing from `context`, rather than raising -- a missing context
    key should degrade the text, not turn an otherwise-handled domain
    error into an unhandled 500.
    """
    try:
        return template.format(**context)
    except KeyError, IndexError:
        return template


def _fill_hint(template: str | None, context: dict[str, str]) -> str | None:
    """Fill an optional hint template, passing None through unchanged."""
    if template is None:
        return None
    return _fill(template, context)


def _resolve_violation_entry(violation: FieldViolation) -> ErrorCatalogEntry:
    """Resolve the catalog entry for one field violation.

    `violation.code` is `ErrorCode.UNKNOWN_ERROR` for every
    domain-raised violation (see module docstring), so a plain
    `ERROR_CATALOG.get(violation.code, ...)` lookup would return the
    generic entry for exactly the violations callers most need real
    text for. When the code was downgraded this way, the original
    ErrorCode string is still available on `violation.value` -- try to
    recover it first, and only fall back to the (already generic)
    `violation.code` lookup if that string doesn't round-trip into a
    real ErrorCode member.

    Args:
        violation: A single field-level violation from either a
            ValidationAppError or a translated pydantic.ValidationError.

    Returns:
        The most specific catalog entry available for this violation.
    """
    if violation.code is ErrorCode.UNKNOWN_ERROR:
        try:
            return ERROR_CATALOG.get(ErrorCode(violation.value), DEFAULT_ERROR_ENTRY)
        except ValueError:
            pass
    return ERROR_CATALOG.get(violation.code, DEFAULT_ERROR_ENTRY)


def _build_field_details(violations: list[FieldViolation]) -> list[FieldErrorDetail]:
    """Map domain FieldViolations to API-facing FieldErrorDetail entries.

    Shared by both handlers that translate FieldViolation lists
    (ValidationAppError and a mapper-stage pydantic.ValidationError) so
    the `.value`-recovery logic in `_resolve_violation_entry()` only
    has one call site to keep correct.

    Args:
        violations: Field violations produced by
            `get_field_violations()` or carried on a ValidationAppError.

    Returns:
        One FieldErrorDetail per violation, in the same order.
    """
    return [
        FieldErrorDetail(
            field=violation.field,
            code=violation.code.value,
            message=_resolve_violation_entry(violation).message,
        )
        for violation in violations
    ]


def _response_headers(code: ErrorCode) -> dict[str, str] | None:
    """Return extra headers to attach for a given ErrorCode, if any.

    Currently only used to attach `Retry-After` on storage failures.
    Returns None (no extra headers) for every other code.
    """
    if code in _RETRYABLE_CODES:
        return {"Retry-After": _RETRY_AFTER_SECONDS}
    return None


async def _handle_validation_app_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Translate a ValidationAppError into the shared validation envelope.

    Registered ahead of the plainer AppError handler below for
    readability only -- FastAPI dispatches by walking the raised
    exception's actual type through its MRO, not by registration order.
    """
    assert isinstance(exc, ValidationAppError)
    # LOGGING: log exc.code / exc.errors here once logging is wired.

    entry = ERROR_CATALOG.get(exc.code, DEFAULT_ERROR_ENTRY)

    body = ValidationErrorResponse(
        error_code=exc.code.value,
        message=entry.message,
        hint=entry.hint,
        details=_build_field_details(exc.errors),
    )
    return JSONResponse(
        status_code=entry.status_code, content=body.model_dump(mode="json")
    )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate any non-validation AppError into the shared envelope.

    Covers every AppError condition that carries a single failure
    reason rather than a list of field violations -- not-found lookups,
    conflicts, and storage failures. `exc.context` values (e.g.
    `identifier`, `value`) are interpolated into both the catalog
    message and hint templates.
    """
    assert isinstance(exc, AppError)
    # LOGGING: log exc.code / exc.cause here once logging is wired --
    # this is the branch that matters most (STORAGE_*, UNKNOWN_ERROR).

    entry = ERROR_CATALOG.get(exc.code, DEFAULT_ERROR_ENTRY)
    context = dict(exc.context)

    body = ErrorResponse(
        error_code=exc.code.value,
        message=_fill(entry.message, context),
        hint=_fill_hint(entry.hint, context),
    )
    return JSONResponse(
        status_code=entry.status_code,
        content=body.model_dump(mode="json"),
        headers=_response_headers(exc.code),
    )


async def _handle_pydantic_validation_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Translate a mapper-stage pydantic.ValidationError.

    Raised when a mapper builds a domain object or Input DTO directly
    from already-schema-valid request data and that construction fails
    a domain rule the Request schema itself has no way to check (e.g.
    INVALID_ACCOUNT_NAME). Reuses get_field_violations() -- the same
    translation ValidationAppError.validation() applies internally --
    so this handler's output is shape-identical to
    _handle_validation_app_error's.
    """
    assert isinstance(exc, PydanticValidationError)

    violations = get_field_violations(exc)
    entry = ERROR_CATALOG.get(ErrorCode.VALIDATION_ERROR, DEFAULT_ERROR_ENTRY)

    body = ValidationErrorResponse(
        error_code=ErrorCode.REQUEST_VALIDATION_ERROR.value,
        message=entry.message,
        hint=entry.hint,
        details=_build_field_details(violations),
    )
    return JSONResponse(
        status_code=entry.status_code, content=body.model_dump(mode="json")
    )


async def _handle_request_validation_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Translate FastAPI's own transport-level request validation failure.

    Raised before any router body runs, when the incoming JSON fails
    the Request Pydantic schema itself -- the failure never reaches the
    domain layer, so it is given the non-domain error_code
    "request.invalid" rather than any ErrorCode member. Strips whichever
    of "body"/"query"/"path"/"header" leads the location tuple, so a
    request-level field path reads the same shape as a domain field
    path instead of leaking the transport-internal prefix.
    """
    assert isinstance(exc, RequestValidationError)

    details = [
        FieldErrorDetail(
            field=".".join(
                str(part)
                for part in error["loc"]
                if str(part) not in _REQUEST_LOCATION_PREFIXES
            ),
            code=str(error["type"]),
            message=str(error["msg"]),
        )
        for error in exc.errors()
    ]

    entry = ERROR_CATALOG.get(ErrorCode.VALIDATION_ERROR, DEFAULT_ERROR_ENTRY)

    body = ValidationErrorResponse(
        error_code=ErrorCode.REQUEST_VALIDATION_ERROR.value,
        message=entry.message,
        hint=entry.hint,
        details=details,
    )

    return JSONResponse(
        status_code=entry.status_code,
        content=body.model_dump(mode="json"),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any exception outside the domain error contract.

    Without this, an unguarded KeyError/AttributeError/etc. anywhere
    below a route would fall through to Starlette's default handler,
    which returns a bare `{"detail": ...}` body -- breaking the
    BaseResponse envelope contract exactly when a client most needs a
    stable shape. The raw exception message is never included in the
    response; only DEFAULT_ERROR_ENTRY's generic text is returned.
    """
    # LOGGING: this is the most important place to log a full
    # stack trace once logging is wired -- this branch means something
    # genuinely unanticipated happened.

    body = ErrorResponse(
        error_code=ErrorCode.UNKNOWN_ERROR.value,
        message=DEFAULT_ERROR_ENTRY.message,
    )
    return JSONResponse(
        status_code=DEFAULT_ERROR_ENTRY.status_code,
        content=body.model_dump(mode="json"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register every domain/validation exception handler on `app`.

    Called exactly once from composition (see
    `api/composition/app.py::create_app()`), mirroring how
    cli/shared/error_boundary.py is wired into every CLI command --
    except here registration happens once for the whole app rather than
    once per command invocation.

    Registration order does not affect dispatch (Starlette resolves the
    handler by walking the *raised* exception's MRO against the
    *registered* class), but ValidationAppError is listed first here
    for readability since it is a subclass of AppError.

    Args:
        app: The FastAPI application to register handlers on. Must be
            called before the app starts serving requests; typically
            immediately after `FastAPI(...)` construction in
            `create_app()`.
    """
    app.add_exception_handler(ValidationAppError, _handle_validation_app_error)
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(
        PydanticValidationError, _handle_pydantic_validation_error
    )
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
