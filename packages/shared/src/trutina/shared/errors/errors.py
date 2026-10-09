"""
Domain-level error types shared across all interfaces.

Defines the stable error contract used throughout Trutina.
AppError is the only exception type permitted to cross a feature
service boundary. Adapters such as the CLI translate ErrorCode values
into user-facing messages, hints, and presentation metadata.

This module is depended on by service-layer workflows throughout the core
account, journal, and posting features. It must remain
independent of CLI, Rich, Typer, and other presentation concerns.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from .codes import ErrorCode

if TYPE_CHECKING:
    from pydantic import ValidationError as PydanticValidationError


def _frozen_context(ctx: Mapping[str, str]) -> Mapping[str, str]:
    """Freeze an error context mapping after construction.

    AppError instances are immutable contracts once they leave the service
    layer. Wrapping context in a read-only proxy prevents accidental
    mutation by callers and keeps error payloads stable for adapters,
    logging, and testing.
    """
    return MappingProxyType(dict(ctx))


@dataclass(frozen=True)
class FieldViolation:
    """
    Represents a single field-level validation failure.

    Each violation identifies the field that failed validation, the
    ErrorCode describing the violated rule, and the offending value.

    `value` is stringified during translation so adapters receive a stable,
    presentation-safe representation rather than arbitrary Python objects.
    """

    code: ErrorCode
    field: str
    value: str


@dataclass(frozen=True)
class AppError(Exception):
    """
    Represents a structured domain failure that has crossed a service boundary.

    AppError is the only exception type permitted to leave a feature
    service and be consumed by adapters. Services raise AppError (or a
    subclass) to communicate stable failure conditions without exposing
    implementation details.

    Adapters map `code` to user-facing messages, hints, HTTP statuses,
    or other presentation metadata. AppError never carries presentation
    strings itself.

    The context payload is a read-only mapping of string keys to string
    values. Domain models, DTOs, repositories, validation errors, and
    other complex objects must never be stored in it.

    The optional `cause` field exists solely for diagnostics and logging
    and must never be exposed to end users.
    """

    code: ErrorCode
    context: Mapping[str, str] = field(default_factory=dict)
    cause: BaseException | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        # frozen=True blocks normal assignment, so use object.__setattr__
        object.__setattr__(self, "context", _frozen_context(self.context))

    @classmethod
    def not_found(cls, code: ErrorCode, resource: str, identifier: str) -> AppError:
        """Create a resource-not-found error.

        Args:
            code: ErrorCode describing the missing resource condition.
            resource: Logical resource type being queried.
            identifier: Caller-supplied identifier that failed lookup.

        Returns:
            An AppError carrying lookup context for adapter translation.
        """
        return cls(code=code, context={"resource": resource, "identifier": identifier})

    @classmethod
    def conflict(
        cls, code: ErrorCode, resource: str, field_name: str, value: str
    ) -> AppError:
        """Create a resource-conflict error.

        Args:
            code: ErrorCode describing the conflict condition.
            resource: Logical resource type involved.
            field_name: Field whose value caused the conflict.
            value: Conflicting value.

        Returns:
            An AppError carrying conflict details for adapter translation.
        """
        return cls(
            code=code,
            context={"resource": resource, "field": field_name, "value": value},
        )

    @classmethod
    def unknown(cls, cause: BaseException | None = None) -> AppError:
        """Create an unexpected-failure error.

        Args:
            cause: Optional underlying exception preserved for diagnostics.

        Returns:
            An AppError with ErrorCode.UNKNOWN_ERROR.
        """
        return cls(code=ErrorCode.UNKNOWN_ERROR, cause=cause)

    @classmethod
    def storage_unavailable(cls, cause: BaseException | None = None) -> AppError:
        """Create a storage-unavailable error.

        Raised when the storage backend cannot be reached due to a
        connection failure. Callers should treat this as a transient
        infrastructure failure, not a domain error.

        Args:
            cause: The underlying connection exception preserved for
                diagnostics and logging.

        Returns:
            An AppError with ErrorCode.STORAGE_UNAVAILABLE.
        """
        return cls(code=ErrorCode.STORAGE_UNAVAILABLE, cause=cause)

    @classmethod
    def storage_timeout(cls, cause: BaseException | None = None) -> AppError:
        """Create a storage-timeout error.

        Raised when the storage backend fails to respond within the
        configured timeout window. Distinguished from a general
        connection failure so callers can apply a different retry or
        alerting strategy.

        Args:
            cause: The underlying timeout exception preserved for
                diagnostics and logging.

        Returns:
            An AppError with ErrorCode.STORAGE_TIMEOUT.
        """
        return cls(code=ErrorCode.STORAGE_TIMEOUT, cause=cause)


@dataclass(frozen=True)
class ValidationAppError(AppError):
    """
    Represents one or more field-level validation failures.

    ValidationAppError is raised when domain validation detects invalid
    input and multiple violations may need to be reported together. It
    carries FieldViolation records that adapters translate into per-field
    error output.

    The contained violations are intended for deterministic rendering so
    users receive stable validation output regardless of execution order.
    """

    errors: list[FieldViolation] = field(default_factory=list)

    @classmethod
    def validation(cls, exc: PydanticValidationError) -> ValidationAppError:
        """Translate a Pydantic ValidationError into a ValidationAppError.

        Pydantic-native error types in the explicit translation allow-list
        are mapped directly. All other types, including custom domain
        validator types, become UNKNOWN_ERROR; the raw Pydantic type is
        preserved in `value` for adapters and logs.

        Args:
            exc: The Pydantic ValidationError raised by a domain schema.

        Returns:
            A ValidationAppError carrying all field violations.
        """
        from .translators import get_field_violations

        return cls(
            code=ErrorCode.VALIDATION_ERROR,
            errors=get_field_violations(exc),
        )

    @classmethod
    def required_field(cls, field_name: str, value: str) -> ValidationAppError:
        """Build a single-violation error for a required field that is blank.

        Used when a caller-supplied value is present but carries no
        content (for example a whitespace-only actor), which Pydantic's
        own ``missing`` check would not report. The violation is built
        directly rather than translated from a Pydantic error, so its
        code stays ``REQUIRED_FIELD`` instead of being downgraded to
        ``UNKNOWN_ERROR`` by ``get_field_violations()``.

        ``REQUIRED_FIELD`` is ``"missing"`` in Pydantic's vocabulary, and a
        blank string is not strictly missing. A dedicated blank-value code
        does not exist, so this is the closest stable identity.

        Args:
            field_name: The name of the offending field.
            value: The rejected input, stringified for presentation safety.
                Must not be a secret.

        Returns:
            A ValidationAppError with code VALIDATION_ERROR carrying one
            FieldViolation with code REQUIRED_FIELD.
        """
        return cls(
            code=ErrorCode.VALIDATION_ERROR,
            errors=[
                FieldViolation(
                    code=ErrorCode.REQUIRED_FIELD,
                    field=field_name,
                    value=value,
                )
            ],
        )
