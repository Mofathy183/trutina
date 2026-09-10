# Trutina

Python double-entry bookkeeping engine. `uv` workspace: `apps/{cli,api}` +
`packages/{core,infrastructure,config,shared}`. Root docs cover cross-cutting facts
only — package/app internals are documented in that package's own README.md/CONTEXT.md.

## Tech Stack

- Python 3.14+, `uv` workspace (`tool.uv.workspace.members = ["apps/*", "packages/*"]`)
- Pydantic v2, Pydantic Settings
- Typer, Rich, AnyIO, prompt-toolkit (CLI)
- FastAPI, Uvicorn (API)
- Beanie, PyMongo (async) — isolated to `trutina-storage-mongo`
- Pytest (`asyncio_mode = auto`), Ruff, `ty`, `import-linter`

## Workspace Packages/Apps

| Package                  | Import path              | Depends on (workspace)                               | Depends on (external)                |
| ------------------------ | ------------------------ | ---------------------------------------------------- | ------------------------------------ |
| `trutina-shared`         | `trutina.shared`         | none                                                 | pydantic                             |
| `trutina-config`         | `trutina.config`         | none                                                 | pydantic, pydantic-settings          |
| `trutina-core`           | `trutina.core`           | trutina-shared                                       | pydantic                             |
| `trutina-storage-mongo` | `trutina.storage_mongo` | trutina-shared, trutina-core, trutina-config         | beanie, pymongo                      |
| `trutina-cli`            | `trutina.cli`            | trutina-core, trutina-storage-mongo, trutina-config | typer, rich, anyio, prompt-toolkit   |
| `trutina-api`            | `trutina.api`            | trutina-core, trutina-storage-mongo, trutina-config | fastapi[standard], uvicorn[standard] |

`trutina-cli` never depends on `trutina-api`, or vice versa. `trutina-core` never
depends on `trutina-config`.

## Import-Linter Contracts (root `pyproject.toml`, enforced in CI)

- `layers`: `trutina.cli | trutina.api → trutina.storage_mongo → trutina.core → trutina.shared | trutina.config`
- `forbidden`: `trutina.core` must never import `beanie` or `pymongo`
- `layers` (internal to core): `trutina.core.posting → trutina.core.journal → trutina.core.account`

## Repository Layout (real, current)

```text
apps/cli/src/trutina/cli/
  main.py, composition/{app,bootstrap,context,state}.py,
  features/{account,journal,posting}/{command,parser,prompt,handler,formatter}.py,
  shared/{boundary/error_boundary.py, errors/, formatters/, interaction/, ui/{theme/,shell_banner.py,logo.py}},
  shell/{loop,dispatch,completion,keybindings,builtins}.py

apps/api/src/trutina/api/
  composition/{container,bootstrap,app,dependencies}.py,
  features/{system,account,journal,posting}/{router,schemas,mapper,handler,presenter}.py,
  shared/{response.py, errors/{catalog,handlers,schemas}.py}

packages/core/src/trutina/core/{account,journal,posting}/{dtos,repo,service}.py, schemas/
packages/infrastructure/src/trutina/infrastructure/mongo/
  {account,journal,posting}/{document,repository}.py, shared/, connection.py, error_translation.py
packages/config/src/trutina/config/{base,mongo,api}.py
packages/shared/src/trutina/shared/{rule,util}.py, errors/{codes,errors,translators}.py

tests/{fixtures,factories,fakes}/     # shared test infra only, no test cases
conftest.py, pytest.ini, ty.toml, ruff.toml, pyproject.toml, compose.yml
```

Package/app own tests live beside their own code (e.g.
`packages/core/src/trutina/core/account/tests/`, `apps/cli/.../features/account/tests/`).

## Confirmed Domain Rules (per `trutina-core`)

- Every journal entry must balance (total debits == total credits).
- A journal line carries exactly one side (debit XOR credit), never both, never
  neither; negative amounts are invalid.
- `JournalEntry` requires at least two lines and a positive `journal_number`.
- `JournalEntry.posting_date` / `LedgerPosting.posting_date` must be later than
  2020-01-01 and not in the future.
- `LedgerPosting` is frozen after creation.
- `Account.normal_balance` is derived from `AccountCategory`, never stored
  independently.
- `ChartOfAccounts` enforces unique codes and unique canonical names,
  case-insensitively (`account_lookup_key()` uses Unicode `casefold()`, not `lower()`).
- Account aliases and `ChartOfAccounts.resolve()` are **not implemented**.
- `AppError` (and its `ValidationAppError` subclass) is the only exception type
  permitted to cross a service boundary in either presentation app.

## Error Model

- `trutina.shared.errors`: `ErrorCode`, `AppError`, `ValidationAppError`,
  `FieldViolation`, `pydantic_error()`, `get_field_violations()`, `PYDANTIC_CODES`.
- Known gap: `get_field_violations()` downgrades domain-raised `ErrorCode`s to
  `UNKNOWN_ERROR` on `FieldViolation.code`; the real code survives only in
  `FieldViolation.value`. Both `trutina-cli` and `trutina-api` recover it there.
- No presentation text lives in `trutina.shared` — CLI (`cli/shared/errors/`) and
  API (`api/shared/errors/catalog.py`) each own an independent message/hint/status
  catalog keyed by `ErrorCode`.

## Tooling Commands

```bash
uv sync --all-packages
uv run pytest -m unit
uv run pytest -m integration          # requires MongoDB
uv run pytest -m "unit and cli"       # single layer, either axis
uv run ruff check
uv run ruff format
uv run ty check
uv run lint-imports
```

`tools/bootstrap.sh` — sync workspace. `tools/fix.sh` — auto-fix format/lint.
`tools/pre-push.sh` — fast local gate (format check, lint, `ty check`, unit tests).
`tools/docker-build.sh` / `tools/docker-smoke.sh` — build/smoke-test the API image.

## Testing Layout

- Root `pytest.ini`: `testpaths = tests apps packages`, `asyncio_mode = auto`,
  markers `unit`/`integration` (speed, hand-written) and
  `core`/`infra`/`cli`/`api`/`shared` (layer, auto-derived from file path by root
  `conftest.py`; collection fails if a test hand-writes a conflicting layer marker).
- Root `tests/{fixtures,factories,fakes}/` — shared test infrastructure only.
- Root `conftest.py` registers per-package fixture plugins (account, posting,
  journal, mongo, settings, services, cli, api).

## Configuration

- `trutina.config`: `Settings` (prod, `TRUTINA_` prefix, `.env`), `TestSettings`
  (`TRUTINA_TEST_` prefix, `.env.test`), `MongoSettings`, `ApiSettings`,
  cached `get_settings()`.
- Nested env vars use double underscore: `TRUTINA_MONGO__URI`,
  `TRUTINA_TEST_MONGO__URI`.
- `get_settings()` is `lru_cache`d — tests must clear the cache before/after
  mutating environment variables (root `tests/fixtures/settings.py` does this
  automatically via an autouse fixture).

## Known Gaps / Cross-Package Flags (do not silently resolve — see PROJECT_CONTEXT.md)

- `trutina-shared` says `util.default_posting_date()` is unused; `apps/cli`'s
  journal parser visibly imports and calls it. Unresolved conflict.
- No `apps/api/README.md` exists; API facts here come from `apps/api/CONTEXT.md` only.
- `apps/api/CONTEXT.md` flags a possibly-invalid `except KeyError, IndexError:` in
  `api/shared/errors/handlers.py` — unconfirmed against live source.
- `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status not
  re-confirmed against current `trutina-core` source in this pass.
- `MongoPostingRepo.save_many()` has no multi-document transaction (accepted,
  documented risk in `trutina-storage-mongo`'s own CONTEXT.md).

## Development Rules

- Keep business logic out of `trutina.cli`/`trutina.api`/`trutina.storage_mongo`
  — it belongs in `trutina.core` services and domain schemas only.
- Never let `trutina.core` import `beanie`, `pymongo`, `typer`, `rich`, or `fastapi`.
- Never let `trutina.cli` and `trutina.api` import each other.
- Update a package's own README.md/CONTEXT.md when its structure or maturity
  changes; do not let root docs re-describe package internals.
- Do not document scaffolding, planned features, or unconfirmed facts as implemented.
