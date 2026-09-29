"""Idempotent root-logger configuration from LoggingSettings.

configure_logging() is the single place a process wires up its
logging pipeline -- called once per process (create_app() for the API,
main.py::run() for the CLI). structlog.configure() is never called:
structlog is used purely as a ProcessorFormatter attached to a stdlib
handler, so every logging.getLogger(__name__).info(...) call anywhere
in the codebase, including third-party libraries, is formatted by the
same pipeline with no per-caller structlog import required.

Idempotency: a second call removes only the handler this function
previously installed (tracked via a marker attribute on the root
logger), never structlog's own state and never handlers installed by
anything else (e.g. pytest's caplog).
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog
from trutina.config import LoggingSettings

from .correlation import get_correlation_id
from .processors import coerce_context, drop_noise_keys, inject_app, redact_sensitive

_INSTALLED_HANDLER_ATTR = "_trutina_observability_handler"


def _correlation_processor(logger, method_name, event_dict):
    cid = get_correlation_id()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def _resolve_sink(settings: LoggingSettings, app: str) -> str:
    if settings.sink != "auto":
        return settings.sink
    return "stdout" if app == "api" else "file"


def _resolve_format(settings: LoggingSettings, sink: str) -> str:
    """Resolve "auto" to a concrete renderer choice.

    "console" and "json" are always honored as given. "auto" renders
    console when the resolved sink is a real interactive terminal
    (a developer watching `trutina-api`/`trutina-cli` run locally) and
    json otherwise -- a piped/redirected stream, a file sink, or a
    container's captured stdout all get json, since those are read by
    something other than a human's eyes in real time.

    Args:
        settings: The resolved LoggingSettings for this process.
        sink: The already-resolved sink ("stdout", "stderr", or
            "file") -- passed in rather than re-resolved, so this and
            _build_stream() never disagree about which sink is active.
    """
    if settings.format != "auto":
        return settings.format
    if sink == "stdout":
        return "console" if sys.stdout.isatty() else "json"
    if sink == "stderr":
        return "console" if sys.stderr.isatty() else "json"
    return "json"  # file sink: always machine-readable, never a TTY


def _default_log_path(app: str) -> str:
    import platformdirs

    log_dir = Path(platformdirs.user_log_dir("trutina"))
    return str(log_dir / f"{app}.log")


def _build_stream(settings: LoggingSettings, app: str, sink: str) -> logging.Handler:
    if sink == "stdout":
        return logging.StreamHandler(sys.stdout)
    if sink == "stderr":
        return logging.StreamHandler(sys.stderr)
    if sink == "file":
        path = settings.file_path or _default_log_path(app)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return RotatingFileHandler(
            path,
            maxBytes=settings.file_max_bytes,
            backupCount=settings.file_backup_count,
        )
    raise ValueError(f"Unknown sink: {sink!r}")


def _supports_color(handler: logging.Handler) -> bool:
    """Whether colorizing this handler's output is safe.

    A RotatingFileHandler's stream is never a TTY, so this is False
    for the file sink automatically -- stated explicitly here rather
    than left to accident, since writing raw ANSI escape codes into a
    log file would make every downstream `grep`/log-shipper's output
    unreadable.
    """
    stream = getattr(handler, "stream", None)
    return bool(stream is not None and hasattr(stream, "isatty") and stream.isatty())


def configure_logging(
    settings: LoggingSettings,
    *,
    app: str,
    extra_processors: tuple = (),
) -> None:
    """Configure the process-wide root logger from LoggingSettings.

    Args:
        settings: The resolved LoggingSettings for this process.
        app: Short app identifier ("api", "cli", ...), injected into
            every record's "app" field and used to resolve "auto"
            sink/format choices.
        extra_processors: Additional structlog-style processors run
            ahead of the final renderer. The seam for later needs
            (tracing ids, a shipping handler) without widening this
            function's own signature.
    """
    root = logging.getLogger()

    previous = getattr(root, _INSTALLED_HANDLER_ATTR, None)
    if previous is not None and previous in root.handlers:
        root.removeHandler(previous)

    sink = _resolve_sink(settings, app)
    handler = _build_stream(settings, app, sink)

    fmt = _resolve_format(settings, sink)
    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(
            colors=_supports_color(handler),
            pad_level=False,
        )
    )

    shared_processors = [
        _correlation_processor,
        inject_app(app),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.ExtraAdder(),
        drop_noise_keys,
        redact_sensitive,
        coerce_context,
        *extra_processors,
        structlog.processors.dict_tracebacks,
    ]

    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root.addHandler(handler)
    setattr(root, _INSTALLED_HANDLER_ATTR, handler)
    root.setLevel(settings.level)

    for logger_name, level in settings.logger_levels.items():
        logging.getLogger(logger_name).setLevel(level)

    # Access logging is fully replaced by CorrelationIdMiddleware's own
    # request.completed line -- silenced outright, not just quieted,
    # to avoid double-logging every request.
    logging.getLogger("uvicorn.access").disabled = True
