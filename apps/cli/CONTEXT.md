# trutina-cli — Context

Audience: maintainers, reviewers, and future contributors deciding whether
a change belongs in this package and whether it preserves the guarantees
the rest of the monorepo depends on. This document explains _why_ the CLI
looks the way it does, not how to call it — see `README.md` for usage.

## Why This Package Exists Separately

Trutina's accounting domain (`trutina-core`) is deliberately storage- and
transport-agnostic: fully async, tested against fakes and real MongoDB, and
with zero knowledge of Typer, Rich, or terminal concerns. Something has to
be the first real user-facing surface onto that domain. `trutina-cli` is
that surface, kept as its own workspace package rather than folded into
`trutina-core` for the same reason `trutina-api` is separate: two
presentation layers over one domain package must not be able to
accidentally depend on each other's presentation concerns, and neither
should be able to leak presentation code into the domain.

Splitting the CLI out also means the CLI's own composition root
(`CliContext`), its sync-to-async bridge (`CliState`), and its
presentation-only error catalog can evolve independently of the API's
equivalent pieces, without either package needing to know the other
exists.

## Why Composition, Shell, And Boundary Are Packages

**Decision:** The Typer app, context construction, `CliContext`, and
`CliState` live under `trutina.cli.composition`. The interactive REPL
lives under `trutina.cli.shell` (`run_shell` from `loop.py`). The command
error seam lives under `trutina.cli.shared.boundary`. Logo and welcome
banner live under `trutina.cli.shared.ui`, not inside `shell/`.

**Why:** Those concerns used to sit as loose modules at the top of
`cli/` (and `error_boundary.py` loose under `shared/`). Grouping them
keeps the composition root, the REPL, and the error seam discoverable
the same way `features/` and `shared/ui/` already were, without mixing
prompt-toolkit loop details into Typer registration or Rich chrome into
dispatch.

**What this is not:** a compatibility layer. Former import paths
(`trutina.cli.app`, `trutina.cli.bootstrap`, `trutina.cli.context`,
`trutina.cli.state`, `trutina.cli.shell` as a module,
`trutina.cli.shell_builtins`, `trutina.cli.shell_completion`,
`trutina.cli.shared.error_boundary`) are not present as forwarding
modules. Callers import from the packages above. (`composition/__init__.py`
and `shared/boundary/__init__.py` still describe shims that are not in
the tree; treat those comments as stale until a docstring pass updates
them.)

## Why A Synchronous CLI Over An Async Domain

**Decision:** Typer/Click commands are plain, synchronous `def`s. Every
crossing into the CLI's async world (`CliContext` accessors, service calls,
repository calls) goes through exactly one `BlockingPortal`, exposed as
`state.call(func, *args)`.

**Why:** Click's dispatch machinery (`app(obj=state)`) is itself
synchronous — there is no supported way to make a Typer command body
`async def` and have Click await it directly. `trutina-core`'s services
are async because they perform real I/O (MongoDB via Beanie/PyMongo) and
the domain layer is designed to be non-blocking and storage-agnostic.
`anyio`'s `BlockingPortal` is the bridge: one background thread hosts one
asyncio event loop, and `portal.call(...)` blocks the calling (main) thread
until the async call resolves and returns a plain result.

**Why not `asyncio.run()` per command instead of a shared portal:**
`asyncio.run()` always creates a brand-new event loop. That would both
fragment MongoDB client state across event loops (which PyMongo's async
client does not support) and be unable to reuse a `CliContext`'s
already-open connection from a previous accessor call in the same
invocation. `start_blocking_portal()` is therefore called exactly once, in
`main.py::run()` — no command, service, handler, or repository may create a
second loop or a second portal.

## Why The Shell Reuses The Same Typer App

**Decision:** Bare `trutina-cli` enters `run_shell(state)`. Each non-empty
line is shlex-split and passed to the same `app(...)` used for one-shot
invocations (`standalone_mode=False`). Help shorthands become
`app([*target, "--help"], obj=state, standalone_mode=False)`.

**Why:** Command behavior, option parsing, and `--help` text must not
fork between "typed in the shell" and "typed as argv". Completion
descriptions are taken from Click's `get_short_help_str()` on that same
tree for the same reason. Shell-only keywords (`exit`, `help`) are not
Typer commands; they live in `SHELL_BUILTINS` so the loop and completer
share one catalog. Only entries with `terminates=True` end the session
today that is `exit`, not `quit`.

**Why prompt_toolkit is a CLI dependency:** the REPL needs a session with
live completion, Tab-to-accept, and a prompt style. That library stays in
this package; `trutina-core` does not import it.

## Why `CliContext` Performs No I/O At Construction

**Decision:** `build_context()` and `CliContext.__init__` never open a
MongoDB connection or construct a repository/service. Every repository and
service is created lazily, the first time a command actually asks for it
via a `get_*_repo()`/`get_*_service()` accessor, and cached for the rest
of the invocation. `__init__` does construct a `MongoExecutor`; that
object only wraps Beanie operations with storage-error translation and
does not open a connection.

**Why:** Startup cost must stay flat regardless of which command runs —
`trutina-cli --help` must never touch MongoDB, because nothing in the
`--help` path calls one of `CliContext`'s accessors. This also makes
testability free: a `CliContext` built with injected `Fake*Repo` instances
can never open a real connection, because the lazy-creation branch in each
accessor only runs when the corresponding repository is `None`. There is no
separate "test mode" flag to forget to set — the absence of an injected
repository is the only signal, and it's structural, not conventional.

**Trade-off accepted:** every accessor has to repeat the same
None-check-then-construct shape (`get_account_repo()`,
`get_journal_repo()`, `get_posting_repo()`, and the three
`get_*_service()` equivalents). This is boilerplate, but it's boilerplate
that's obvious to audit — a new repository/service follows the exact same
pattern, and a reviewer doesn't need to trace unrelated construction
logic to confirm the laziness invariant holds.

**Current connection path:** `composition/context.py` imports
`beanie.init_beanie` and PyMongo's `ConnectionFailure` /
`ServerSelectionTimeoutError` so first repository use can initialize
Beanie and translate connection failures into `AppError.storage_timeout`
/ `AppError.storage_unavailable`. That is the only CLI module that
imports those libraries today. There is no import-linter contract
forbidding Beanie/PyMongo in `trutina.cli` (the forbidden contract
applies to `trutina.core` only).

## Why Caller-Injected Repositories Are Never Torn Down

**Decision:** `CliContext.aclose()` clears repositories it built itself but
leaves caller-injected repositories (`account_repo=`, etc., passed at
construction) untouched.

**Why:** Ownership has to be unambiguous. In production, `CliContext` is
the sole owner of everything it lazily constructs for the life of one CLI
invocation — closing it is closing everything. But a test that injects a
`FakeAccountRepo` still owns that fake's lifetime and identity (its
`created_accounts`/`updated_accounts` inspection hooks need to survive
`aclose()` for assertions to run afterward). Tearing down caller-owned
state on `aclose()` would make `Fake*Repo` inspection unreliable depending
on exactly when a test happens to call `aclose()`, which is precisely the
kind of order-dependent test fragility this design avoids.

## Why CLI Error Copy Lives Outside `trutina-shared`

**Decision:** `cli/shared/errors/errors.py` (`ERRORS: dict[ErrorCode,
ErrorDetail]`) and `cli/shared/errors/hint.py` (`HINTS`, `FIELD_LABELS`)
are CLI-owned catalogs, entirely separate from `trutina-shared`'s
`ErrorCode`/`AppError` model.

**Why:** `trutina-shared`'s architectural invariant (see its own
`CONTEXT.md`) is that the shared error layer carries no presentation text.
`AppError`/`ValidationAppError` identify _what_ went wrong via `ErrorCode`;
they never carry a user-facing sentence. If message/hint text lived in
`shared`, a future second presentation layer (the API) would either have to
reuse CLI wording verbatim (wrong tone for an HTTP error envelope) or the
shared layer would need two parallel message sets, defeating the point of
being shared. Keeping wording entirely in `cli/shared/errors/` means the
API is free to build its own catalog with zero coordination cost or risk of
CLI-specific phrasing leaking into JSON responses.

## Why `error_boundary()` Is A Single, Narrow Seam

**Decision:** `error_boundary()` in `shared/boundary/error_boundary.py` is
the only code in the CLI that catches `AppError`, `ValidationAppError`, or
a raw `pydantic.ValidationError`. Commands wrap handler (and sometimes
parser) work in that context manager rather than writing their own
`try`/`except`.

**Why:** If every command wrote its own `try`/`except`, error rendering
(panel formatting, exit codes, whether to chain `from None`) would drift
per feature as each command's exception handling was authored
independently. Centralizing it means a single bug fix or presentation
change (e.g. a new panel style) is exactly one file to touch, and it
guarantees the CLI never lets a raw domain exception reach the terminal as
an unhandled traceback. `ValidationAppError` is caught before
plain `AppError` specifically because it is a subclass; getting that
ordering backward would silently swallow every field-violation list into
the single-panel `AppError` branch.

**What the source actually does:** several commands use more than one
`error_boundary()` in a single body (account `update`/`delete` fetch via
`_fetch_account`, then mutate). Account `create` wraps DTO construction
and the handler call in the same block. Nested `error_boundary()` occurs
when `update` calls `_fetch_account` from inside an outer block. The
invariant to preserve is "no second catcher of those exception types,"
not "exactly one `state.call` per command."

## Why Prompts Always Delegate To Parsers

**Decision:** `prompt.py` never constructs a DTO directly. It collects raw
values via `cli.shared.interaction` and always calls the same `parser.py`
functions the CLI-flag path uses.

**Why:** DTO construction must have exactly one source of truth regardless
of where the input came from. If prompts built DTOs independently, a
validation rule added to a parser function (e.g. a new whitespace-cleaning
step) could silently apply to flag-mode input but not interactive input, or
vice versa — a divergence that would only surface as an inconsistent user
experience, not a test failure, since unit tests for each path exercise
different entry points. Funneling both paths through the same functions
makes that class of drift structurally impossible rather than something
that has to be remembered.

## Why Posting Has No Input DTO Or Parser-Level DTO Construction

**Decision:** Unlike `account`/`journal`, the `posting` feature's
`parser.py` validates and cleans raw scalars (a journal number, an account
identifier) rather than building a DTO — because `PostingService`'s own
methods take plain arguments, mirroring the absence of a posting input DTO
in `trutina-core` itself (see that package's `CONTEXT.md` for
why: postings are derived internally, never submitted by a caller).

**Why replicate that decision at the CLI layer instead of inventing a
CLI-only wrapper DTO:** Introducing a `PostForm`-style DTO purely for the
CLI's own convenience would create a type with no service-layer consumer —
exactly the kind of speculative structure the project's "no new
functionality beyond what's needed" development rule warns against. Two
scalars are simple enough that a wrapper type adds indirection without
adding safety.

## Architectural Invariants That Must Never Be Broken

- **Commands never call a repository or service directly.** Only
  `CliContext` constructs them; only handlers call them.
- **Commands never construct domain models.** `Account(...)`,
  `JournalEntry(...)`, etc. are built exclusively by `trutina-core`
  services.
- **Commands never render Rich components directly**, including one-line
  status text — every user-facing string is composed in a feature's
  `formatter.py`.
- **Handlers never import `typer` or `rich`, and never prompt or print.**
  A handler must remain callable identically from a command or directly
  from a test.
- **Formatters never call a service or repository, and never import a
  domain schema** — only the DTOs/ViewModels a service already returned.
- **Services remain UI-independent.** Nothing under `trutina-core`
  imports `rich`, `typer`, or anything under `cli/` — enforced by the
  workspace's layered import-linter contract.
- **Exactly one `BlockingPortal`/event loop per process.** No command,
  service, or repository may open a second one.
- **`error_boundary()` is the only catcher of `AppError`,
  `ValidationAppError`, and Pydantic `ValidationError`.** Do not add a
  second `try`/`except` for those types outside that seam.

## Allowed and Forbidden Dependencies

**Allowed** (per `apps/cli/pyproject.toml`): `trutina-core`,
`trutina-storage-mongo`, `trutina-config`, `typer`, `rich`, `anyio`,
`prompt-toolkit`.

**Forbidden:** `trutina-api`, or any other `apps/*` package — the CLI must
never depend on a sibling application.

**Direction:** enforced by the workspace's root `pyproject.toml`
import-linter `layers` contract:
`trutina.cli | trutina.api → trutina.storage_mongo → trutina.core →
trutina.shared | trutina.config`. This package sits at the top; nothing
downstream may import from it.

## Layering Within This Package

```text
cli.composition.app
  -> cli.features.*.command
    -> cli.features.*.{parser, prompt}     -> DTOs or scalars (trutina-core)
    -> cli.composition.state.CliState.call(...)
      -> cli.features.*.handler
        -> cli.composition.context.CliContext -> trutina-core services
    -> cli.features.*.formatter -> cli.shared.ui
    -> cli.shared.boundary.error_boundary
         -> cli.shared.formatters.error + cli.shared.errors + cli.shared.ui

cli.main.run
  -> start_blocking_portal + CliState
  -> cli.shell.run_shell  or  cli.composition.app(obj=state)
  -> finally: portal.call(context.aclose)

cli.shell.loop
  -> cli.shared.ui.print_welcome_banner
  -> prompt_toolkit PromptSession
       (cli.shell.completion, cli.shared.ui.theme.build_shell_style,
        cli.shell.keybindings)
  -> cli.shell.dispatch.app(...)   [same Typer app]
```

Within `cli/shared/`, `boundary/error_boundary.py` sits above `formatters/error.py`,
`errors/`, and `ui/` — it depends on all three, but none of them depend
back on it. `ui/` is the lowest sub-layer (generic Rich widgets, logo,
banner; no error-model awareness); `errors/`/`formatters/` build on
`trutina-shared`'s `ErrorCode`/`AppError` plus `ui/`'s widgets;
`error_boundary.py` is the only place all of that, plus `typer.Exit`,
actually combines.

`shell/` depends on `composition` (the app and `CliState`) and `shared/ui`
(banner, console, prompt_toolkit style). It does not own copy or logo art.

No import-linter contract currently enforces this sub-layering
mechanically (only the workspace-level `apps → infrastructure → core →
shared/config` contract is checked in CI) — it is observed convention in
the current source, flagged here rather than described as enforced.

## Control Flow

```text
User types a command (argv or shell line)
  -> Typer parses into command + options
  -> Command function runs
      - flags/arguments given -> parser.py validates and builds a DTO
        (or a posting scalar)
      - required flags omitted -> prompt.py interactively collects them,
        still funneling through parser.py
  -> state.call(handler_fn, state.context, ...)   [crosses into async world]
  -> Handler resolves the relevant service from CliContext
  -> Service (trutina-core) orchestrates domain construction, validation,
     repository calls
  -> Repository (trutina-core contract -> trutina-storage-mongo adapter)
     persists/reads data
  -> Service returns a ViewModel, or raises AppError / ValidationAppError
      - success -> formatter.py builds a renderable, command calls
        print_*(), Rich Console renders it
      - failure -> error_boundary() catches the exception, formats it,
        prints panel(s), raises typer.Exit(code=1)
```

Bootstrap sequence (once per process):

```text
main() -> build_context() -> start_blocking_portal() -> CliState
  -> run_shell(state)  or  app(obj=state)
  -> finally: portal.call(context.aclose)
```

`composition/app.py`'s `main_callback()` is a defensive fallback only: if
`ctx.obj` is `None` (a real invocation dispatched through `main.py` never
hits this), it calls `build_context()` itself and stores a `CliContext`,
not a `CliState`. A context built this way is _not_ wrapped in
`main.py`'s `finally`, so nothing calls `aclose()` on it — this fallback
must only ever pair with a context that can never open a real connection
(a fake-backed one), never with a path that might lazily touch MongoDB.
Click/Typer resolves eager options such as `--help` before invoking this
callback, so `trutina-cli --help` never reaches it.

## Data Flow

- **Into a command:** raw `sys.argv` strings (Typer/Click-parsed) or
  nothing, if falling into interactive mode. Shell lines are shlex-split
  first.
- **Into a handler:** an already-validated DTO or plain scalar, plus
  `state.context` (never the `CliState` wrapper itself).
- **Out of a handler:** a ViewModel (or list of ViewModels), or a raised
  `AppError`/`ValidationAppError` that propagates unchanged.
- **Into a formatter:** ViewModels only — never a domain schema, never a
  repository result.
- **Out of a formatter's `build_*()`:** a Rich renderable (`Panel`, `Text`,
  `Table`) — no I/O. `print_*()` wraps that with a single
  `console.print(...)` call. The welcome banner follows the same
  `build_welcome_banner()` / `print_welcome_banner()` split.
- **Into `error_boundary()`:** whatever exception the wrapped block raised.
- **Out of `error_boundary()`:** printed panels, plus `typer.Exit(code=1)`
  chained `from None` so the original traceback is never re-surfaced.

## Extension Points

- **A new feature command group:** mirrors
  `cli/features/{account,journal,posting}/` — see README's
  "Contributing" section for the mechanical steps. Register the Typer
  app in `composition/app.py`; `main.py` picks up new top-level group
  names from `registered_groups`, and the shell completer from the Click
  tree.
- **A new `CliContext` accessor:** add a `get_<feature>_repo()`/
  `get_<feature>_service()` pair following the existing None-check-then-
  construct shape; wire any peer-service dependency the same way
  `JournalService` is wired to `AccountService` (and `PostingService` to
  `JournalService`).
- **New CLI-facing error wording:** add entries to
  `cli/shared/errors/errors.py`/`hint.py` keyed by `ErrorCode` — never add
  presentation text to `trutina-shared`.
- **New shared Rich widgets:** add to `cli/shared/ui/widgets.py` following
  `panel()`/`rule()`/`table()`'s shape (accept style-name strings, never
  hardcode colors); feature formatters should build on these three rather
  than constructing `rich.panel.Panel`/`rich.table.Table` inline.
- **New shell built-in:** add to `SHELL_BUILTINS` in `shell/builtins.py`
  (description plus whether it terminates). Do not maintain a second
  terminator set in `loop.py`.

## Assumptions This Package Relies On

- **`trutina-core` services are the only source of business validation.**
  This package assumes every `AppError`/`ValidationAppError` it might catch
  originates from a real `trutina-core` service or DTO construction — it
  performs no independent business-rule checking of its own.
- **Exactly one process-wide event loop.** Every accessor, service call,
  and repository call assumes it is running on the single portal-owned loop
  established once in `main.py::run()`.
- **`ErrorCode` members referenced in `cli/shared/errors/` stay in sync
  with `trutina.shared`'s `ErrorCode` enum.** `format_app_error()` and
  related formatters use `ERRORS.get(..., ERRORS[ErrorCode.UNKNOWN_ERROR])`
  (and the same fallback for `HINTS`). A new `ErrorCode` added upstream
  without a matching `ERRORS`/`HINTS` entry here degrades to that generic
  catalog text rather than failing loudly — this is presentation
  degradation, not a test failure, so it must be checked
  manually when `trutina-shared`'s `ErrorCode` enum changes.
- **`Fake*Repo` instances behave closely enough to their Mongo counterparts
  for CLI-level assertions.** E.g. `FakeJournalRepo` issues sequential
  journal numbers starting at 1 regardless of whether the caller ultimately
  saves the entry, matching `MongoJournalRepo`'s real allocation contract
  closely enough for unit-tier command tests — but it is still a fake, and
  integration tests against `real_cli_state` exist specifically because
  fidelity here is "close enough," not "identical."

## Common Mistakes to Avoid

- **Calling a service or repository from inside `command.py`** to "save a
  round trip" instead of going through `handler.py`. This breaks the
  guarantee that handlers are independently testable, portal-free, plain
  `async def` callables.
- **Printing directly from a command or handler** instead of routing
  through a feature's `formatter.py`. Every user-facing string, including
  trivial status text, belongs there so presentation stays in one place.
- **Adding a second `try`/`except AppError` block** somewhere outside
  `error_boundary()`. If a command needs different error handling, that's
  a sign the boundary itself needs a new capability, not a local
  workaround.
- **Constructing a DTO directly inside `prompt.py`** instead of collecting
  raw values and delegating to `parser.py`. This is the exact drift
  parser convergence is designed to prevent (see above).
- **Assuming `trutina-shared`'s `ErrorCode` message belongs in this
  package's catalogs.** `trutina-shared` intentionally carries no
  presentation text — every `ErrorCode` needs its own `ERRORS`/`HINTS`
  entry here; there is no fallback derivation from the shared model beyond
  the generic `UNKNOWN_ERROR` catalog entry.
- **Opening a second `BlockingPortal`** inside a test fixture or command
  for convenience. This is the single-loop invariant's most common
  violation and produces intermittent, hard-to-reproduce failures under
  PyMongo's async client, not an immediate error.
- **Re-introducing top-level forwarding modules** and leaving two public
  homes for the same symbols, or documenting shims that are not in the
  tree.
- **Adding `quit` as a terminator in comments or tests without adding it
  to `SHELL_BUILTINS`.** The loop only terminates on keywords returned by
  `terminating_keywords()`.
