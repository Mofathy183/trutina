"""User registration use case.

Creates a user from an email and a password: it validates both, refuses an
address that is already registered, hashes the password and stores the
result. It depends only on the repository, hasher, clock and event-sink
contracts, so it has no storage, web or CLI knowledge. No route or command
exposes it yet.
"""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic import ValidationError as PydanticValidationError
from trutina.authentication.credentials.passwords import (
    MAX_PASSWORD_LENGTH,
    PasswordHasher,
    normalize_password,
)
from trutina.authentication.shared import (
    AuthEvent,
    AuthEventSink,
    Clock,
    NoOpAuthEventSink,
)
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
)
from trutina.shared.secret import REDACTED

from .email import is_well_formed_email, normalize_email
from .user import User, UserRepo

MIN_PASSWORD_LENGTH = 8
"""Shortest accepted password, in characters, measured after normalization.

A registration-only rule. Login never applies it, so a user whose password
was accepted under an earlier rule can still sign in.
"""

_REGISTERED_EVENT = "auth.user_registered"


class RegisterInput(BaseModel):
    """Raw registration input handed to ``RegistrationService``.

    Carries types only. Every business rule (email shape, password length)
    is checked by the service, so each failure reaches the caller as a
    ``ValidationAppError`` with a stable ``ErrorCode``. Rejected values are
    kept out of Pydantic error text by ``hide_input_in_errors``.

    Attributes:
        email: The address as entered; the service normalizes it.
        password: The plaintext password. ``SecretStr`` keeps it out of
            ``repr``.
    """

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    email: str
    password: SecretStr


class RegisteredUser(BaseModel):
    """What a successful registration reports back to its caller.

    Deliberately omits the password hash and every other stored field, so
    nothing returned by registration can carry a credential.

    Attributes:
        id: The new user's stable subject identifier.
        email: The address as stored (trimmed and case-folded).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str


class RegistrationService:
    """Registers new users with a hashed password.

    One registration validates the input, rejects an address that already
    exists (in any casing), hashes the normalized password, stores an
    active user and reports the event. Input that fails validation never
    reaches the hasher or the repository.

    The duplicate check and the insert are not atomic. Two concurrent
    registrations of one address can both pass the check; the storage
    unique index decides, and its ``DUPLICATE_USER_EMAIL`` error is passed
    on unchanged. A rejected duplicate skips hashing, so it returns faster
    than a new registration.
    """

    def __init__(
        self,
        *,
        users: UserRepo,
        hasher: PasswordHasher,
        clock: Clock,
        events: AuthEventSink | None = None,
    ) -> None:
        """Wire the service to its collaborators.

        Args:
            users: Where users are looked up and stored.
            hasher: Produces the stored password hash.
            clock: Supplies the timezone-aware creation time.
            events: Receives the registration event. Defaults to a sink
                that discards every event.
        """
        self._users = users
        self._hasher = hasher
        self._clock = clock
        self._events = events if events is not None else NoOpAuthEventSink()

    async def register(self, data: RegisterInput) -> RegisteredUser:
        """Create an active user with a hashed password.

        The email is normalized and must have a minimal valid shape. The
        password must be at most ``MAX_PASSWORD_LENGTH`` characters as
        typed, and after ``normalize_password`` must be present and at
        least ``MIN_PASSWORD_LENGTH`` and at most ``MAX_PASSWORD_LENGTH``
        characters. Every violation is reported together. A password
        violation never echoes the password: its ``value`` is masked.

        Args:
            data: The raw registration input.

        Returns:
            The new user's id and stored email.

        Raises:
            ValidationAppError: VALIDATION_ERROR carrying INVALID_EMAIL on
                ``email``, and on ``password`` REQUIRED_FIELD (blank),
                STRING_TOO_SHORT or STRING_TOO_LONG.
            AppError: DUPLICATE_USER_EMAIL if the address is already
                registered, with a context of ``resource`` and ``field``
                only. The same error is raised unchanged when the
                repository reports it after a race. UNKNOWN_ERROR if the
                validated values still cannot form a ``User``, which
                points to a defect such as a clock returning naive times.
        """
        email = normalize_email(data.email)

        violations: list[FieldViolation] = []
        if not is_well_formed_email(email):
            violations.append(
                FieldViolation(code=ErrorCode.INVALID_EMAIL, field="email", value="")
            )

        password, password_violation = _check_password(data.password.get_secret_value())
        if password_violation is not None:
            violations.append(password_violation)

        if violations:
            raise ValidationAppError(code=ErrorCode.VALIDATION_ERROR, errors=violations)

        if await self._users.get_by_email(email) is not None:
            raise AppError(
                code=ErrorCode.DUPLICATE_USER_EMAIL,
                context={"resource": "user", "field": "email"},
            )

        password_hash = await self._hasher.hash(SecretStr(password))

        try:
            user = User(
                id=uuid4(),
                email=email,
                password_hash=password_hash,
                is_active=True,
                created_at=self._clock.now(),
            )
        except PydanticValidationError as exc:
            raise AppError.unknown(cause=exc) from exc

        await self._users.create(user)

        self._events.emit(
            AuthEvent(name=_REGISTERED_EVENT, context={"subject_id": str(user.id)})
        )

        return RegisteredUser(id=user.id, email=user.email)


def _check_password(raw: str) -> tuple[str, FieldViolation | None]:
    """Validate a raw password and return the string to hash.

    The raw length is checked before normalizing, so oversized input is
    rejected before any normalization work. The length is checked again
    after normalization, which can lengthen some characters.

    Returns:
        ``(normalized, None)`` when valid, otherwise ``("", violation)``.
    """
    if len(raw) > MAX_PASSWORD_LENGTH:
        return "", _password_violation(ErrorCode.STRING_TOO_LONG)

    normalized = normalize_password(raw)
    if not normalized:
        return "", _password_violation(ErrorCode.REQUIRED_FIELD)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        return "", _password_violation(ErrorCode.STRING_TOO_SHORT)
    if len(normalized) > MAX_PASSWORD_LENGTH:
        return "", _password_violation(ErrorCode.STRING_TOO_LONG)
    return normalized, None


def _password_violation(code: ErrorCode) -> FieldViolation:
    """Build a password violation whose value is always masked."""
    return FieldViolation(code=code, field="password", value=REDACTED)
