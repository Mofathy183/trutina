# trutina-config — Context

For usage, see README.md. This document explains why, not how.

## Why this architecture was chosen

Trutina has multiple applications (`trutina-cli`, `trutina-api`) and storage
adapters (`trutina-storage-mongo`, `trutina-storage-postgres`) that all need the
same categories of configuration — a Mongo connection, a PostgreSQL connection,
API bind settings, and (as of the logging rollout) a logging pipeline
configuration — sourced the same way. The alternative (`os.environ` reads
scattered across each app) would mean re-deriving env-var naming, dotenv
loading, and test/production isolation independently in every consumer, with
no guarantee they'd agree on a prefix convention or a nesting delimiter.

`pydantic-settings`'s `BaseSettings` was chosen (over hand-rolled
`os.environ.get(...)` parsing, or a plain `BaseModel` populated by a caller)
specifically because it gives typed validation, a documented
`env_nested_delimiter`, and dotenv-file loading for free, and because
`pydantic` is already the project's validation library everywhere else —
introducing a second config-parsing dependency would be inconsistent with
that.

## Alternatives considered

- **One flat `Settings` model with no nesting** (`mongo_uri`, `mongo_db`,
  `postgres_uri`, `api_host`, `api_port`, `logging_level` as top-level fields).
  Rejected: as the number of settings groups grows — `PostgresSettings` and
  `LoggingSettings` both joining `MongoSettings`/`ApiSettings` are confirmed
  examples of this happening — a flat model becomes an undifferentiated field
  list with no way to tell which fields belong to which subsystem at a glance.
  Nesting (`settings.mongo.uri`, `settings.postgres.uri`, `settings.api.port`,
  `settings.logging.level`) keeps each group's fields visibly grouped and
  independently reusable — a storage adapter only ever needs its own nested
  settings object, not the whole `Settings` object, and `trutina-observability`
  only ever needs `settings.logging`.
- **Passing raw environment variables into each consumer.** Rejected: this is
  precisely the "N independently drifting copies of the same rule" failure
  mode the rest of the codebase's architecture avoids for business logic, and
  configuration parsing is no different — a typo in an env var name should
  fail once, at one well-tested boundary, not silently produce `None` in
  three different places.
- **A single settings class with a runtime "test mode" flag** instead of a
  separate `TestSettings` subclass. Rejected: a boolean flag threaded through
  every field access is easy to forget to check and easy to leave set by
  accident between tests. A distinct class with its own `env_prefix`/
  `env_file` makes the two configurations structurally incapable of reading
  each other's variables — the isolation is enforced by type, not by
  convention.

## Trade-offs accepted

- **`get_settings()`'s `lru_cache` makes configuration effectively
  process-global.** This is deliberate — repeatedly re-parsing the
  environment on every access would be wasteful and would risk a settings
  object changing mid-request if the environment mutated concurrently. The
  accepted cost is that tests which mutate environment variables must
  explicitly clear the cache, which is why the isolation fixture exists as
  shared test infrastructure rather than being left to each test file to
  remember.
- **Nested settings models (`MongoSettings`, `ApiSettings`,
  `PostgresSettings`, `LoggingSettings`) are plain `BaseModel`, not
  `BaseSettings`.** Confirmed in source: none of the four defines a
  `model_config`/`SettingsConfigDict`. Only the root `Settings`/`TestSettings`
  classes own env-prefix and dotenv-file configuration. This means a nested
  settings object can never be constructed standalone from the environment —
  it must always be built as part of the root model's `default_factory`.
  That's an accepted constraint, not an oversight: giving every nested model
  its own independent `BaseSettings` config would create ambiguity about
  which prefix wins when a nested model is used outside of `Settings`.

## Design decisions future contributors should preserve

- Every settings group (`MongoSettings`, `ApiSettings`, `PostgresSettings`,
  `LoggingSettings`, and any future addition) stays a plain `BaseModel`
  nested inside `Settings` — never its own independently-loaded
  `BaseSettings`.
- `TestSettings` stays a subclass of `Settings`, overriding only
  `env_prefix` and `env_file` (confirmed: `base.py`'s `TestSettings` changes
  nothing else), so any field added to `Settings` is automatically available
  under the test prefix without a second definition.
- `get_settings()` stays the single cached accessor for production code.
  Constructing `Settings()` directly is reserved for tests and explicit
  override scenarios — application composition roots should call
  `get_settings()`, not `Settings()`, so there's exactly one cached instance
  per process.

### `LoggingSettings.file_path` coerces `pathlib.Path` to `str`

**Decision:** `file_path` is typed `str | None`, but carries a
`mode="before"` field validator that coerces any `pathlib.Path` input to
`str` before Pydantic's own type check runs.

**Why:** Found as a real bug during Phase 3 of the logging rollout (see
`trutina-observability`'s own CONTEXT.md for the full account), not designed
in from the start. Pydantic v2 does not implicitly coerce `Path → str` for a
plain string field, and both pytest's `tmp_path` fixture and any
Windows-flavored path-building code naturally hand out `Path` objects, not
strings — every caller that forgot an explicit `str(path)` at the call site
failed validation outright with `ValidationError: file_path — Input should
be a valid string`. Coercing at the settings boundary means no caller
anywhere in the workspace has to remember this, rather than trusting every
future call site (test fixture or real code) to convert first.

**Constraint for contributors:** if a future settings field is ever given a
filesystem-path type, apply the same `mode="before"` coercion rather than
leaving it `str`-only and hoping every caller remembers to convert.

## Architectural invariants that must never be broken

- **Zero dependencies on any other `trutina-*` package.** Confirmed by
  `pyproject.toml`: dependencies are exactly `pydantic` and
  `pydantic-settings`. This package sits at the root of the workspace
  dependency graph. If this package ever needs to import from `trutina.core`
  or a storage adapter, that is a sign the code doesn't belong here.
- **No I/O beyond dotenv-file reads performed by `pydantic-settings`
  itself.** This package must never open a network connection, read a
  database, or otherwise perform work beyond parsing configuration —
  confirmed, none of `base.py`/`mongo.py`/`api.py`/`postgres.py`/`logging.py`
  perform any I/O of their own.
- **Production and test configuration must remain namespace-isolated.**
  `TRUTINA_` vs. `TRUTINA_TEST_`, `.env` vs. `.env.test`. A change that lets
  test configuration silently fall back to reading production variables (or
  vice versa) is a correctness regression, not a refactor.

## Allowed dependencies

- `pydantic` — field validation and model definitions.
- `pydantic-settings` — environment/dotenv loading, `env_nested_delimiter`.
- Python standard library (`functools.lru_cache`, `pathlib.Path` for the
  `LoggingSettings.file_path` coercion).

## Forbidden dependencies

- Any other `trutina-*` workspace package (`trutina-core`,
  `trutina-storage-mongo`, `trutina-storage-postgres`, `trutina-cli`,
  `trutina-api`, `trutina-observability`). This package is a dependency root;
  nothing here may depend on anything downstream of it — including
  `trutina-observability`, which depends on this package, never the reverse.
- Any driver or client library for a specific backend (`pymongo`, `beanie`,
  `sqlalchemy`, `asyncpg`, an HTTP client, `structlog`, etc.) — this package
  describes configuration shape, it does not use the configuration to
  connect to anything or to configure a logging pipeline itself.

## Layering rules

`trutina-config` has no internal layers of its own beyond five sibling files
(`mongo.py`, `postgres.py`, `api.py`, `logging.py`, `base.py`) plus
`__init__.py`. The only ordering rule: `base.py` imports from
`mongo.py`/`postgres.py`/`api.py`/`logging.py` (to nest them into `Settings`),
never the reverse — a nested settings module must never import the root
`Settings`/`TestSettings` classes.

## Control flow

1. An application composition root calls `get_settings()` (or constructs
   `Settings()`/`TestSettings()` directly, in tests).
2. `pydantic-settings` reads the relevant dotenv file (if present) and
   overlays matching `TRUTINA_`/`TRUTINA_TEST_`-prefixed environment
   variables.
3. Nested fields (`mongo`, `postgres`, `api`, `logging`) are populated from
   double-underscore-delimited variables (`TRUTINA_MONGO__URI`,
   `TRUTINA_POSTGRES__URI`, `TRUTINA_LOGGING__LEVEL`) or fall back to each
   nested model's own `Field(default=...)` values if unset.
4. The resulting `Settings`/`TestSettings` instance is handed to whatever
   needs it (`connect(settings.mongo)`, `connect(settings.postgres)`,
   `uvicorn.run(host=settings.api.host, ...)`,
   `configure_logging(settings.logging, app=...)`), by the caller — this
   package never passes its own output anywhere itself.

## Data flow

Environment variables and dotenv files are the only data sources. There is
no reverse flow — nothing in this package writes to the environment,
persists settings, or mutates its own output after construction.

## Extension points

`PostgresSettings` and `LoggingSettings` are both confirmed, already-realized
examples of the pattern below (added alongside `MongoSettings`/`ApiSettings`
during the Postgres migration and the logging rollout, respectively) —
follow the same shape for anything added after them:

- New settings groups: add a `BaseModel` file, nest it into `Settings` with
  a `default_factory`, re-export it from `__init__.py`. See README's API
  table for the current field set of each group.
- New fields on an existing group: add a `Field(...)` with a sensible
  default and a description; no other file needs to change unless the field
  affects `TestSettings`'s isolation story (it won't, since `TestSettings`
  inherits the same field set).
- A field that will hold a filesystem path: type it `str` and add a
  `mode="before"` field validator coercing `pathlib.Path → str`, following
  `LoggingSettings.file_path`'s precedent, rather than leaving it `str`-only.

## Assumptions this package relies on

- Callers that need test isolation between environment-variable mutations
  will clear `get_settings`'s cache (directly, or via the shared
  `isolate_settings_cache` fixture) — this package does not enforce that
  itself.
- `.env`/`.env.test` files, if present, are trusted local input — this
  package performs no secrets-manager integration and assumes production
  secrets are supplied via real environment variables, not a committed
  dotenv file.

## Known gaps

- No secrets-manager integration exists — `Settings`/`TestSettings` read
  only from environment variables and dotenv files. Nothing in this
  package's source suggests otherwise; this is a genuine absence, not
  scaffolding for something partially built.
- This package's own test coverage is confirmed present:
  `packages/config/src/trutina/config/tests/{test_mongo,test_api,
test_postgres,test_settings,test_logging}.py` cover each nested settings
  group's defaults/overrides, confirm none is a `BaseSettings` subclass, and
  pin `Settings`/`TestSettings` namespace isolation, `get_settings()`'s cache
  behavior, and (as of `test_logging.py`) `LoggingSettings`'s validation
  rules and `Path` coercion.
- Whether `trutina-storage-postgres` formally declares `trutina-config` as a
  dependency in its own `pyproject.toml` was not directly confirmed in this
  pass — `PostgresSettings`' docstring names it as the consumer of these
  fields, but the package's own manifest wasn't available to check. Confirm
  before stating it as fact elsewhere.

## Common mistakes to avoid

- **Calling `Settings()` directly in application code instead of
  `get_settings()`.** This bypasses the cache and can produce a second,
  independently-constructed settings object mid-process — use
  `get_settings()` in production code paths; reserve direct construction for
  tests and explicit overrides.
- **Forgetting to clear the `get_settings` cache after mutating environment
  variables in a test.** If you're writing a test outside the shared fixture
  infrastructure, remember `get_settings` is process-cached — a
  `monkeypatch.setenv(...)` won't be reflected until the cache is cleared.
- **Giving a new nested settings model its own `BaseSettings`/env prefix.**
  Only `Settings`/`TestSettings` should ever own environment-loading
  configuration — a nested model added as `BaseSettings` will silently
  ignore the parent's prefix rules.
- **Assuming this package validates connectivity.** `MongoSettings`/
  `PostgresSettings` describe a URI/DB name; neither verifies a database
  instance is reachable at that URI — that check belongs to the respective
  storage adapter's own `connect()`. Likewise, `LoggingSettings` describes
  shape only — it never opens a file handle or installs a logging handler
  itself; that belongs to `trutina-observability`'s `configure_logging()`.
- **Typing a new path-like field as bare `str` without the coercion
  validator**, then being surprised when a `pathlib.Path`-returning caller
  (a test fixture, a CLI argument) fails validation — see
  `LoggingSettings.file_path`'s decision above.
