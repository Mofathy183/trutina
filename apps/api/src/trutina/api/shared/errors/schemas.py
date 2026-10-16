"""Response envelope schemas for the Trutina API.

BaseResponse defines the two fields every JSON body carries regardless
of outcome -- `success` and `timestamp` -- so the success envelopes each
feature's presenter.py builds from a ViewModel (e.g.
AccountResponse(BaseResponse)) and the error envelopes this module's
exception handlers build share one consistent top-level shape. This
module owns only the error side: ErrorResponse and
ValidationErrorResponse.

ValidationErrorResponse extends ErrorResponse rather than `details`
living on the base -- a plain not-found or conflict has nothing
field-level to report, so it never carries a `details` array at all,
instead of carrying one that's always None.
"""

from typing import Literal

from pydantic import BaseModel, Field
from trutina.api.shared.response import BaseResponse


class FieldErrorDetail(BaseModel):
    """One field-level validation failure within a ValidationErrorResponse.

    Mirrors the shape of FieldViolation
    (trutina.shared.errors.errors.FieldViolation) but is a distinct
    type: FieldViolation is a domain contract shared across services and
    the CLI, while this is the API's own JSON-serializable presentation
    of it. Keeping them separate means a future change to
    FieldViolation's internal shape doesn't automatically change the
    API's public response contract.

    Attributes:
        field: Dotted field path, e.g. "lines.0.account".
        code: Stable machine-readable code for this violation -- the real
            ErrorCode value for domain-raised violations (recovered from
            the downgraded violation, see handlers.py), or a raw
            Pydantic/FastAPI error type string for transport-level
            violations that never reached the domain layer.
        message: Human-readable description of this specific violation.
        hint: Optional resolution guidance for this specific violation,
            taken from the API error catalog. None when the catalog has
            no hint for the violation's code, and for transport-level
            violations that never reached the domain layer.
    """

    field: str
    code: str
    message: str
    hint: str | None = None


class ErrorResponse(BaseResponse):
    """The base error envelope, returned for every non-validation failure.

    Covers every AppError condition carrying a single failure reason
    rather than a list of field violations -- not-found lookups,
    conflicts, and storage failures. ValidationErrorResponse extends
    this with a `details` array for the validation case; plain
    ErrorResponse instances never carry one.

    Attributes:
        error_code: Stable, machine-readable identifier -- an ErrorCode
            value (e.g. "account.unknown") for domain failures, or
            "request.invalid" for a failure that never reached the
            domain layer. Callers should branch on this, never on
            `message` text, which may be reworded over time.
        message: Human-readable summary of the failure.
        hint: Optional resolution guidance -- what the caller should try
            next. None when the message is already self-explanatory.
    """

    success: Literal[False] = False
    error_code: str
    message: str
    hint: str | None = None


class ValidationErrorResponse(ErrorResponse):
    """Error envelope for failures carrying per-field validation detail.

    Used for ValidationAppError, a mapper-stage
    pydantic.ValidationError, and FastAPI's own RequestValidationError
    -- the three failure modes where more than one field may have
    failed at once.

    Attributes:
        details: One entry per failed field. Always a list (defaults to
            empty), never None -- distinguishing "no field errors" from
            "field errors not applicable" the way ErrorResponse (which
            has no `details` field at all) does for non-validation
            failures.
    """

    details: list[FieldErrorDetail] = Field(default_factory=list)
