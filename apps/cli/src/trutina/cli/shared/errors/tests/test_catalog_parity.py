import pytest
from trutina.cli.shared.errors import ERRORS, FIELD_LABELS, HINTS
from trutina.shared.errors import ErrorCode

# Never raised by a service, so the CLI never renders it.
_NOT_CATALOGED = {ErrorCode.REQUEST_VALIDATION_ERROR}


@pytest.mark.unit
class TestCliCatalogParity:
    def test_every_error_code_has_a_message(self):
        missing = set(ErrorCode) - _NOT_CATALOGED - set(ERRORS)

        assert missing == set()

    def test_every_error_code_has_a_hint(self):
        missing = set(ErrorCode) - _NOT_CATALOGED - set(HINTS)

        assert missing == set()

    def test_each_entry_carries_its_own_code(self):
        assert all(code == detail.code for code, detail in ERRORS.items())

    def test_exclusions_are_genuinely_absent(self):
        assert _NOT_CATALOGED.isdisjoint(ERRORS)
        assert _NOT_CATALOGED.isdisjoint(HINTS)

    @pytest.mark.parametrize(
        "code",
        [
            ErrorCode.DUPLICATE_USER_EMAIL,
            ErrorCode.UNKNOWN_USER,
            ErrorCode.INVALID_EMAIL,
        ],
    )
    def test_user_codes_have_a_field_label(self, code):
        assert code in FIELD_LABELS

    def test_invalid_credentials_label_does_not_name_a_single_field(self):
        label = FIELD_LABELS[ErrorCode.AUTH_INVALID_CREDENTIALS]

        assert label not in {"email", "password"}

    def test_throttled_has_no_field_label(self):
        assert ErrorCode.AUTH_THROTTLED not in FIELD_LABELS
