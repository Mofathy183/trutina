# trutina-api

The HTTP presentation layer for Trutina: a FastAPI application exposing the same
double-entry accounting domain (`trutina-core`) that `trutina-cli` exposes over the
terminal.

## What Is This

`trutina-api` (import path `trutina.api`) is one of two presentation layers over
`trutina-core`, the other being `trutina-cli`. No accounting rules live here — this
package translates HTTP requests into service calls and service results into JSON
responses. It owns:

- The FastAPI application factory and composition root (`api/composition/`).
- One feature package per resource — `account`, `journal`, `posting`, and `system`
  (`api/features/`) — each following the same fixed request pipeline:

```text
  HTTP Request -> Router -> Request Schema -> Mapper -> Input DTO -> Handler
    -> Service -> ViewModel -> Presenter -> Response Schema -> HTTP Response
```

A route function resolves the mapper, calls the handler via
`Depends(get_<feature>_service)`, resolves the presenter, and returns. No route
contains business logic, constructs a domain model, or catches
`AppError`/`ValidationAppError` — those propagate uncaught to the exception
handlers registered once in `create_app()`. `system` (`GET /`, `GET /health`) is a
documented flat exception with no `mapper.py`/`handler.py`/`presenter.py` — see
`CONTEXT.md` for why, and don't copy its shape for a feature with a request body.

- The shared response envelope and the error-to-HTTP translation catalog
  (`api/shared/`).

## Installation

Within the workspace:

```bash
uv sync --package trutina-api
```

## Public API

| Symbol                                                                                        | Module                         | Purpose                                                                                                                             |
| --------------------------------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `create_app(settings: Settings \| None = None) -> FastAPI`                                    | `trutina.api.composition`      | Application factory; falls back to `get_settings()` when no settings are passed.                                                    |
| `make_lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]` | `trutina.api.composition`      | Builds the startup/shutdown sequence (`connect` → `init_beanie` → `build_container` → `disconnect`) bound to a specific `Settings`. |
| `build_container() -> Container`                                                              | `trutina.api.composition`      | Pure, I/O-free construction of the singleton service graph.                                                                         |
| `Container`                                                                                   | `trutina.api.composition`      | Frozen dataclass holding `account_service`, `journal_service`, `posting_service`.                                                   |
| `app`                                                                                         | `trutina.api.composition.app`  | Module-level `FastAPI` instance (`create_app()` called with no arguments).                                                          |
| `main() -> None`                                                                              | `trutina.api.main`             | Console-script entry point (`trutina-api`); resolves `Settings` and calls `uvicorn.run(...)`.                                       |
| `router`                                                                                      | `trutina.api.features.account` | `APIRouter` for `/accounts` (create/list/get/update/delete).                                                                        |
| `router`                                                                                      | `trutina.api.features.journal` | `APIRouter` for `/journal-entries` (create/list/get).                                                                               |
| `router`                                                                                      | `trutina.api.features.posting` | `APIRouter` for `/postings` (post/get-by-account/get-by-journal).                                                                   |
| `router`                                                                                      | `trutina.api.features.system`  | `APIRouter` for `GET /` and `GET /health`.                                                                                          |
| `BaseResponse`, `SuccessResponse`                                                             | `trutina.api.shared.response`  | Common envelope fields (`success`, `timestamp`); every feature response extends one of these.                                       |
| `ErrorResponse`, `ValidationErrorResponse`                                                    | `trutina.api.shared.errors`    | Error envelope schemas; the latter adds `details` for field-level failures.                                                         |
| `ERROR_CATALOG`                                                                               | `trutina.api.shared.errors`    | `dict[ErrorCode, ErrorCatalogEntry]` mapping domain codes to HTTP status/message/hint.                                              |
| `register_exception_handlers(app: FastAPI) -> None`                                           | `trutina.api.shared.errors`    | Registers all five exception handlers on a FastAPI app; called once from `create_app()`.                                            |

Per-service dependency providers (`get_account_service`, `get_journal_service`,
`get_posting_service`, `get_settings_dep`) live in `api/composition/dependencies.py`
and are consumed via `Depends(...)` inside routers rather than imported directly by
callers outside this package.

## Usage

### Running locally

```bash
uv run --package trutina-api uvicorn trutina.api.composition.app:app --reload
```

or via the installed console script:

```bash
uv run trutina-api
```

Interactive docs: `/docs`. Raw OpenAPI schema: `/openapi.json`.

### Example requests

```bash
curl -X POST http://localhost:8000/accounts \
  -H "content-type: application/json" \
  -d '{"code": "1001", "name": "Cash", "category": "ASSET"}'

curl -X POST http://localhost:8000/journal-entries \
  -H "content-type: application/json" \
  -d '{
        "posting_date": "2025-01-01T00:00:00",
        "lines": [
          {"account": "Cash", "debit_amount": "100", "credit_amount": "0"},
          {"account": "Sales Revenue", "debit_amount": "0", "credit_amount": "100"}
        ]
      }'

curl -X POST http://localhost:8000/postings/1

curl http://localhost:8000/postings/by-account/Cash
curl http://localhost:8000/postings/by-journal/1
```

### Response envelope

Every JSON body carries `success: bool` and `timestamp: datetime`:

```json
{
    "success": true,
    "timestamp": "2026-07-14T12:00:00Z",
    "account": {
      "code": "1001",
      "name": "Cash",
      "category": "ASSET",
      "normal_balance": "debit"
    }
}
```

Error responses (`success: false`) additionally carry `error_code`, `message`, an
optional `hint`, and — for validation failures — a `details` array:

```json
{
    "success": false,
    "timestamp": "2026-07-14T12:00:00Z",
    "error_code": "account.unknown",
    "message": "No account was found for '9999'.",
    "hint": "Verify the account code or name, or create it first via POST /accounts."
}
```

Every domain `ErrorCode` currently raised anywhere in Trutina has a status/message/
hint entry in `api/shared/errors/catalog.py`; anything without an entry falls back to
a generic `500` rather than raising inside the handler itself.

## Integration

```text
apps/cli, apps/api          <- you are here
        │
        ▼
trutina-storage-mongo     (Mongo* repos)
        │
        ▼
trutina-core                (AccountService, JournalService, PostingService)
        │
        ▼
trutina-shared, trutina-config
```

Depends on (per `apps/api/pyproject.toml`): `trutina-core`, `trutina-storage-mongo`,
`trutina-config`, `fastapi[standard]`, `uvicorn[standard]`. Never imports
`trutina-cli`, or any other `apps/*` package — enforced by the workspace's `layers`
import-linter contract (`trutina.cli | trutina.api → trutina.storage_mongo →
trutina.core → trutina.shared | trutina.config`).

## Extending

Adding a new feature (e.g. a future `reporting` resource):

1. **Create the feature folder** — `api/features/<name>/`, exporting `router` from
   an `__init__.py`.
2. **Define request/response schemas** (`schemas.py`) — mirror the corresponding
   `trutina-core` DTO/ViewModel field-for-field where shapes naturally match, kept as
   distinct classes so the HTTP contract can evolve independently.
3. **Write the mapper** (`mapper.py`) — pure, synchronous, no I/O: Request Schema ->
   Input DTO. No business validation; that fires inside the service.
4. **Write the handler** (`handler.py`) — one `async def` per operation, each exactly
   one service call, no FastAPI import, no exception handling.
5. **Write the presenter** (`presenter.py`) — pure, synchronous: ViewModel -> Response
   Schema.
6. **Write the router** (`router.py`) — wire mapper -> `Depends(get_*_service)` ->
   handler -> presenter, one function per operation.
7. **Add a dependency provider** in `composition/dependencies.py` if the feature needs
   a service not already exposed, and add the service to `Container`
   (`composition/container.py`) and `build_container()` (`composition/bootstrap.py`).
8. **Register the router** in `composition/app.py::create_app()`.
9. **Add tests** mirroring an existing feature: `test_mapper.py`, `test_handler.py`,
   `test_presenter.py`, `test_router_unit.py` (fake-backed), `test_router_integration.py`
   (real MongoDB).

## Testing

Two tiers, mirroring the CLI's fake/real fixture split (`tests/fixtures/api.py`):

- **Unit tier** (`@pytest.mark.unit`) — `api_app`/`api_client` built via `create_app()`
  with a `fake_container` (every service backed by a `Fake*Repo`) attached directly to
  `app.state.container`. The real lifespan is never entered.
- **Integration tier** (`@pytest.mark.integration`) — `real_api_app`/`real_api_client`
  enter the real lifespan (`bootstrap.make_lifespan()`) against `TestSettings`, backed
  by `clean_db`.

```bash
uv run pytest -m "unit and api"
uv run pytest -m "integration and api"
```
