"""
Translation utilities between Pydantic validation errors and Trutina's
domain error model.

Provides helpers that allow domain validators to raise ErrorCode-backed
validation failures while ensuring callers ultimately receive stable
FieldViolation records rather than framework-specific exceptions.

Depended on by shared/errors/errors.py and domain schemas throughout
the application. This module isolates Pydantic-specific behavior from
the rest of the error architecture.

Credential safety: FieldViolation.value never carries a credential.
The Pydantic input is rendered through trutina.shared.secret, which
masks it when the error's location is credential-shaped and masks
credential-keyed entries when the input is a container (Pydantic
reports the whole parent object as the input of a `missing` error).
"""

from pydantic import ValidationError as PydanticValidationError
from pydantic_core import PydanticCustomError
from trutina.shared.secret import safe_input_text

from .codes import ErrorCode
from .errors import FieldViolation


def pydantic_error(code: ErrorCode) -> PydanticCustomError:
    """Construct a Pydantic-compatible domain validation error.

    Wraps a domain error code in a PydanticCustomError so validators
    can raise it directly. The error message is intentionally empty
    because user-facing messages are resolved from ERRORS at the
    presentation layer rather than embedded in the exception. The empty
    message also means a validator that uses this helper cannot echo
    the rejected value into the error text.

    Args:
        code: The domain error code identifying the validation failure.

    Returns:
        A PydanticCustomError whose type is the supplied ErrorCode value.
        The generic translator preserves that value in FieldViolation.value
        when it is not one of the Pydantic-native types in PYDANTIC_CODES.
    """
    # noinspection PyTypeChecker
    return PydanticCustomError(code.value, "")


# Pydantic-native validation types that intentionally map directly to
# equivalent ErrorCode values. These codes are preserved during
# translation rather than collapsed into UNKNOWN_ERROR.
PYDANTIC_CODES: frozenset[str] = frozenset(
    {
        ErrorCode.REQUIRED_FIELD,
        ErrorCode.INVALID_NUMBER,
        ErrorCode.INVALID_DECIMAL,
        ErrorCode.STRING_TYPE,
        ErrorCode.STRING_TOO_SHORT,
        ErrorCode.STRING_TOO_LONG,
        ErrorCode.TOO_SHORT,
        ErrorCode.TOO_LONG,
        ErrorCode.GREATER_THAN,
        ErrorCode.GREATER_THAN_EQUAL,
        ErrorCode.LESS_THAN_EQUAL,
    }
)


def get_field_violations(exc: PydanticValidationError) -> list[FieldViolation]:
    """Translate framework validation failures into domain error records.

    Converts a Pydantic ValidationError into the stable FieldViolation
    structure used throughout Trutina's error architecture. This isolates
    Pydantic-specific error formats from adapters and service-layer code,
    allowing the rest of the application to work exclusively with
    ErrorCode values and FieldViolation records.

    Pydantic-native error types listed in PYDANTIC_CODES are mapped directly
    to equivalent ErrorCode values, with the rejected input stringified
    into `value` through `safe_input_text` so a credential is never
    carried (it is masked, not omitted: the violation still names the
    field and the rule). All other types are downgraded to
    UNKNOWN_ERROR rather than exposing framework-specific failures outside
    the translation layer; their raw Pydantic type is retained in value,
    which is a code string and never user input.

    Args:
        exc: The Pydantic ValidationError raised by a domain schema.

    Returns:
        FieldViolation records in the order Pydantic reports them.
    """
    violations: list[FieldViolation] = []

    for e in exc.errors():
        raw_type = e["type"]

        if raw_type in PYDANTIC_CODES:
            code = ErrorCode(raw_type)
            value = safe_input_text(e["loc"], e.get("input", ""))
        else:
            code = ErrorCode.UNKNOWN_ERROR
            value = raw_type

        violations.append(
            FieldViolation(
                code=code,
                field=".".join(str(loc) for loc in e["loc"]),
                value=value,
            )
        )

    return violations
