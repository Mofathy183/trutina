# trutina-config

> Typed, environment-driven configuration for Trutina's Mongo, PostgreSQL, and API layers.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-config-informational)

## Quick Start

```bash
uv sync --package trutina-config
```

```python
from trutina.config import get_settings

settings = get_settings()
print(settings.postgres.uri)
```

## What This Is

`trutina-config` (import path `trutina.config`) is the strongly typed settings
surface every Trutina application and storage adapter reads its configuration
from — a MongoDB connection, a PostgreSQL connection, API bind settings —
instead of each one reading `os.environ` directly. It sits at the root of the
workspace dependency graph: every other package may depend on it, and it
depends on nothing else in the workspace. See [CONTEXT.md](CONTEXT.md) for why
it's shaped this way.

## API at a Glance

| Symbol                       | Purpose                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------- |
| `Settings`                   | Root production configuration model. Loads from `TRUTINA_`-prefixed env vars and `.env`. |
| `TestSettings`               | `Settings` subclass. Loads from `TRUTINA_TEST_`-prefixed env vars and `.env.test`.       |
| `MongoSettings`              | Nested MongoDB connection settings.                                                      |
| `PostgresSettings`           | Nested PostgreSQL connection settings (SQLAlchemy async URI, pool sizing).               |
| `ApiSettings`                | Nested API-layer settings (host, port, reload, OpenAPI metadata).                        |
| `get_settings() -> Settings` | `lru_cache`-wrapped accessor returning a cached `Settings` instance.                     |

### `MongoSettings` fields

| Field                          | Default                     | Description                                            |
| ------------------------------ | --------------------------- | ------------------------------------------------------ |
| `uri`                          | `mongodb://localhost:27017` | MongoDB connection URI.                                |
| `db`                           | `trutina`                   | Database name.                                         |
| `server_selection_timeout_ms`  | `5000`                      | Max time (ms) to wait for MongoDB server selection.    |
| `min_pool_size`                | `1`                         | Minimum connections maintained in the connection pool. |
| `retry_reads` / `retry_writes` | `True`                      | Whether retryable reads/writes are enabled.            |

### `PostgresSettings` fields

| Field               | Default                                       | Description                                                       |
| ------------------- | --------------------------------------------- | ----------------------------------------------------------------- |
| `uri`               | `postgresql+asyncpg://localhost:5432/trutina` | SQLAlchemy async connection URI (path carries the DB name).       |
| `connect_timeout_s` | `5.0`                                         | Max seconds to wait for a new connection before raising.          |
| `pool_size`         | `1`                                           | Minimum connections SQLAlchemy's pool keeps open.                 |
| `max_overflow`      | `10`                                          | Additional connections allowed above `pool_size` under load.      |
| `pool_pre_ping`     | `True`                                        | Liveness-check a pooled connection before handing it to a caller. |

### `ApiSettings` fields

| Field           | Default              | Description                                          |
| --------------- | -------------------- | ---------------------------------------------------- |
| `title`         | `Trutina API`        | Title shown in the OpenAPI schema.                   |
| `version`       | `0.1.0`              | API version string.                                  |
| `host` / `port` | `127.0.0.1` / `8000` | Interface and port the API server binds to.          |
| `reload`        | `False`              | Enable uvicorn auto-reload (local development only). |

## Usage

```python
from trutina.config import get_settings

settings = get_settings()
settings.mongo.uri
settings.postgres.uri
settings.api.port
```

For an isolated instance instead of the cached singleton:

```python
from trutina.config import Settings, PostgresSettings

settings = Settings(
    postgres=PostgresSettings(uri="postgresql+asyncpg://localhost:5432/trutina")
)
```

For tests, use `TestSettings()` directly to read the `TRUTINA_TEST_` namespace
and `.env.test` instead of the production namespace.

### Environment variables

Nested settings use a double underscore (`__`) as the delimiter:

```bash
TRUTINA_MONGO__URI=mongodb://localhost:27017
TRUTINA_POSTGRES__URI=postgresql+asyncpg://username:password@localhost:5432/trutina
TRUTINA_API__PORT=8000
```

Test configuration reads the same shape under a `TRUTINA_TEST_` prefix from
`.env.test`. See `.env.example` and `.env.test.example` at the repo root for
the full set of currently supported keys.

## Testing

```bash
uv run pytest -m "unit and config"
```

The `config` layer marker is auto-derived from file path by the root
`conftest.py` — only the `unit`/`integration` speed marker needs to be
written on the test itself.

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants.
- Confirmed direct dependents (per their own `pyproject.toml`): `trutina-storage-mongo`,
  `trutina-cli`, `trutina-api`. `trutina-storage-postgres` almost certainly
  depends on this package too (`PostgresSettings`' own docstring names it as
  the consumer of these fields), but its `pyproject.toml` wasn't available to
  confirm directly in this pass — flag before relying on it.
- `trutina-config` depends on nothing else in the workspace.
