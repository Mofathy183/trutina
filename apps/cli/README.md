# trutina-cli

> A Typer/Rich terminal for Trutina's double-entry bookkeeping engine — commands and an interactive shell, no accounting logic of its own.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-cli-informational)

## Quick Start

```bash
uv sync --package trutina-cli
uv run trutina-cli
```

Bare invocation opens the interactive shell; a recognized top-level group (`account`, `journal`, `posting`) or `-h`/`--help` dispatches one-shot instead. Logging is configured once, at process start, before the portal opens — see Logging and Correlation below.

## What This Is

`trutina-cli` (import path `trutina.cli`, console script `trutina-cli`) turns argv or shell input into calls to `trutina-core` services, then renders view models and `AppError`s with Rich. It does not implement accounting rules or persistence; repositories come from `trutina-storage-postgres` through `CliContext`. See [CONTEXT.md](CONTEXT.md) for why it's shaped this way.

## API at a Glance

| Symbol                                                   | Purpose                                                                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `account`                                                | `create`, `get`, `list`, `update`, `delete`.                                                                       |
| `journal`                                                | `create`, `get`, `list`. `--line` is `Account:Debit:Credit`.                                                       |
| `posting`                                                | `post`, `get-by-account`, `get-by-journal`.                                                                        |
| `trial-balance`                                          | Single top-level command (not a group). `--as-of YYYY-MM-DD` optional; omitted means all time.                     |
| `app` / `build_context()` / `CliContext` / `CliState`    | Typer root, lazy composition, and `state.call(...)` sync-to-async bridge (`trutina.cli.composition`).              |
| `run_shell(state, *, input=None, output=None)`           | Interactive REPL until `exit`/EOF/Ctrl-C (`trutina.cli.shell`). Each dispatched line gets its own correlation id.  |
| `ask` / `confirm` / `select`                             | Themed prompt helpers (`trutina.cli.shared.interaction`).                                                          |
| `console` / `panel()` / `rule()` / `table()`             | Shared Rich console and widget factories (`trutina.cli.shared.ui`).                                                |
| `error_boundary()` / `ERRORS` / `HINTS` / `FIELD_LABELS` | Command error seam and CLI-owned catalogs keyed by `ErrorCode`. Also the single place a command failure is logged. |

## Usage

One-shot command:

```bash
uv run trutina-cli account create --code 2001 --name Bank --category asset
```

Journal create with two `--line` values (accounts must already exist):

```bash
uv run trutina-cli journal create --line Cash:100:0 --line "Sales Revenue:0:100"
```

Trial balance over all posted entries, or only postings on or before a date:

```bash
uv run trutina-cli trial-balance
uv run trutina-cli trial-balance --as-of 2025-06-30
```

The report is a panel titled `Trial Balance` (or `Trial Balance (as of YYYY-MM-DD)`) with one row per account that has postings — account, debit total, credit total — followed by total debits, total credits, and a `Balanced: Yes/No` line. When nothing is in scope it shows `No postings found.` Only posted journal entries count; an entry that has not been posted contributes nothing. `--as-of` is read as midnight at the start of that date, so a posting stamped later on the same day is excluded. An invalid date exits with Click's usage error (exit code 2).

Same commands inside the shell (`trutina>` prompt). A leading `/` is optional. `help <command>` and `<command> help` both become `--help`. Only `exit` ends the session (`quit` is not a built-in):

```text
uv run trutina-cli
trutina> account list
trutina> /journal list
trutina> posting post 1
trutina> trial-balance --as-of 2025-06-30
```

## Logging and Correlation

`main.py::main()` calls `configure_logging(settings.logging, app="cli")` once, before `build_context()`/`run()`. Nothing goes to stdout for logging — Rich owns stdout entirely; by default logs go to a rotating JSON file in the platform log directory (e.g. `%LOCALAPPDATA%\trutina\Logs\cli.log` on Windows).

A one-shot invocation is wrapped in a single `correlation_scope()` around the whole `app(obj=state)` call in `run()`, so every log line the invocation produces — including ones from service/repository code running inside the portal's event loop — shares one id. The interactive shell binds its own scope **per dispatched line** instead, in `shell/dispatch.py` (`dispatch()` and `run_help()` each wrap their own `app(...)` call): a long-running shell session never has every command sharing a single id, and typing `help <target>` gets its own id too. No re-bind is needed inside `CliState.call()` — a correlation id set on the main thread reaches code run through `BlockingPortal.call(...)` on its own.

`error_boundary()` is also the single place a command failure is logged: exactly one `command.failed` line per caught exception, via a shared `_log_failure()` helper. `STORAGE_UNAVAILABLE`, `STORAGE_TIMEOUT`, and `UNKNOWN_ERROR` log at ERROR with a traceback; every other, expected domain error (validation, not found, conflict) logs at INFO with no traceback. This mirrors the API's own `_log_failure()`/`ERROR_CATALOG`-status-code split, but the two `ErrorCode` sets that decide "is this an incident" are deliberately kept independent, not shared — see [`trutina-observability`'s CONTEXT.md](../../packages/observability/CONTEXT.md) for why.

See [CONTEXT.md](CONTEXT.md) for the full design rationale.

## Testing

```bash
uv run pytest -m "unit and cli"
uv run pytest -m "integration and cli"   # requires PostgreSQL
```

`shell/tests/test_dispatch_logging.py` is the hard acceptance test for shell correlation: two commands dispatched in the same session get distinct ids, and no id leaks outside a dispatched line.

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants.
- [`trutina-core`](../../packages/core/README.md) — the accounting services this package calls.
- [`trutina-storage-postgres`](../../packages/storage-postgres/README.md) — repository implementations reached through `CliContext`.
- [`trutina-config`](../../packages/config/README.md) — typed settings (`Settings`, `TestSettings`, `LoggingSettings`) this package consumes.
- [`trutina-observability`](../../packages/observability/README.md) — `configure_logging()` and `correlation_scope()`, the only two symbols this package imports from it.
