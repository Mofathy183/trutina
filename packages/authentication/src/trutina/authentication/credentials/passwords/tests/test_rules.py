import pytest
from trutina.authentication import MAX_PASSWORD_LENGTH, normalize_password


@pytest.mark.unit
class TestNormalizePassword:
    def test_converts_to_nfkc(self):
        assert normalize_password("ＰＡＳＳ１２３４") == "PASS1234"

    def test_expands_compatibility_ligatures(self):
        assert normalize_password("ﬁne-password") == "fine-password"

    def test_strips_leading_and_trailing_whitespace(self):
        assert normalize_password("  pass word 1  ") == "pass word 1"

    def test_keeps_interior_whitespace(self):
        assert normalize_password("a  b\tc") == "a  b\tc"

    def test_strips_no_break_and_ideographic_spaces(self):
        assert normalize_password("\u00a0abc\u3000") == "abc"

    @pytest.mark.parametrize("blank", ["", " ", "        ", "\t\n", "\u3000\u00a0"])
    def test_blank_input_becomes_empty(self, blank):
        assert normalize_password(blank) == ""

    def test_never_changes_case(self):
        assert normalize_password("AbC-dEf") == "AbC-dEf"

    @pytest.mark.parametrize("raw", ["  Ｐａｓｓ word  ", "ﬁ x", "plain"])
    def test_is_idempotent(self, raw):
        once = normalize_password(raw)

        assert normalize_password(once) == once


@pytest.mark.unit
class TestPasswordLimits:
    def test_maximum_length_is_128(self):
        assert MAX_PASSWORD_LENGTH == 128
