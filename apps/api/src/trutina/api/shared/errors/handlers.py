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

Logging
-------
Every handler below calls `_log_failure()` exactly once, so one raised
exception produces exactly one log line regardless of which handler
catches it. Status codes under 500 (validation, not-found, conflict)
log at INFO -- they're expected outcomes, not incidents. 500 and above
log at ERROR with `exc_info` attached, so STORAGE_* / UNKNOWN_ERROR
failures get a full traceback.

Correlation id
--------------
CorrelationIdMiddleware stores the id at scope["state"]["correlation_id"],
which Starlette exposes as `request.state.correlation_id`. Handlers read
it from there, never from a context variable: Starlette runs the
catch-all `Exception` handler *outside* user middleware, after the
middleware's `correlation_scope()` has already reset the context
variable, so a context-variable read (including the logging pipeline's
own automatic one) would silently lose the id on exactly the 500s that
matter most. `_log_failure()` therefore passes the id as an explicit
top-level `extra` key, and the catch-all handler echoes it back as an
`X-Request-ID` response header itself, because its response never
passes through the middleware's send wrapper. Every other handler
runs inside the middleware, which adds the header for them.
"""

import logging

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

logger = logging.getLogger(__name__)

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

# Status at or above which a translated failure is an incident (ERROR
# with traceback) rather than an expected outcome (INFO).
_ERROR_LOG_THRESHOLD = 500

_REQUEST_ID_HEADER = "X-Request-ID"


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


def _correlation_id(request: Request) -> str | None:
    """Read the correlation id CorrelationIdMiddleware stored on this request.

    The middleware writes to scope["state"]["correlation_id"], which
    Starlette's Request.state exposes as an attribute.

    Returns None if the middleware wasn't installed (e.g. a bare
    Request built in a unit test without going through create_app()).
    """
    return getattr(request.state, "correlation_id", None)


def _log_failure(
    request: Request,
    exc: Exception,
    *,
    status_code: int,
    error_code: str,
    log_exc_info: bool = False,
) -> None:
    """Log exactly one line for a request that ended in a translated error.

    Called once per handler, after the response body is built, so the
    log line's error_code/status_code always match what the client
    actually received.

    The correlation id is passed as a top-level `extra` key (not inside
    `context`) so it lands in the same place as on every other record;
    see the module docstring for why the logging pipeline's own
    context-variable lookup cannot be relied on here.
    """
    extra: dict[str, object] = {
        "error_code": error_code,
        "context": {
            "http_status": status_code,
            "route": request.url.path,
        },
    }
    correlation_id = _correlation_id(request)
    if correlation_id is not None:
        extra["correlation_id"] = correlation_id

    level = logging.ERROR if status_code >= _ERROR_LOG_THRESHOLD else logging.INFO
    logger.log(
        level,
        "request.failed",
        extra=extra,
        exc_info=exc if log_exc_info else None,
    )


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

    entry = ERROR_CATALOG.get(exc.code, DEFAULT_ERROR_ENTRY)

    body = ValidationErrorResponse(
        error_code=exc.code.value,
        message=entry.message,
        hint=entry.hint,
        details=_build_field_details(exc.errors),
    )

    _log_failure(request, exc, status_code=entry.status_code, error_code=exc.code.value)

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

    entry = ERROR_CATALOG.get(exc.code, DEFAULT_ERROR_ENTRY)
    context = dict(exc.context)

    body = ErrorResponse(
        error_code=exc.code.value,
        message=_fill(entry.message, context),
        hint=_fill_hint(entry.hint, context),
    )

    _log_failure(
        request,
        exc,
        status_code=entry.status_code,
        error_code=exc.code.value,
        log_exc_info=entry.status_code >= _ERROR_LOG_THRESHOLD,
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

    _log_failure(
        request,
        exc,
        status_code=entry.status_code,
        error_code=ErrorCode.REQUEST_VALIDATION_ERROR.value,
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

    _log_failure(
        request,
        exc,
        status_code=entry.status_code,
        error_code=ErrorCode.REQUEST_VALIDATION_ERROR.value,
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

    Unlike every other handler, this one runs outside
    CorrelationIdMiddleware, so its response never passes through the
    middleware's send wrapper. The X-Request-ID header is therefore
    attached here, from the id the middleware stored on the request --
    a client reporting a 500 is exactly the caller who needs it.
    """
    body = ErrorResponse(
        error_code=ErrorCode.UNKNOWN_ERROR.value,
        message=DEFAULT_ERROR_ENTRY.message,
    )

    _log_failure(
        request,
        exc,
        status_code=DEFAULT_ERROR_ENTRY.status_code,
        error_code=ErrorCode.UNKNOWN_ERROR.value,
        log_exc_info=True,
    )

    correlation_id = _correlation_id(request)
    headers = {_REQUEST_ID_HEADER: correlation_id} if correlation_id else None

    return JSONResponse(
        status_code=DEFAULT_ERROR_ENTRY.status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
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
