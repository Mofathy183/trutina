import json
import logging

import pytest
from trutina.config import LoggingSettings
from trutina.observability.configure import _INSTALLED_HANDLER_ATTR, configure_logging


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    root = logging.getLogger()
    handler = getattr(root, _INSTALLED_HANDLER_ATTR, None)
    if handler is not None and handler in root.handlers:
        root.removeHandler(handler)
        delattr(root, _INSTALLED_HANDLER_ATTR)


@pytest.mark.unit
class TestConfigureLogging:
    def test_installs_exactly_one_handler(self):
        configure_logging(LoggingSettings(sink="stderr"), app="api")
        root = logging.getLogger()
        installed = [
            h for h in root.handlers if h is getattr(root, _INSTALLED_HANDLER_ATTR)
        ]
        assert len(installed) == 1

    def test_calling_twice_leaves_one_handler_not_two(self):
        configure_logging(LoggingSettings(sink="stderr"), app="api")
        configure_logging(LoggingSettings(sink="stderr"), app="api")
        root = logging.getLogger()
        installed = [
            h for h in root.handlers if h is getattr(root, _INSTALLED_HANDLER_ATTR)
        ]
        assert len(installed) == 1

    def test_json_record_contains_every_contract_field(self, capsys):
        configure_logging(LoggingSettings(sink="stdout", format="json"), app="api")
        from trutina.observability.correlation import correlation_scope

        with correlation_scope("test-corr-id"):
            logging.getLogger("some.module").info(
                "posting.created", extra={"context": {"journal_number": 1}}
            )

        line = capsys.readouterr().out.strip().splitlines()[-1]
        record = json.loads(line)

        assert record["event"] == "posting.created"
        assert record["level"] == "info"
        assert record["logger"] == "some.module"
        assert record["app"] == "api"
        assert record["correlation_id"] == "test-corr-id"
        assert record["context"] == {"journal_number": 1}
        assert "timestamp" in record

    def test_applies_logger_level_overrides(self):
        configure_logging(
            LoggingSettings(
                sink="stderr", logger_levels={"sqlalchemy.engine": "ERROR"}
            ),
            app="api",
        )
        assert logging.getLogger("sqlalchemy.engine").level == logging.ERROR

    def test_disables_uvicorn_access(self):
        configure_logging(LoggingSettings(sink="stderr"), app="api")
        assert logging.getLogger("uvicorn.access").disabled is True


@pytest.mark.unit
class TestConfigureLoggingConsoleFormat:
    def test_console_format_strips_color_message(self, capsys):
        configure_logging(LoggingSettings(sink="stdout", format="console"), app="api")
        logging.getLogger("uvicorn.error").info(
            "Started server", extra={"color_message": "\x1b[36mStarted\x1b[0m"}
        )
        out = capsys.readouterr().out
        assert "color_message" not in out
        assert "\x1b[36m" not in out  # the raw uvicorn ANSI code, not ours

    def test_auto_format_resolves_to_json_when_not_a_tty(self, capsys, monkeypatch):
        # capsys replaces sys.stdout with a non-tty object, so "auto"
        # must fall back to json here even with no format set explicitly.
        configure_logging(LoggingSettings(sink="stdout", format="auto"), app="api")
        logging.getLogger("x").info("some.event")
        out = capsys.readouterr().out.strip()
        json.loads(out.splitlines()[-1])  # must not raise
