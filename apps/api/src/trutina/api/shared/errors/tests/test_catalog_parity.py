import pytest
from trutina.api.shared.errors.catalog import ERROR_CATALOG
from trutina.shared.errors import ErrorCode

# Used only as a raw error_code on transport-level validation failures
# (see handlers.py); never looked up in the catalog.
_NOT_CATALOGED = {ErrorCode.REQUEST_VALIDATION_ERROR}

_AUTH_CODES = [ErrorCode.AUTH_INVALID_CREDENTIALS, ErrorCode.AUTH_THROTTLED]


@pytest.mark.unit
class TestErrorCatalogParity:
    def test_every_error_code_has_a_catalog_entry(self):
        missing = set(ErrorCode) - _NOT_CATALOGED - set(ERROR_CATALOG)

        assert missing == set()

    def test_exclusions_are_genuinely_absent_from_the_catalog(self):
        assert _NOT_CATALOGED.isdisjoint(ERROR_CATALOG)

    @pytest.mark.parametrize(
        ("code", "status_code"),
        [
            (ErrorCode.DUPLICATE_USER_EMAIL, 409),
            (ErrorCode.UNKNOWN_USER, 404),
        ],
    )
    def test_user_codes_map_to_the_decided_status(self, code, status_code):
        assert ERROR_CATALOG[code].status_code == status_code

    @pytest.mark.parametrize(
        "code", [ErrorCode.DUPLICATE_USER_EMAIL, ErrorCode.UNKNOWN_USER]
    )
    def test_user_entries_interpolate_no_context(self, code):
        entry = ERROR_CATALOG[code]

        assert "{" not in entry.message
        assert entry.hint is not None
        assert "{" not in entry.hint

    @pytest.mark.parametrize(
        ("code", "status_code"),
        [
            (ErrorCode.AUTH_INVALID_CREDENTIALS, 401),
            (ErrorCode.AUTH_THROTTLED, 429),
        ],
    )
    def test_auth_codes_map_to_the_decided_status(self, code, status_code):
        assert ERROR_CATALOG[code].status_code == status_code

    @pytest.mark.parametrize("code", _AUTH_CODES)
    def test_auth_entries_interpolate_no_context(self, code):
        entry = ERROR_CATALOG[code]

        assert "{" not in entry.message
        assert entry.hint is not None
        assert "{" not in entry.hint
