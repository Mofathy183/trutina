from datetime import datetime

import pytest
from pydantic import SecretStr, ValidationError
from trutina.authentication import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    RegisteredUser,
    RegisterInput,
    RegistrationService,
    User,
    normalize_password,
)
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError
from trutina.shared.secret import REDACTED

from tests.factories.secret import SECRET_SENTINEL
from tests.fakes import (
    FakeAuthEventSink,
    FakeClock,
    FakePasswordHasher,
    FakeUserRepo,
)

VALID_PASSWORD = "correct horse 1"


class _Harness:
    """A service wired to fakes, exposing each fake for assertions."""

    def __init__(
        self,
        *,
        users: FakeUserRepo | None = None,
        clock: FakeClock | None = None,
    ) -> None:
        self.users = users if users is not None else FakeUserRepo()
        self.hasher = FakePasswordHasher()
        self.clock = clock if clock is not None else FakeClock()
        self.events = FakeAuthEventSink()
        self.service = RegistrationService(
            users=self.users,
            hasher=self.hasher,
            clock=self.clock,
            events=self.events,
        )


class _RacingUserRepo(FakeUserRepo):
    """Reports a duplicate from create(), as the unique index would in a race."""

    def __init__(self) -> None:
        super().__init__()
        self.raised = AppError(
            code=ErrorCode.DUPLICATE_USER_EMAIL,
            context={"resource": "user", "field": "email"},
        )

    async def create(self, user: User) -> None:
        raise self.raised


@pytest.fixture
def harness() -> _Harness:
    return _Harness()


def _input(
    email: str = "ann@example.com", password: str = VALID_PASSWORD
) -> RegisterInput:
    return RegisterInput(email=email, password=SecretStr(password))


def _pairs(error: ValidationAppError) -> list[tuple[ErrorCode, str]]:
    return [(violation.code, violation.field) for violation in error.errors]


def _assert_nothing_happened(harness: _Harness) -> None:
    assert harness.hasher.hash_calls == 0
    assert harness.users.created_users == []
    assert harness.events.events == []


@pytest.mark.unit
class TestRegister:
    async def test_stores_one_active_user_with_a_normalized_email(self, harness):
        result = await harness.service.register(_input(email=" Ann@Example.com "))

        assert len(harness.users.created_users) == 1
        stored = harness.users.created_users[0]
        assert stored.email == "ann@example.com"
        assert stored.is_active is True
        assert stored.created_at == harness.clock.now()
        assert stored.id == result.id

    async def test_hashes_the_normalized_password_exactly_once(self, harness):
        raw = "  Ｐass word 1  "

        await harness.service.register(_input(password=raw))

        stored = harness.users.created_users[0]
        assert harness.hasher.hash_calls == 1
        assert stored.password_hash == f"fake${normalize_password(raw)}"
        assert stored.password_hash == "fake$Pass word 1"

    @pytest.mark.parametrize("length", [8, MAX_PASSWORD_LENGTH])
    async def test_accepts_the_shortest_and_longest_password(self, harness, length):
        await harness.service.register(_input(password="a" * length))

        assert len(harness.users.created_users) == 1

    async def test_accepts_an_email_at_the_length_limit(self, harness):
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c")) + "@b.c"

        result = await harness.service.register(_input(email=email))

        assert len(result.email) == MAX_EMAIL_LENGTH

    async def test_returns_a_summary_without_the_hash(self, harness):
        result = await harness.service.register(_input())

        assert isinstance(result, RegisteredUser)
        assert result.email == "ann@example.com"
        assert "password_hash" not in result.model_dump()
        assert "fake$" not in result.model_dump_json()

    async def test_emits_one_event_carrying_only_the_subject_id(self, harness):
        result = await harness.service.register(_input())

        assert len(harness.events.events) == 1
        event = harness.events.events[0]
        assert event.name == "auth.user_registered"
        assert dict(event.context) == {"subject_id": str(result.id)}


@pytest.mark.unit
class TestRegisterRejectsInvalidInput:
    @pytest.mark.parametrize(
        "email", ["", "no-at-sign", "a@@b.co", "a b@c.co", "@b.co", "a@"]
    )
    async def test_rejects_a_malformed_email(self, harness, email):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(email=email))

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert _pairs(exc_info.value) == [(ErrorCode.INVALID_EMAIL, "email")]
        _assert_nothing_happened(harness)

    async def test_rejects_an_email_one_over_the_length_limit(self, harness):
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c") + 1) + "@b.c"

        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(email=email))

        assert _pairs(exc_info.value) == [(ErrorCode.INVALID_EMAIL, "email")]
        _assert_nothing_happened(harness)

    async def test_rejects_a_password_below_the_minimum(self, harness):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(password="a" * 7))

        assert _pairs(exc_info.value) == [(ErrorCode.STRING_TOO_SHORT, "password")]
        _assert_nothing_happened(harness)

    async def test_counts_the_minimum_after_trimming(self, harness):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(password="  abc    "))

        assert _pairs(exc_info.value) == [(ErrorCode.STRING_TOO_SHORT, "password")]
        _assert_nothing_happened(harness)

    @pytest.mark.parametrize("blank", ["", "        ", "\t\n  \t\n  ", "\u3000" * 10])
    async def test_rejects_a_blank_password_as_required(self, harness, blank):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(password=blank))

        assert _pairs(exc_info.value) == [(ErrorCode.REQUIRED_FIELD, "password")]
        _assert_nothing_happened(harness)

    async def test_rejects_a_password_above_the_maximum(self, harness):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(
                _input(password="a" * (MAX_PASSWORD_LENGTH + 1))
            )

        assert _pairs(exc_info.value) == [(ErrorCode.STRING_TOO_LONG, "password")]
        _assert_nothing_happened(harness)

    async def test_checks_the_raw_length_before_trimming(self, harness):
        # Only whitespace, so it would normalize to empty; the raw cap
        # applies first and reports the length, not a blank password.
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(
                _input(password=" " * (MAX_PASSWORD_LENGTH + 1))
            )

        assert _pairs(exc_info.value) == [(ErrorCode.STRING_TOO_LONG, "password")]
        _assert_nothing_happened(harness)

    async def test_rejects_a_password_that_grows_past_the_maximum_when_normalized(
        self, harness
    ):
        # U+FDFA is one character that NFKC expands to 18, so 8 of them are
        # well under the raw limit but 144 characters once normalized.
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(password="\ufdfa" * 8))

        assert _pairs(exc_info.value) == [(ErrorCode.STRING_TOO_LONG, "password")]
        _assert_nothing_happened(harness)

    async def test_reports_email_and_password_violations_together(self, harness):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(email="bad", password="short"))

        assert _pairs(exc_info.value) == [
            (ErrorCode.INVALID_EMAIL, "email"),
            (ErrorCode.STRING_TOO_SHORT, "password"),
        ]
        _assert_nothing_happened(harness)

    async def test_masks_the_password_value_in_every_violation(self, harness):
        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(email="bad", password="short"))

        values = {v.field: v.value for v in exc_info.value.errors}
        assert values["password"] == REDACTED
        assert values["email"] == ""


@pytest.mark.unit
class TestRegisterDuplicates:
    async def test_rejects_an_existing_email_in_another_casing(self, harness):
        await harness.service.register(_input(email="ann@example.com"))

        with pytest.raises(AppError) as exc_info:
            await harness.service.register(_input(email="ANN@example.com"))

        error = exc_info.value
        assert error.code == ErrorCode.DUPLICATE_USER_EMAIL
        assert dict(error.context) == {"resource": "user", "field": "email"}
        assert "ann@example.com" not in repr(error).casefold()
        assert len(harness.users.created_users) == 1

    async def test_rejects_a_duplicate_before_hashing_or_emitting(self, harness):
        await harness.service.register(_input())

        with pytest.raises(AppError):
            await harness.service.register(_input(email="Ann@Example.com"))

        assert harness.hasher.hash_calls == 1
        assert len(harness.events.events) == 1

    async def test_passes_a_race_duplicate_from_create_on_unchanged(self):
        users = _RacingUserRepo()
        harness = _Harness(users=users)

        with pytest.raises(AppError) as exc_info:
            await harness.service.register(_input())

        assert exc_info.value is users.raised
        assert harness.events.events == []


@pytest.mark.unit
class TestRegisterKeepsThePasswordSecret:
    async def test_success_exposes_the_password_nowhere_but_the_hash(self, harness):
        result = await harness.service.register(_input(password=SECRET_SENTINEL))

        assert SECRET_SENTINEL not in repr(result)
        assert SECRET_SENTINEL not in result.model_dump_json()
        assert all(SECRET_SENTINEL not in repr(e) for e in harness.events.events)

    async def test_a_rejected_registration_never_echoes_the_password(self, harness):
        too_long = SECRET_SENTINEL + " " * 200

        with pytest.raises(ValidationAppError) as exc_info:
            await harness.service.register(_input(email="bad", password=too_long))

        error = exc_info.value
        assert SECRET_SENTINEL not in repr(error)
        assert all(SECRET_SENTINEL not in v.value for v in error.errors)

    async def test_a_duplicate_error_never_echoes_the_password(self, harness):
        await harness.service.register(_input(password=SECRET_SENTINEL))

        with pytest.raises(AppError) as exc_info:
            await harness.service.register(_input(password=SECRET_SENTINEL))

        assert SECRET_SENTINEL not in repr(exc_info.value)

    def test_input_validation_errors_hide_the_rejected_values(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterInput(
                email=123,  # ty:ignore[invalid-argument-type]
                password=SecretStr(SECRET_SENTINEL),
            )

        assert "input_value" not in str(exc_info.value)
        assert SECRET_SENTINEL not in str(exc_info.value)


@pytest.mark.unit
class TestRegisterDefects:
    async def test_a_naive_clock_surfaces_as_unknown_error_not_validation(self):
        harness = _Harness(clock=FakeClock(datetime(2025, 1, 1)))

        with pytest.raises(AppError) as exc_info:
            await harness.service.register(_input())

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert not isinstance(exc_info.value, ValidationAppError)
        assert isinstance(exc_info.value.cause, ValidationError)
        assert harness.users.created_users == []
        assert harness.events.events == []
