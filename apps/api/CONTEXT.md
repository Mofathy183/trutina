# trutina-api — Context

For usage, see README.md. This document explains why, not how.

Audience: maintainers, reviewers, and future contributors deciding whether a change
belongs in this package and whether it preserves the guarantees the rest of the
monorepo depends on.

## Why This Package Exists Separately

`trutina-core`'s services are deliberately transport-agnostic — fully async, tested
against fakes and a real database, with zero knowledge of FastAPI, Typer, or any
presentation concern. Two presentation layers need to sit on top of that domain: a
terminal (`trutina-cli`) and an HTTP API (this package). Keeping them as independent
workspace packages, rather than folding the API into the CLI or vice versa, means
neither can accidentally depend on the other's presentation code, and the domain
layer never needs to know either exists. This mirrors `trutina-cli`'s own
`CONTEXT.md` reasoning for why it is split from `trutina-core` — the same argument
applies symmetrically here.

## Why The Fixed Router → Mapper → Handler → Presenter Workflow

**Decision:** Every feature router (`account`, `journal`, `posting`, `trial_balance`)
is split into four files with one direction of data flow:
a Request Schema is turned into an Input DTO by a pure `mapper.py`;
a `handler.py` makes exactly one service call; the returned ViewModel is turned into a Response Schema by a pure `presenter.py`;
the router (`router.py`) does nothing but wire those three together plus `Depends(...)`.

**Why:** This is the same motivation as the CLI's `parser.py` → `handler.py` →
`formatter.py` split, applied to HTTP instead of Typer. Four narrow files with one
job each are individually testable in isolation — `test_mapper.py` and
`test_presenter.py` need no I/O and no FastAPI test client at all, `test_handler.py`
needs only a fake-backed service, and `test_router_unit.py` is the only tier that
proves the wiring itself holds end-to-end. Splitting this way means a bug in field
mapping and a bug in HTTP wiring fail in different, specific tests rather than both
surfacing as "the endpoint returned the wrong JSON."

**Trade-off accepted:** four small files per feature instead of one, mirroring the
same boilerplate-for-auditability trade the CLI already makes with its own
four-file-per-feature shape — a reviewer never has to trace unrelated logic to
confirm one layer's responsibility.

**`trial_balance` has no Request Schema.** A trial balance is computed from persisted postings, never submitted, so there is no request body to validate. Its only input is one optional `as_of` query parameter, which FastAPI parses into a `datetime` before the route body runs. `mapper.py` still exists as the single place that normalizes that value before it reaches the handler; it returns the value unchanged today. `TrialBalanceResponse` extends `SuccessResponse`, so the standard `success`/`timestamp` envelope applies.

## Why `system` Is A Documented Exception To That Workflow

**Decision:** `api/features/system/` has only `router.py` and `schemas.py` — no
`mapper.py`, `handler.py`, or `presenter.py`.

**Why:** `GET /` and `GET /health` have no request body, construct no domain model,
and can raise no `AppError` to translate. A mapper that maps nothing, a handler that
calls no service, and a presenter that passes a value through unchanged would be
three files that exist purely to satisfy a template. `system`'s router docstring
names this explicitly so it is not mistaken for a starting point when a new feature
is scaffolded; a feature with a request body or a service dependency should follow
the full four-file shape from the start. Those two responses also skip the
`BaseResponse` envelope used everywhere else — see README.md Usage for the wire
shapes; the envelope decision below applies to domain and error bodies.

## Why `Container` Is Built Eagerly At Startup, Not Lazily Like `CliContext`

**Decision:** `bootstrap.build_container()` and `make_lifespan()` open the
PostgreSQL connection and construct every service exactly once, during the FastAPI
lifespan's startup phase — before the first request is served. This is the opposite
of `CliContext`'s lazy, per-invocation, per-accessor construction.

**Why:** A CLI invocation is short-lived and rewards laziness — `trutina account
--help` should never pay for a database connection it doesn't need. A long-running
API process has the opposite cost model: it will serve many requests, so the
connection and service graph are needed regardless, and paying that cost once at
startup means the first real request isn't the one that eats the connection latency.
`bootstrap.py`'s own module docstring states the accepted consequence: if the
initial PostgreSQL ping (performed inside `connect()`) fails, startup fails loudly
and the process never starts serving traffic, rather than starting "successfully"
and returning confusing per-request 500s. Process orchestration (systemd,
Kubernetes restart-with-backoff) owns retry policy — this module does not retry.
Table existence itself is not this module's concern either: schema is guaranteed by
Alembic migrations applied before the process starts (see
`trutina-storage-postgres`'s own `CONTEXT.md`), so `bootstrap.py` performs no
schema-registration step of its own.

## Why A Frozen `Container` Dataclass Rather Than App-Level Globals

**Decision:** `Container` (`composition/container.py`) is a frozen,
`slots=True` dataclass holding only `account_service`, `journal_service`, `posting_service`,
and `trial_balance_service`, attached once to `app.state.container`.

**Why:** Every attribute is stateless by design — concurrent requests calling the
same service concurrently is safe only because no service holds mutable,
request-specific state. Freezing the container makes that invariant structural
rather than a convention someone could accidentally violate by reassigning
`app.state.container.account_service` mid-process. Exposing only service attributes
— never a `PostgresConnection`, `PostgresExecutor`, or a `Postgres*Repo` — keeps
every route and dependency provider ignorant of the storage layer, mirroring
`CliContext`'s own refusal to leak storage-specific types past its accessors.
`trial_balance_service` depends on no other service.
It reads persisted postings through its own `TrialBalanceRepo`,
so `build_container()` constructs it independently of the account → journal → posting chain.

**Note for future contributors:** the day a service needs request-specific state (a
transactional session, an authenticated user's identity), this frozen-singleton
invariant has to be deliberately broken, not silently worked around with a mutable
attribute bolted onto `Container`.

## Why Per-Service Dependency Providers Instead Of Injecting The Whole Container

**Decision:** `composition/dependencies.py` exposes one provider function per service
(`get_account_service`, `get_journal_service`, `get_posting_service`, `get_trial_balance_service`),
each a one-line `request.app.state.container.<attr>` pass-through,
rather than a single `get_container()` provider that routes destructure themselves.

**Why:** FastAPI's `app.dependency_overrides` keys on the provider function object. A
single `get_container()` provider would force every test that wants to fake one
service to either fake the entire container or patch an attribute on a shared object
— both messier than `app.dependency_overrides[get_account_service] = lambda:
fake_service`, which the `override_service` test fixture relies on directly. Narrow
providers make narrow overrides possible.

## Why Response Envelope (`BaseResponse`/`SuccessResponse`/`ErrorResponse`) Wraps Every Body

**Decision:** Every domain success model and every error model inherits from
`BaseResponse` (`success: bool`, `timestamp: datetime`). `SuccessResponse` fixes
`success: Literal[True]`; `ErrorResponse` fixes `success: Literal[False]`. Example
bodies and field names are in README.md Usage.

**Why:** A client should never need to infer outcome from the HTTP status code alone
(which conflates transport-level and domain-level failure) nor from response shape
alone (which would require knowing, per endpoint, which fields indicate success). A
fixed `success` boolean, present in every domain and error response this API
returns, is a single, universal branch point. `ValidationErrorResponse` extends
`ErrorResponse` with a `details` array rather than putting an always-nullable
`details` field on the base — a plain not-found or conflict has nothing field-level
to report, and should not carry a field that is always `None`.

`system`'s identity and liveness bodies are the documented exception (see the
`system` section above): they are not domain outcomes, so they do not pretend to
carry the same branch point.

## Why The Error Catalog Lives In `api/shared/errors/`, Not `trutina-shared`

**Decision:** `api/shared/errors/catalog.py` (`ERROR_CATALOG: dict[ErrorCode,
ErrorCatalogEntry]`) maps every domain `ErrorCode` to an HTTP status code, a message
template, and an optional hint template — entirely separate from `trutina-shared`'s
`ErrorCode`/`AppError` model.

**Why:** This is the same boundary rule `trutina-shared`'s own `CONTEXT.md` states
for the CLI's error catalog: the shared error layer identifies _what_ went wrong
(`ErrorCode`); it never carries presentation text or transport-specific metadata (an
HTTP status code is exactly that). If HTTP status codes lived in `trutina-shared`,
every future presentation layer would either inherit HTTP semantics that don't apply
to it, or the shared layer would need parallel catalogs per transport. Keeping the
catalog here means the API can evolve its status-code and wording choices with zero
coordination cost against the CLI's own catalog.

## Why `register_exception_handlers()` Is Registered Once, Not Per-Route

**Decision:** `create_app()` calls `register_exception_handlers(app)` exactly once,
immediately after `FastAPI(...)` construction. No router or route function contains
its own `try`/`except`.

**Why:** This is the API's equivalent of the CLI's `error_boundary()` — a single,
narrow seam through which every domain and validation exception becomes a response,
so a presentation change (a new field on the error envelope, a new retry header) is
exactly one file to touch instead of N per-route try/except blocks drifting
independently. FastAPI's exception middleware dispatches by walking the _raised_
exception's MRO against the _registered_ class — `ValidationAppError` (a subclass of
`AppError`) must be registered so it is matched correctly regardless of registration
order, but the walk itself, not order, is what guarantees correct dispatch.

**Handler ordering, by contract, not convention:**

- `ValidationAppError` — 422, `details` populated from `.errors`.
- `AppError` (every other subclass, and the base class) — status/message/hint
  resolved from `ERROR_CATALOG` by `.code`, `.context` interpolated into both
  templates.
- `pydantic.ValidationError` — raised when a mapper constructs a domain object or
  Input DTO directly from already-schema-valid request data and a domain validator
  rejects it; uses the same field-violation translation path as `ValidationAppError`.
- `RequestValidationError` — FastAPI's own transport-level failure, raised before any
  router body runs; given the non-domain error code `"request.invalid"` rather than
  any `ErrorCode` member, since it never reached the domain layer.
- A final catch-all `Exception` handler, so no response can ever escape this app
  without the standard envelope shape.

## Why `FieldViolation.value` Recovery Exists In `handlers.py`

**Context:** `trutina-shared`'s `get_field_violations()` currently downgrades every
domain-raised `ErrorCode` to `ErrorCode.UNKNOWN_ERROR` on `FieldViolation.code`
(documented in `trutina-shared`'s own `CONTEXT.md` as a real, unresolved gap). Left
unhandled, every field-level validation message returned by this API would read "An
unexpected error occurred" instead of the real domain message.

**Why the API works around it here rather than waiting for the upstream fix:**
`_resolve_violation_entry()` in `handlers.py` recovers the real `ErrorCode` from
`FieldViolation.value` (which still carries the original domain code as a string)
before doing the catalog lookup. This mirrors the CLI's own identical recovery for
the identical reason. If `get_field_violations()` is ever fixed at the source, this
function becomes a harmless no-op — it should not be deleted silently without
confirming the upstream fix landed.

## Allowed and Forbidden Dependencies

**Allowed** (per `apps/api/pyproject.toml`): `trutina-core`, `trutina-storage-postgres`,
`trutina-config`, `fastapi[standard]`, `uvicorn[standard]`. Adjacent-package READMEs
are listed in this package's README.md See Also.

**Forbidden:** `trutina-cli`, or any other `apps/*` package. Nothing here should
import `sqlalchemy`/`asyncpg` directly outside of `composition/bootstrap.py`, which is
the one module permitted to see `PostgresConnection`/`PostgresExecutor`/
`Postgres*Repo` types — routes, dependency providers, and `app.py` see only
`Container`'s service attributes.

**Direction:** enforced by the workspace's root `pyproject.toml` import-linter
`layers` contract (`trutina.cli | trutina.api → trutina.storage_mongo →
trutina.core → trutina.shared | trutina.config`). This package sits at the top beside
the CLI; nothing downstream may import from it. **Flag:** the root contract's middle
layer is still named `trutina.storage_mongo`, even though this package's own
`pyproject.toml` now declares `trutina-storage-postgres` as its storage dependency,
not `trutina-storage-mongo`. Whether that's a stale layer name in the root contract
or an intentional generic role-name is outside this package's own docs to resolve —
flagged for the root-level contract to confirm, not silently corrected here.

## Layering Within This Package

```text
api.composition.app.create_app()
  -> api.composition.bootstrap.make_lifespan()   -> Container (once, at startup)
  -> api.shared.errors.register_exception_handlers()
  -> api.features.*.router
       -> Request Schema (schemas.py)
       -> mapper.py            -> Input DTO (trutina-core)
       -> Depends(get_*_service) -> composition.dependencies
       -> handler.py            -> trutina-core service
       -> presenter.py           -> Response Schema (schemas.py)
```

Within `api/shared/`, `response.py` sits below `errors/` — `errors/schemas.py`'s
`ErrorResponse` extends `response.py`'s `BaseResponse`, never the reverse.
`errors/catalog.py` and `errors/schemas.py` have no dependency on each other beyond
both being read by `errors/handlers.py`, the only module that combines catalog
lookup, response construction, and FastAPI's `add_exception_handler` registration.

No import-linter contract currently enforces this sub-layering mechanically (only
the workspace-level `apps → infrastructure → core → shared/config` contract is
checked in CI) — it is observed convention in the current source, flagged here
rather than described as enforced, mirroring the same caveat in `trutina-cli`'s own
`CONTEXT.md`.

## Control Flow

```text
Process starts
  -> main() / uvicorn -> create_app(settings)
      -> FastAPI(...) constructed
      -> register_exception_handlers(app)
      -> five routers included (system, account, journal, posting, trial_balance)
      -> lifespan = make_lifespan(settings), not yet entered
  -> uvicorn enters the lifespan
      -> connect(settings.postgres)  -- verified via ping; failure aborts startup
      -> app.state.container = build_container(connection)
      -> (yield -- app now serves requests)
  -> per request:
      -> router resolves Depends(get_*_service) -> Container attribute
      -> mapper -> handler -> service -> presenter
      -> success: Response Schema serialized, standard envelope
      -> failure: exception propagates uncaught to the registered handler
         -> JSON error envelope, correct HTTP status
  -> process shutdown
      -> lifespan's finally: disconnect(connection)
```

Entry points, bind address, and HTTP paths are in README.md Quick Start / API at a
Glance. Table/schema existence is a precondition of this flow, not a step in it —
Alembic migrations are applied out-of-band before the process starts (see
`trutina-storage-postgres`'s own `CONTEXT.md`); `bootstrap.py` never creates or alters
schema itself.

## Data Flow

See README.md's "API at a Glance" and "Usage" for routes, request bodies, and
envelope fields. At the layer level: a router receives a `Request` plus a
FastAPI-validated Request Schema instance (or nothing, for `system`); a mapper turns
that into an Input DTO (pure, no I/O); a handler calls exactly one service method and
returns a ViewModel or propagates `AppError`/`ValidationAppError`; a presenter turns a
ViewModel into a Response Schema (pure, no I/O); an exception handler turns whatever
propagated out of a route into a `JSONResponse` built from
`.model_dump(mode="json")` — never the bare `.model_dump()`, since
`BaseResponse.timestamp` is a `datetime` with no default JSON encoder in Starlette's
`JSONResponse`.

## Extension Points

- **A new feature router** — mirrors `account`/`journal`/`posting` exactly; see
  README.md's API at a Glance and the `Trutina API Feature & Testing Prompt` for
  the full step-by-step.
- **A new `Container` service** — add the attribute to `Container`, wire it in
  `build_container()` exactly the way `PostingService` is wired to `JournalService`,
  and add a matching provider in `dependencies.py`.
- **New error presentation** — add or edit an `ErrorCatalogEntry` in `catalog.py`,
  keyed by `ErrorCode`. Never add HTTP-specific metadata to `trutina-shared`.
- **New response envelope shape** — extend `BaseResponse`/`SuccessResponse`/
  `ErrorResponse`, never introduce a parallel, uncoordinated response base for a
  single feature.

## Assumptions This Package Relies On

- **`trutina-core` services are the only source of business validation.** This
  package assumes every `AppError`/`ValidationAppError` it might catch originates
  from a real `trutina-core` service or DTO/domain construction.
- **Exactly one `Container` per process**, constructed once during startup and never
  rebuilt mid-process. No route or dependency provider may construct a service or
  repository directly.
- **`Container`'s services are safe under concurrent request handling** because they
  are stateless. This assumption breaks the day a service gains request-scoped
  mutable state (see the `Container` section above).
- **The database schema already matches what `Postgres*Repo` expects when
  `bootstrap.py` runs.** Alembic migration history is applied before this process
  starts (mirrored in tests by `tests/fixtures/postgres.py`'s `schema_init`, which
  runs the real migration history once per test session) — `bootstrap.py` performs
  no schema creation and will surface a mismatch only as a query-time failure, not a
  startup-time one.
- **Every `ErrorCode` the domain can raise has a matching `ERROR_CATALOG` entry.** A
  new code added upstream without a matching entry degrades to a generic `500` via
  `DEFAULT_ERROR_ENTRY` rather than crashing the handler — presentation degradation,
  not a test failure, and must be checked manually when `trutina-shared`'s
  `ErrorCode` enum changes.

## Known Gaps / Flags

- **`_fill()` in `shared/errors/handlers.py` uses `except KeyError, IndexError:`**,
  which is not valid Python 3 exception-handling syntax (`except (KeyError,
IndexError):` is required). **Confirmed against live source in this pass** — this is
  a live syntax defect, not an artifact of how the source was previously captured,
  and would raise `SyntaxError` at import time as written. This resolves the prior
  version of this document's open flag on the same question; it is no longer
  "unconfirmed."
- **The root workspace's import-linter `layers` contract still names its storage
  layer `trutina.storage_mongo`**, while this package's own `pyproject.toml` depends
  on `trutina-storage-postgres`. See the "Allowed and Forbidden Dependencies"
  section above — flagged here, not resolved, since the root contract is outside
  this package's own docs.
- **`GET /trial-balance?as_of=` accepts any datetime, while `postings.posting_date` is a naive (timezone-unaware) timestamp.**
  What happens when a timezone-aware value, such as one ending in `Z`, is supplied has not been tested. It may fail at the database comparison instead of returning a report.
- **`as_of` is not validated beyond being a parseable datetime.** A future value includes every posting, and a value before the earliest posting yields an empty `entries` list. An unparseable value is rejected with a 422 by FastAPI.

## Common Mistakes to Avoid

- Adding business logic, exception handling, or a domain-model construction call
  inside a router function. A router's only job is wiring mapper -> handler ->
  presenter behind `Depends(...)`.
- Reaching for a real PostgreSQL type (`PostgresConnection`, `PostgresExecutor`, a
  `Postgres*Repo`) anywhere outside `composition/bootstrap.py`.
- Constructing `Container` or calling `build_container()` inside a route or a
  dependency provider "to save a round trip."
- Copying `system`'s flat router shape for a feature that has a request body or a
  domain error to translate.
- Bypassing `register_exception_handlers()` with a local `try`/`except AppError`
  inside a route. If a route needs different error handling than the shared catalog
  provides, that's a sign the catalog needs a new entry, not a local workaround.
- Assuming a schema change is picked up automatically. `bootstrap.py` creates no
  tables and applies no migrations itself — a new column or table needs a real
  Alembic migration in `trutina-storage-postgres`, applied before the process starts,
  or the failure surfaces only the first time the affected query runs.
- Assuming `trutina-shared`'s `ErrorCode` message belongs in this package's catalog
  by inheritance — every `ErrorCode` needs its own `ERROR_CATALOG` entry here.
