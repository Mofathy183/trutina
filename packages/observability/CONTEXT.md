# trutina-observability — Context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

CLI and API both need the same formatter chain, redaction, correlation handling, and settings mapping. Building that twice was the exact duplication the workspace's own architecture doc treats as an extraction trigger, so it was built once, in Phase 2, rather than deferred to "when a second consumer needs it" — both consumers already existed.

## Why Emit Side and Configure Side Are Split

Every other package (`trutina-core`, `trutina-shared`, `trutina-config`, both storage packages) emits through plain `logging.getLogger(__name__)` calls and imports nothing from this package or from `structlog`. Two forbidden import-linter contracts make this structural, not conventional:

- **"Emitters use stdlib logging only"** — `trutina.core`, `trutina.shared`, `trutina.config`, `trutina.storage_mongo`, `trutina.storage_postgres` may never import `structlog` or `trutina.observability`.
- **"Observability stays generic"** — `trutina.observability` may never import `trutina.core`, either storage package, `fastapi`, `starlette`, `typer`, or `rich`.

This is what lets `trutina-core` change its logging output format without every service file changing, and what keeps this package honest about being domain-agnostic — it has no `ErrorCode` awareness, no accounting vocabulary, nothing that would tie it to Trutina's business domain specifically.

## Why `structlog.configure()` Is Never Called

`configure_logging()` attaches a `structlog.stdlib.ProcessorFormatter` to a stdlib `logging.Handler`. `structlog.configure()` itself is never invoked. This means every `logging.getLogger(__name__).info(...)` call anywhere in the codebase — including from third-party libraries like uvicorn and SQLAlchemy — is formatted by the same pipeline with zero per-caller `structlog` import. The alternative (calling `structlog.configure()` and having callers use `structlog.get_logger()`) would have required every emitting module across five packages to add a `structlog` dependency and would have made third-party library output a second-class citizen, formatted differently from first-party output.

## Why Idempotency Matters

`configure_logging()` is called from more than one place in a real process: `apps/api/main.py` calls it before `uvicorn.run()`, and `apps/api/composition/app.py::create_app()` calls it again (because the production/dev containers start the `uvicorn` CLI directly against the app module, which never runs `main()` — see the reload-mode finding below). A second call must not install a second handler. `configure_logging()` tracks its own installed handler via a marker attribute on the root logger (`_INSTALLED_HANDLER_ATTR`) and removes only that handler before installing a new one — never structlog's own state, never a handler installed by anything else, including pytest's `caplog`.

## Event Catalog

Lifecycle and transport events, fixed names:

| Event                              | Emitted by                             | When                                                                                                                                                      |
| ---------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.started` / `app.stopped`      | API lifespan (`bootstrap.py`)          | Once per process, at startup/shutdown.                                                                                                                    |
| `db.connected` / `db.disconnected` | Both storage packages' `connection.py` | Once per connection open/close. Context never includes the URI.                                                                                           |
| `request.completed`                | `CorrelationIdMiddleware`              | Once per HTTP request, even if the handler raised.                                                                                                        |
| `request.failed`                   | API exception handlers                 | Once per request that ended in a translated error. INFO under HTTP 500, ERROR (with traceback) at or above it.                                            |
| `command.failed`                   | CLI `error_boundary()`                 | Once per caught CLI command failure. INFO for expected domain errors; ERROR (with traceback) for `STORAGE_UNAVAILABLE`/`STORAGE_TIMEOUT`/`UNKNOWN_ERROR`. |

Business events, added in Phase 5, success-only:

| Event                                                     | Service               | Context                                                               |
| --------------------------------------------------------- | --------------------- | --------------------------------------------------------------------- |
| `account.created` / `account.updated` / `account.deleted` | `AccountService`      | `code`, and `category` on create.                                     |
| `journal.created`                                         | `JournalService`      | `journal_number`, `line_count`.                                       |
| `posting.created`                                         | `PostingService`      | `journal_number`, `line_count` — one line per batch, not per posting. |
| `trial_balance.generated`                                 | `TrialBalanceService` | `entry_count`, `as_of_date` — never a debit/credit amount.            |

## Level Policy

| Level     | Use for                                                                                                                                                | Never for                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| `DEBUG`   | Amounts, per-line detail, third-party chatter.                                                                                                         | Anything enabled by default. |
| `INFO`    | Successful state changes, lifecycle, one line per request/command, expected domain errors (validation, not found, conflict — anything under HTTP 500). | Amounts. Read-only lookups.  |
| `WARNING` | Recoverable infrastructure oddities that didn't fail the request.                                                                                      | User mistakes.               |
| `ERROR`   | Storage unavailable/timeout, `UNKNOWN_ERROR`, unhandled exceptions — anything that should page.                                                        | Expected domain errors.      |

## Why `_ERROR_LEVEL_CODES` Is Duplicated Between CLI and API, Not Shared

Which `ErrorCode`s count as an incident worth a traceback is defined independently in `apps/cli/shared/boundary/error_boundary.py` and `apps/api/shared/errors/handlers.py`. This mirrors `trutina-shared`'s own documented refusal to merge CLI and API error-message catalogs (see that package's CONTEXT.md): which failures are worth paging an operator on is a presentation-layer, per-consumer decision — the CLI's local log file and the API's production aggregator have different operators and different alerting needs. It's also below the workspace's own extraction threshold, which calls for a confirmed _third_ real consumer with genuinely identical intent, not two independently-justified sets that happen to share a shape.

## Findings From Phase 0's Spikes (confirmed against Python 3.14.4, structlog 26.1.0, anyio 4.14.1/4.15.1, uvicorn 0.53.0)

- A context variable set on the CLI's main thread reaches code run through `anyio.from_thread.BlockingPortal.call(...)` without needing a re-bind inside `CliState.call()`. Confirmed both by the spike and by Phase 4's `test_dispatch_logging.py` two-commands-two-ids acceptance test.
- `structlog`'s `ProcessorFormatter` formats plain stdlib records correctly, including ones from a foreign (non-structlog) logger, with `ExtraAdder`, `dict_tracebacks`, and a `foreign_pre_chain` of shared processors.
- uvicorn's own startup/lifecycle lines flow through the root logger when started with `log_config=None`, including under `--reload`.
- **`--reload` caveat, confirmed live in Phase 3:** `uvicorn.run(reload=True)` spawns a parent reloader-supervisor process that never imports the app module — only its spawned child worker does. `create_app()`'s own `configure_logging()` call therefore never runs in that parent process, so `apps/api/main.py::main()` also calls `configure_logging()` directly, before `uvicorn.run(...)`, redundant with and a harmless no-op alongside `create_app()`'s own idempotent call in the child worker. Dev-only; the production Docker image never passes `--reload` and never calls `main()` at all (it starts `uvicorn` directly against the app module).

## Known Risks

- **The correlation id is read at _format_ time**, via a structlog processor that reads the context variable when a record is rendered. This works today because `StreamHandler`/`RotatingFileHandler` format in the emitting thread. Adopting a `QueueHandler` later would move formatting to a different thread and lose the id — capture it at _emit_ time instead if that change is ever made.
- **Windows file rotation** can fail if two CLI processes hold the same log file open simultaneously. The large (5 MB) rotation threshold makes this rare in practice; a logging error never crashes the app. Not yet exercised at real volume — only confirmed that a first emit creates the file correctly.
- **Long-lived tasks started inside the CLI's portal** (e.g. a connection pool's own background tasks) retain the correlation id bound at their creation time. Only matters if a library logs from inside such a task; not yet observed as an actual problem.

## Allowed and Forbidden Dependencies

**Allowed** (per `packages/observability/pyproject.toml`): `trutina-config`, `structlog`, `platformdirs`.

**Forbidden:** `trutina-core`, either storage package, `fastapi`, `starlette`, `typer`, `rich` — enforced by the "Observability stays generic" import-linter contract.

## Common Mistakes to Avoid

- Importing `trutina.observability` or `structlog` from `trutina-core`, `trutina-shared`, `trutina-config`, or either storage package — caught immediately by `lint-imports`.
- Calling `structlog.configure()` anywhere. This package's entire design assumes it is never called.
- Logging an amount (`debit_amount`, `credit_amount`, `balance`, etc.) at INFO or above — the redaction processor drops known monetary keys above DEBUG, but a new field name that doesn't match `_MONETARY_KEYS` won't be caught automatically; add it to that set if a service starts logging a new monetary-shaped field.
- Adding a second `configure_logging()` call site without checking whether it's actually needed — see the `--reload` caveat above for the one case where a second call site is intentional, not redundant.
