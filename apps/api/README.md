# trutina-api

> A FastAPI HTTP presentation layer over Trutina's double-entry accounting domain.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-api-informational)

## Quick Start

```bash
uv sync --package trutina-api
uv run trutina-api
curl http://127.0.0.1:8000/health
```

`trutina-api` binds to `127.0.0.1:8000` by default (`trutina.config.ApiSettings`). Startup opens PostgreSQL using `Settings.postgres`; apply migrations from `trutina-storage-postgres` before the process will serve requests.

## What This Is

`trutina-api` (import path `trutina.api`) is the HTTP presentation layer over `trutina-core`, sibling to `trutina-cli`. It turns HTTP requests into service calls and service results into JSON; accounting rules stay in `trutina-core` and persistence in `trutina-storage-postgres`. See [CONTEXT.md](CONTEXT.md) for why it's shaped this way.

## API at a Glance

| Symbol                                 | Purpose                                                                                                              |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `GET /`, `GET /health`                 | Process identity and liveness. These two bodies are not the success/error envelope.                                  |
| `/accounts`                            | `POST` (201), `GET` list, `GET`/`PATCH`/`DELETE /{code}`.                                                            |
| `/journal-entries`                     | `POST` (201), `GET` list, `GET /{journal_number}`.                                                                   |
| `/postings`                            | `POST /{journal_number}` (201); `GET /by-account/{account}`; `GET /by-journal/{journal_number}`.                     |
| `/trial-balance`                       | `GET` only. Optional `as_of` datetime query parameter; omitted means all time.                                       |
| `create_app(settings=None) -> FastAPI` | Application factory; uses `get_settings()` when `settings` is omitted.                                               |
| `app`                                  | Module-level `FastAPI` instance from `create_app()` with no arguments.                                               |
| `main() -> None`                       | Console-script entry (`trutina-api`); runs uvicorn against `trutina.api.composition.app:app`.                        |
| `Container`                            | Frozen dataclass of `account_service`, `journal_service`, `posting_service`, `trial_balance_service` on `app.state`. |

`make_lifespan`, `build_container`, `register_exception_handlers`, `ERROR_CATALOG`, and the `get_*_service` providers live under `trutina.api.composition` and `trutina.api.shared.errors`. Route modules are `trutina.api.features.{system,account,journal,posting,trial_balance}`.

## Usage

Reload during local work (same ASGI target `main()` uses):

```bash
uv run --package trutina-api uvicorn trutina.api.composition.app:app --reload
```

Interactive docs: `/docs`. Raw OpenAPI schema: `/openapi.json`.

Create two accounts, a balanced journal entry, then post it:

```bash
curl -X POST http://127.0.0.1:8000/accounts \
  -H "content-type: application/json" \
  -d '{"code": "1001", "name": "Cash", "category": "ASSET"}'

curl -X POST http://127.0.0.1:8000/accounts \
  -H "content-type: application/json" \
  -d '{"code": "4001", "name": "Sales Revenue", "category": "REVENUE"}'

curl -X POST http://127.0.0.1:8000/journal-entries \
  -H "content-type: application/json" \
  -d '{
        "posting_date": "2025-01-01T00:00:00",
        "lines": [
          {"account": "Cash", "debit_amount": "100", "credit_amount": "0"},
          {"account": "Sales Revenue", "debit_amount": "0", "credit_amount": "100"}
        ]
      }'

curl -X POST http://127.0.0.1:8000/postings/1
```

Read the trial balance of everything posted so far, or only postings recorded on or before a cutoff:

```bash
curl http://127.0.0.1:8000/trial-balance
curl "http://127.0.0.1:8000/trial-balance?as_of=2025-06-30T00:00:00"
```

The response carries `entries` (one `{account, debit_total, credit_total}` item per account with postings in scope), `as_of_date` (`null` for all time), `total_debits`, `total_credits`, and `is_balanced`, plus the standard `success` and `timestamp`. `entries` is an empty list, not an error, when nothing is in scope. Only posted journal entries count. An unparseable `as_of` returns a 422 validation error.

Account, journal, posting, and trial balance success bodies, and every error body, carry `success` and `timestamp`. Error bodies also carry `error_code`, `message`, an optional `hint`, and — on validation failures — `details`. `GET /` and `GET /health` do not use that envelope.

## Testing

```bash
uv run pytest -m "unit and api"
uv run pytest -m "integration and api"   # requires PostgreSQL
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants, known gaps.
- [`trutina-core`](../../packages/core/README.md) — domain services this package presents over HTTP.
- [`trutina-storage-postgres`](../../packages/storage-postgres/README.md) — repository implementations `bootstrap.py` wires into `Container`.
- [`trutina-config`](../../packages/config/README.md) — `PostgresSettings` and `ApiSettings` used by `connect()` and `create_app()`.
