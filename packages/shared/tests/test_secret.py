import pytest
from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator
from trutina.shared.errors import ErrorCode, get_field_violations, pydantic_error
from trutina.shared.secret import (
    REDACTED,
    is_secret_location,
    is_secret_name,
    redact_input,
    safe_input_text,
)

SENTINEL = "S3NTINEL-must-never-be-logged"


@pytest.mark.unit
class TestIsSecretName:
    @pytest.mark.parametrize(
        "name",
        [
            "password",
            "new_password",
            "PASSWORD",
            "refresh_token",
            "Authorization",
            "client_secret",
            "api_key",
            "credentials",
        ],
    )
    def test_matches_credential_shaped_names(self, name):
        assert is_secret_name(name) is True

    @pytest.mark.parametrize(
        "name", ["email", "name", "code", "credit_amount", "journal_number"]
    )
    def test_ignores_ordinary_names(self, name):
        assert is_secret_name(name) is False


@pytest.mark.unit
class TestIsSecretLocation:
    def test_matches_when_any_segment_is_credential_shaped(self):
        assert is_secret_location(("credentials", "value")) is True

    def test_ignores_list_indexes_and_ordinary_segments(self):
        assert is_secret_location(("lines", 0, "account")) is False


@pytest.mark.unit
class TestRedactInput:
    def test_masks_credential_keyed_values_at_every_depth(self):
        result = redact_input({"a": {"password": SENTINEL}, "b": [{"token": SENTINEL}]})

        assert result == {"a": {"password": REDACTED}, "b": [{"token": REDACTED}]}

    def test_does_not_mutate_the_input(self):
        original = {"password": SENTINEL}

        redact_input(original)

        assert original == {"password": SENTINEL}

    def test_passes_scalars_through(self):
        assert redact_input("plain") == "plain"


@pytest.mark.unit
class TestSafeInputText:
    def test_masks_whole_value_for_a_credential_location(self):
        assert safe_input_text(("password",), SENTINEL) == REDACTED

    def test_stringifies_ordinary_values_unchanged(self):
        assert safe_input_text(("name",), "A") == "A"


class _Login(BaseModel):
    email: str
    password: SecretStr


class _PlainSecretField(BaseModel):
    new_password: str = Field(min_length=64)


class _Parent(BaseModel):
    credentials: _PlainSecretField


class _DomainRuleOnSecret(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def _reject(cls, value: str) -> str:
        raise pydantic_error(ErrorCode.INVALID_ACCOUNT_NAME)


@pytest.mark.unit
class TestFieldViolationsNeverCarryCredentials:
    def test_masks_value_on_a_credential_named_field(self):
        with pytest.raises(ValidationError) as exc_info:
            _PlainSecretField(new_password=SENTINEL)

        violation = get_field_violations(exc_info.value)[0]

        assert violation.code == ErrorCode.STRING_TOO_SHORT
        assert violation.field == "new_password"
        assert violation.value == REDACTED

    def test_masks_value_when_the_credential_is_nested(self):
        with pytest.raises(ValidationError) as exc_info:
            _Parent.model_validate({"credentials": {"new_password": SENTINEL}})

        violation = get_field_violations(exc_info.value)[0]

        assert violation.field == "credentials.new_password"
        assert violation.value == REDACTED

    def test_masks_a_sibling_credential_in_a_missing_field_input(self):
        with pytest.raises(ValidationError) as exc_info:
            _Login.model_validate({"password": SENTINEL})

        violation = get_field_violations(exc_info.value)[0]

        assert violation.code == ErrorCode.REQUIRED_FIELD
        assert violation.field == "email"
        assert SENTINEL not in violation.value

    def test_sentinel_absent_from_violation_repr(self):
        with pytest.raises(ValidationError) as exc_info:
            _Login.model_validate({"password": SENTINEL})

        violations = get_field_violations(exc_info.value)

        assert SENTINEL not in repr(violations)

    def test_keeps_domain_code_in_value_for_a_credential_field(self):
        with pytest.raises(ValidationError) as exc_info:
            _DomainRuleOnSecret(password=SENTINEL)

        violation = get_field_violations(exc_info.value)[0]

        assert violation.code == ErrorCode.UNKNOWN_ERROR
        assert violation.value == ErrorCode.INVALID_ACCOUNT_NAME
