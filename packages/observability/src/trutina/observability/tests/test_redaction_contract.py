"""Contract: no secret value reaches a rendered log line.

Covers the four credential keys M2 introduces (password, token,
refresh_token, authorization) end to end through configure_logging(),
at the top level, inside "context", and nested inside context values.
"""

import json
import logging

import pytest
from trutina.config import LoggingSettings
from trutina.observability.configure import configure_logging
from trutina.observability.processors import redact_sensitive

SENTINEL = "S3NTINEL-must-never-be-logged"

SECRET_KEYS = [
    "password",
    "token",
    "refresh_token",
    "authorization",
    "Authorization",
    "access_token",
    "password_hash",
]


def _emit_and_capture(capsys, **extra) -> tuple[str, dict]:
    configure_logging(LoggingSettings(sink="stdout", format="json"), app="api")
    logging.getLogger("tests.redaction").info("auth.attempt", extra=extra)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    return line, json.loads(line)


@pytest.mark.unit
class TestRedactionThroughPipeline:
    @pytest.mark.parametrize("key", SECRET_KEYS)
    def test_secret_in_context_never_appears_in_output(self, capsys, key):
        line, record = _emit_and_capture(capsys, context={key: SENTINEL})

        assert SENTINEL not in line
        assert record["context"][key] == "***REDACTED***"

    @pytest.mark.parametrize("key", SECRET_KEYS)
    def test_secret_as_top_level_field_never_appears_in_output(self, capsys, key):
        line, _record = _emit_and_capture(capsys, **{key: SENTINEL})

        assert SENTINEL not in line

    @pytest.mark.parametrize("key", SECRET_KEYS)
    def test_secret_nested_in_a_dict_never_appears_in_output(self, capsys, key):
        line, _record = _emit_and_capture(
            capsys, context={"request": {"headers": {key: SENTINEL}}}
        )

        assert SENTINEL not in line

    def test_secret_inside_a_list_of_dicts_never_appears_in_output(self, capsys):
        line, _record = _emit_and_capture(
            capsys, context={"attempts": [{"password": SENTINEL}]}
        )

        assert SENTINEL not in line

    def test_non_secret_context_survives_redaction(self, capsys):
        _line, record = _emit_and_capture(
            capsys, context={"journal_number": 42, "request": {"method": "POST"}}
        )

        assert record["context"]["journal_number"] == 42
        assert record["context"]["request"] == {"method": "POST"}


@pytest.mark.unit
class TestRedactSensitiveNesting:
    def test_masks_secret_one_level_below_an_innocent_key(self):
        result = redact_sensitive(
            None,
            "info",
            {"level": "info", "context": {"headers": {"Authorization": SENTINEL}}},
        )

        assert result["context"]["headers"]["Authorization"] == "***REDACTED***"

    def test_masks_uri_credentials_nested_in_a_dict(self):
        result = redact_sensitive(
            None,
            "info",
            {"level": "info", "context": {"db": {"uri": "postgresql://u:pw@h/db"}}},
        )

        assert "pw" not in result["context"]["db"]["uri"]

    def test_does_not_mutate_the_input_dict(self):
        original = {"headers": {"Authorization": SENTINEL}}
        redact_sensitive(None, "info", {"level": "info", "context": original})

        assert original["headers"]["Authorization"] == SENTINEL
