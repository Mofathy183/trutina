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

Bare invocation opens the interactive shell; a recognized top-level group (`account`, `journal`, `posting`) or `-h`/`--help` dispatches one-shot instead.

## What This Is

`trutina-cli` (import path `trutina.cli`, console script `trutina-cli`) turns argv or shell input into calls to `trutina-core` services, then renders view models and `AppError`s with Rich. It does not implement accounting rules or persistence; repositories come from `trutina-storage-postgres` through `CliContext`. See [CONTEXT.md](CONTEXT.md) for why it's shaped this way.

## API at a Glance

| Symbol | Purpose |
|---|---|
| `account` | `create`, `get`, `list`, `update`, `delete`. |
| `journal` | `create`, `get`, `list`. `--line` is `Account:Debit:Credit`. |
| `posting` | `post`, `get-by-account`, `get-by-journal`. |
| `app` / `build_context()` / `CliContext` / `CliState` | Typer root, lazy composition, and `state.call(...)` sync-to-async bridge (`trutina.cli.composition`). |
| `run_shell(state, *, input=None, output=None)` | Interactive REPL until `exit`/EOF/Ctrl-C (`trutina.cli.shell`). |
| `ask` / `confirm` / `select` | Themed prompt helpers (`trutina.cli.shared.interaction`). |
| `console` / `panel()` / `rule()` / `table()` | Shared Rich console and widget factories (`trutina.cli.shared.ui`). |
| `error_boundary()` / `ERRORS` / `HINTS` / `FIELD_LABELS` | Command error seam and CLI-owned catalogs keyed by `ErrorCode`. |

## Usage

One-shot command:

```bash
uv run trutina-cli account create --code 2001 --name Bank --category asset
```

Journal create with two `--line` values (accounts must already exist):

```bash
uv run trutina-cli journal create --line Cash:100:0 --line "Sales Revenue:0:100"
```

Same commands inside the shell (`trutina>` prompt). A leading `/` is optional. `help <command>` and `<command> help` both become `--help`. Only `exit` ends the session (`quit` is not a built-in):

```text
uv run trutina-cli
trutina> account list
trutina> /journal list
trutina> posting post 1
```

## Testing

```bash
uv run pytest -m "unit and cli"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants.
- [`trutina-core`](../../packages/core/README.md) — the accounting services this package calls.
- [`trutina-storage-postgres`](../../packages/storage-postgres/README.md) — repository implementations reached through `CliContext`.
- [`trutina-config`](../../packages/config/README.md) — typed settings (`Settings`, `TestSettings`) this package consumes.
