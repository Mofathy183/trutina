import pytest
from trutina.observability.processors import (
    coerce_context,
    drop_noise_keys,
    inject_app,
    redact_sensitive,
)


@pytest.mark.unit
class TestInjectApp:
    def test_stamps_app_when_absent(self):
        result = inject_app("api")(None, "info", {})
        assert result["app"] == "api"

    def test_does_not_override_an_existing_app(self):
        result = inject_app("api")(None, "info", {"app": "cli"})
        assert result["app"] == "cli"


@pytest.mark.unit
class TestRedactSensitive:
    def test_masks_a_top_level_sensitive_key(self):
        result = redact_sensitive(None, "info", {"password": "hunter2"})
        assert result["password"] == "***REDACTED***"

    def test_masks_credentials_inside_a_uri_value(self):
        result = redact_sensitive(
            None, "info", {"uri": "postgresql://user:pw@host:5432/db"}
        )
        assert "pw" not in result["uri"]
        assert result["uri"].endswith("@host:5432/db")

    def test_masks_sensitive_key_inside_context(self):
        result = redact_sensitive(
            None, "info", {"level": "info", "context": {"token": "abc"}}
        )
        assert result["context"]["token"] == "***REDACTED***"

    def test_drops_monetary_key_above_debug(self):
        result = redact_sensitive(
            None, "info", {"level": "info", "context": {"amount": "100.00"}}
        )
        assert "amount" not in result["context"]

    def test_keeps_monetary_key_at_debug(self):
        result = redact_sensitive(
            None, "debug", {"level": "debug", "context": {"amount": "100.00"}}
        )
        assert result["context"]["amount"] == "100.00"

    def test_leaves_non_sensitive_context_untouched(self):
        result = redact_sensitive(
            None, "info", {"level": "info", "context": {"journal_number": 42}}
        )
        assert result["context"]["journal_number"] == 42

    def test_never_masks_reserved_keys(self):
        result = redact_sensitive(None, "info", {"event": "account.created"})
        assert result["event"] == "account.created"

    def test_uri_named_key_is_masked_not_fully_redacted(self):
        result = redact_sensitive(
            None, "info", {"uri": "postgresql://user:pw@host:5432/db"}
        )
        assert result["uri"] != "***REDACTED***"

    def test_password_named_key_is_fully_redacted_not_partially_masked(self):
        result = redact_sensitive(None, "info", {"password": "hunter2://not-a-uri"})
        assert result["password"] == "***REDACTED***"


@pytest.mark.unit
class TestCoerceContext:
    def test_leaves_primitives_unchanged(self):
        result = coerce_context(
            None, "info", {"context": {"a": 1, "b": "x", "c": True, "d": None}}
        )
        assert result["context"] == {"a": 1, "b": "x", "c": True, "d": None}

    def test_coerces_an_arbitrary_object_to_a_type_name_placeholder(self):
        class Widget:
            pass

        result = coerce_context(None, "info", {"context": {"thing": Widget()}})
        assert result["context"]["thing"] == "<Widget>"

    def test_recurses_into_nested_dicts_and_lists(self):
        class Widget:
            pass

        result = coerce_context(
            None, "info", {"context": {"items": [Widget()], "nested": {"x": Widget()}}}
        )
        assert result["context"]["items"] == ["<Widget>"]
        assert result["context"]["nested"]["x"] == "<Widget>"


@pytest.mark.unit
class TestDropNoiseKeys:
    def test_strips_color_message(self):
        result = drop_noise_keys(
            None, "info", {"event": "x", "color_message": "\x1b[36mx\x1b[0m"}
        )
        assert "color_message" not in result

    def test_leaves_other_keys_untouched(self):
        result = drop_noise_keys(None, "info", {"event": "x", "context": {"a": 1}})
        assert result == {"event": "x", "context": {"a": 1}}
