import pytest
from trutina.shared.errors import ErrorCode


@pytest.mark.unit
class TestAuthErrorCodes:
    def test_invalid_credentials_value_is_stable(self):
        assert ErrorCode.AUTH_INVALID_CREDENTIALS.value == "auth.invalid_credentials"

    def test_throttled_value_is_stable(self):
        assert ErrorCode.AUTH_THROTTLED.value == "auth.throttled"
