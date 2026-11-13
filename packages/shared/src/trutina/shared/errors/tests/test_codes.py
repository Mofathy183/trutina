import pytest
from trutina.shared.errors import ErrorCode


@pytest.mark.unit
class TestAuthErrorCodes:
    def test_invalid_credentials_value_is_stable(self):
        assert ErrorCode.AUTH_INVALID_CREDENTIALS.value == "auth.invalid_credentials"

    def test_throttled_value_is_stable(self):
        assert ErrorCode.AUTH_THROTTLED.value == "auth.throttled"


@pytest.mark.unit
class TestUserErrorCodes:
    def test_invalid_email_value_is_stable(self):
        assert ErrorCode.INVALID_EMAIL.value == "user.invalid_email"


@pytest.mark.unit
class TestSessionErrorCodes:
    def test_token_invalid_value_is_stable(self):
        assert ErrorCode.AUTH_TOKEN_INVALID.value == "auth.token_invalid"

    def test_reauth_required_value_is_stable(self):
        assert ErrorCode.AUTH_REAUTH_REQUIRED.value == "auth.reauth_required"
