# trutina-observability

> Shared logging configuration and request/command correlation for Trutina's presentation apps.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Layer](https://img.shields.io/badge/layer-storage--adjacent-informational)

## Quick Start

```bash
uv sync --package trutina-observability
uv run pytest -m "unit and observability"
```

## What This Is

`trutina-observability` (import path `trutina.observability`) is the single place a Trutina process decides _where_ its logs go and _what they look like_. It never decides _whether_ to log — every package and app emits through the standard library's `logging` module directly (`logging.getLogger(__name__)`), with zero import of this package or of `structlog`. Only `apps/cli` and `apps/api` import `trutina.observability`, exactly once each, at their own composition root. See [CONTEXT.md](CONTEXT.md) for why it's shaped this way.

## API at a Glance

| Symbol                                                     | Purpose                                                                                                                                                          |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `configure_logging(settings, *, app, extra_processors=())` | Idempotent root-logger setup from `LoggingSettings`. Call once per process.                                                                                      |
| `correlation_scope(correlation_id=None)`                   | Context manager binding one correlation id for its duration; generates one if none is given or the given one is invalid.                                         |
| `new_correlation_id()`                                     | A fresh, time-ordered (`uuid7`) id.                                                                                                                              |
| `get_correlation_id()`                                     | Read the id bound in the current scope, or `None`.                                                                                                               |
| `CorrelationIdMiddleware`                                  | Pure ASGI middleware: honors/generates a request id, echoes it as `X-Request-ID`, stores it on `scope["state"]`, emits one `request.completed` line per request. |

## Usage

Any package or app emits with no dependency on this one:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("posting.created", extra={"context": {"journal_number": 42}})
```

A new app adopts the pipeline with one dependency and four lines:

```python
from trutina.config import get_settings
from trutina.observability import configure_logging, correlation_scope

configure_logging(get_settings().logging, app="worker")
with correlation_scope():
    run_job()
```

An ASGI app adds the middleware instead of a manual scope:

```python
from trutina.observability import CorrelationIdMiddleware

app.add_middleware(CorrelationIdMiddleware)
```

## Log Contract

Every record carries `timestamp`, `level`, `logger`, `event` (a dotted name — never an f-string), `app`, and `correlation_id` when one is bound. Failure records add `error_code`, `context`, and `exception`. See [CONTEXT.md](CONTEXT.md) for the full event catalog and level policy.

## Testing

```bash
uv run pytest -m "unit and observability"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, event catalog, level policy, known risks.
- [`trutina-config`](../config/README.md) — `LoggingSettings`, the only input this package's `configure_logging()` takes.
- [`apps/api`](../../apps/api/README.md), [`apps/cli`](../../apps/cli/README.md) — the two consumers that import this package.
