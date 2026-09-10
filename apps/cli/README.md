# trutina-cli

`trutina-cli` is Trutina's terminal presentation package: it turns command-line arguments or interactive shell input into calls to the `trutina-core` services, then renders the returned view models and application errors with Rich. Accounting rules and persistence behavior do not live here.

## What Is This

The installed command is `trutina-cli`. It requires Python 3.14+ and depends on the workspace packages `trutina-core`, `trutina-storage-mongo`, and `trutina-config`, plus `typer`, `rich`, `anyio`, and `prompt-toolkit`.

Bare invocation (`trutina-cli`) opens a persistent interactive shell; invocation with a registered top-level command name (`account`, `journal`, `posting`) or a help flag (`-h`/`--help`) dispatches one-shot through Typer instead.

## Installation

Within the workspace:

```bash
uv sync --package trutina-cli
```

## Public API

### `trutina.cli.composition`

| Symbol                                       | Purpose                                                                                                                                                                |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app`                                        | The root Typer application, with `account`/`journal`/`posting` sub-apps registered.                                                                                    |
| `main_callback`                              | `app.callback()`; fills `ctx.obj` with a fresh `CliContext` only when `ctx.obj` is `None` (test seam — never true for a real invocation dispatched through `main.py`). |
| `build_context(settings=None) -> CliContext` | Constructs a `CliContext`; performs no I/O.                                                                                                                            |
| `CliContext`                                 | Per-invocation composition root; lazily creates and caches repositories/services and the shared MongoDB connection.                                                    |
| `CliState`                                   | Pairs a `CliContext` with an `anyio.BlockingPortal`; `state.call(func, *args)` is the sync-to-async bridge every command uses.                                         |

### `trutina.cli.shell`

| Symbol                                         | Purpose                                                 |
| ---------------------------------------------- | ------------------------------------------------------- |
| `run_shell(state, *, input=None, output=None)` | Runs the interactive REPL loop until `exit`/EOF/Ctrl-C. |

### `trutina.cli.shared.ui`

| Symbol                                                                                 | Purpose                                                          |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `console`                                                                              | Shared themed Rich `Console` singleton.                          |
| `panel(content, title, style="success")` / `rule(style="success")` / `table(*columns)` | Generic Rich widget factories every feature formatter builds on. |
| `build_logo()`                                                                         | ASCII balance-scale mark + wordmark.                             |
| `build_welcome_banner()` / `print_welcome_banner()`                                    | The shell's startup banner.                                      |

### `trutina.cli.shared.interaction`

| Symbol                                                                          | Purpose                                                       |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `ask(message, *, default=None, style="info")`                                   | Themed `Prompt.ask()` wrapper.                                |
| `confirm(message, *, default=False, style="warning")`                           | Themed `Confirm.ask()` wrapper, returns `bool`.               |
| `select(message, options, *, default=None, label=str, style="info", title=...)` | Renders a numbered option panel and returns the chosen value. |

### `trutina.cli.shared.errors`

| Symbol         | Purpose                                                                 |
| -------------- | ----------------------------------------------------------------------- |
| `ERRORS`       | `dict[ErrorCode, ErrorDetail]` — CLI-owned user-facing message catalog. |
| `HINTS`        | `dict[str, str]` — CLI-owned resolution-hint catalog.                   |
| `FIELD_LABELS` | Fallback display field names for errors with no natural field.          |
| `ErrorDetail`  | `(code, message)` dataclass.                                            |

### `trutina.cli.shared.formatters`

| Symbol                             | Purpose                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `FormattedError`                   | Display-ready `(field, message, code, hint)`.                                                                      |
| `format_validation_errors(exc)`    | Pydantic `ValidationError` → `list[FormattedError]`.                                                               |
| `format_app_error(exc)`            | `AppError` → `FormattedError`.                                                                                     |
| `format_validation_app_error(exc)` | `ValidationAppError` → `list[FormattedError]`, recovering the real domain `ErrorCode` from `FieldViolation.value`. |
| `build_error_panels(errors)`       | `list[FormattedError]` → `list[rich.Panel]`.                                                                       |

### `trutina.cli.shared.boundary`

| Symbol             | Purpose                                                                                                                                                   |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `error_boundary()` | Context manager; the CLI's single seam catching `AppError`/`ValidationAppError`/`pydantic.ValidationError`, printing panels, and raising `typer.Exit(1)`. |

### `trutina.cli.features.{account,journal,posting}`

Each re-exports `app` — that feature's Typer sub-application.

## Usage

```text
trutina-cli
```

| Group     | Commands                                    |
| --------- | ------------------------------------------- |
| `account` | `create`, `get`, `list`, `update`, `delete` |
| `posting` | `post`, `get-by-account`, `get-by-journal`  |
| `journal` | `create`, `get`, `list`                     |

`-h` is also a top-level help flag. Commands that omit required input fall into their feature's interactive prompt flow, where supported.

### Interactive shell

Bare `trutina-cli` (no arguments, no recognized command as the first token) opens a persistent interactive shell — prompt `trutina>` — rather than dispatching a single command. On start, it prints a welcome banner (the ASCII balance-scale mark, the Trutina wordmark, and a short orientation line: `/ to browse commands · help for detail`) before the first prompt.

A leading `/` on any line is optional and stripped before dispatch — `/account list` and `account list` behave identically, including for the shell's own built-ins (`/exit` == `exit`, `/help` == `help`). Typing `/` (or just starting to type) opens live, Claude Code–style tab completion built from the real Typer/Click command tree, so suggestions and their descriptions can never drift from actual `--help` text. Tab accepts the highlighted (or first) match instead of just cycling through the menu.

`<command path> help` is shorthand for `<command path> --help` and render Typer's own help output for that path — there is no separate, hand-written help text to keep in sync.

`exit` (or `/exit`) is the only keyword that ends the session; EOF (Ctrl+D) and Ctrl+C also end it.

## Integration

```text
apps/cli            <- you are here (leaf application; nothing depends on it)
   │
   ▼
trutina-storage-mongo     (Mongo* repositories)
   │
   ▼
trutina-core                (AccountService, JournalService, PostingService)
   │
   ▼
trutina-shared, trutina-config
```

Depends on (per `apps/cli/pyproject.toml`): `trutina-core`, `trutina-storage-mongo`, `trutina-config`, `typer`, `rich`, `anyio`, `prompt-toolkit`. Never imports `trutina-api` or any other `apps/*` package — enforced by the workspace's `layers` import-linter contract: `trutina.cli | trutina.api → trutina.storage_mongo → trutina.core → trutina.shared | trutina.config`.

## Extending

Adding a new command group: create `features/<name>/{command,parser,prompt,handler,formatter}.py` + `tests/` mirroring `account`/`journal`/`posting`; register the Typer app in `composition/app.py`. The shell's completion tree reads the live Click command tree, so no separate shell-side command list needs updating. A new terminating/shell-only keyword goes in `shell/builtins.py::SHELL_BUILTINS`.

## Testing

```bash
uv run pytest -m "unit and cli"
uv run pytest -m "integration and cli"
```

The `cli` layer marker is derived automatically from file path by the root `conftest.py`; only the `unit`/`integration` speed marker needs to be written on the test itself.
