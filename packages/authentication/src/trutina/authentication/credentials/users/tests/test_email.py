import pytest
from trutina.authentication import MAX_EMAIL_LENGTH, normalize_email
from trutina.authentication.credentials.users.email import is_well_formed_email


@pytest.mark.unit
class TestNormalizeEmail:
    def test_strips_surrounding_whitespace(self):
        assert normalize_email("  ann@example.com ") == "ann@example.com"

    def test_folds_case(self):
        assert normalize_email("Ann@Example.COM") == "ann@example.com"

    def test_uses_casefold_not_lower(self):
        assert normalize_email("Straße@example.com") == "strasse@example.com"


@pytest.mark.unit
class TestIsWellFormedEmail:
    @pytest.mark.parametrize(
        "email", ["a@b.co", "ann@example.com", "first.last+tag@sub.example.org"]
    )
    def test_accepts_a_minimal_address(self, email):
        assert is_well_formed_email(email) is True

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "no-at-sign",
            "@b.co",
            "a@",
            "a@@b.co",
            "a@b@c.co",
            "a b@c.co",
            "a@b .co",
            "a\t@b.co",
            "a\x00@b.co",
            "a\u200b@b.co",
        ],
    )
    def test_rejects_a_malformed_address(self, email):
        assert is_well_formed_email(email) is False

    def test_accepts_an_address_at_the_length_limit(self):
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c")) + "@b.c"

        assert len(email) == MAX_EMAIL_LENGTH
        assert is_well_formed_email(email) is True

    def test_rejects_an_address_one_over_the_length_limit(self):
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c") + 1) + "@b.c"

        assert len(email) == MAX_EMAIL_LENGTH + 1
        assert is_well_formed_email(email) is False
