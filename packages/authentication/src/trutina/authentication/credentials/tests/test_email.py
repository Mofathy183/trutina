import pytest
from trutina.authentication import normalize_email


@pytest.mark.unit
class TestNormalizeEmail:
    def test_strips_surrounding_whitespace(self):
        assert normalize_email("  ann@example.com ") == "ann@example.com"

    def test_folds_case(self):
        assert normalize_email("Ann@Example.COM") == "ann@example.com"

    def test_uses_casefold_not_lower(self):
        assert normalize_email("Straße@example.com") == "strasse@example.com"
