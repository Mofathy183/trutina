# trutina-config

Typed, environment-driven configuration for Trutina.

## What Is This

`trutina-config` (import path `trutina.config`) is the strongly typed
settings surface every Trutina application and storage adapter reads its
configuration from — a Mongo connection, API bind settings — instead of
each one reading `os.environ` directly. It sits at the root of the
workspace dependency graph: every other package may depend on it, and it
depends on nothing else in the workspace.

## Public API

Everything below is re-exported from `trutina.config`:

| Symbol                       | Purpose                                                                                                                                 |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `Settings`                   | Root production configuration model. Loads from `TRUTINA_`-prefixed env vars and `.env`.                                                |
| `TestSettings`               | `Settings` subclass. Loads from `TRUTINA_TEST_`-prefixed env vars and `.env.test`, keeping test configuration isolated from production. |
| `MongoSettings`              | Nested MongoDB connection settings.                                                                                                     |
| `ApiSettings`                | Nested API-layer settings (host, port, reload, OpenAPI metadata).                                                                       |
| `get_settings() -> Settings` | `lru_cache`-wrapped accessor returning a cached `Settings` instance.                                                                    |

### `MongoSettings` fields

| Field                         | Default                     | Description                                            |
| ----------------------------- | --------------------------- | ------------------------------------------------------ |
| `uri`                         | `mongodb://localhost:27017` | MongoDB connection URI.                                |
| `db`                          | `trutina`                   | Database name.                                         |
| `server_selection_timeout_ms` | `5000`                      | Max time (ms) to wait for MongoDB server selection.    |
| `min_pool_size`               | `1`                         | Minimum connections maintained in the connection pool. |
| `retry_reads`                 | `True`                      | Whether retryable reads are enabled.                   |
| `retry_writes`                | `True`                      | Whether retryable writes are enabled.                  |

### `ApiSettings` fields

| Field         | Default                                       | Description                                          |
| ------------- | --------------------------------------------- | ---------------------------------------------------- |
| `title`       | `Trutina API`                                 | Title shown in the OpenAPI schema.                   |
| `version`     | `0.1.0`                                       | API version string.                                  |
| `description` | `REST API for the Trutina accounting engine.` | Description shown in the OpenAPI schema.             |
| `host`        | `127.0.0.1`                                   | Host interface the API server binds to.              |
| `port`        | `8000`                                        | Port the API server listens on.                      |
| `reload`      | `False`                                       | Enable uvicorn auto-reload (local development only). |

## Installation

Within the workspace, add it as a dependency in your package's
`pyproject.toml`:

```toml
dependencies = ["trutina-config"]

[tool.uv.sources]
trutina-config = { workspace = true }
```

## Usage

```python
from trutina.config import get_settings

settings = get_settings()
print(settings.mongo.uri)
print(settings.api.port)
```

For an isolated instance instead of the cached singleton (e.g. to pass
explicit values):

```python
from trutina.config import Settings, MongoSettings

settings = Settings(mongo=MongoSettings(uri="mongodb://localhost:27017"))
```

### Environment variables

Production configuration reads `TRUTINA_`-prefixed variables and an
optional `.env` file at the repo root. Nested settings use a double
underscore (`__`) as the delimiter:

```bash
TRUTINA_MONGO__URI=mongodb://localhost:27017
TRUTINA_MONGO__DB=trutina
TRUTINA_MONGO__SERVER_SELECTION_TIMEOUT_MS=5000
TRUTINA_MONGO__MIN_POOL_SIZE=1
TRUTINA_MONGO__RETRY_READS=true
TRUTINA_MONGO__RETRY_WRITES=true

TRUTINA_API__HOST=127.0.0.1
TRUTINA_API__PORT=8000
TRUTINA_API__RELOAD=true
```

Test configuration reads the same shape under a `TRUTINA_TEST_` prefix
from `.env.test`:

```bash
TRUTINA_TEST_MONGO__URI=mongodb://localhost:27017
TRUTINA_TEST_MONGO__DB=trutina_test
```

See `.env.example` and `.env.test.example` at the repo root for the full
set of currently supported keys.

## Integration

- `trutina-storage-mongo` accepts a `MongoSettings` instance directly
  (never calls `get_settings()` itself).
- `trutina-cli` and `trutina-api` each call `get_settings()` at their own
  composition root and pass the nested settings down to whatever needs
  them.
- `trutina-config` imports nothing from any other `trutina-*` package —
  confirmed via `pyproject.toml`, which lists only `pydantic` and
  `pydantic-settings` as dependencies.
- Confirmed dependents, per their own `pyproject.toml`: `trutina-cli`,
  `trutina-api`, `trutina-storage-mongo`. `trutina-core` does not depend
  on this package.

## Extending

Adding a new settings group (e.g. a future `WorkerSettings`):

1. Add a new `BaseModel` (not `BaseSettings`) in its own file, following
   `mongo.py`/`api.py`'s shape — plain `Field(...)` defaults with
   descriptions, no env-loading logic of its own.
2. Add it as a field on `Settings` in `base.py` with a `default_factory`.
3. Re-export it from `__init__.py`.

Do not give a nested settings model its own `BaseSettings`/
`SettingsConfigDict` — only `Settings`/`TestSettings` own the env-prefix
and dotenv-file configuration.

## Testing

- Use `TestSettings()` directly for a settings instance that reads the
  `TRUTINA_TEST_` namespace and `.env.test`.
- If a test mutates environment variables that affect settings, clear
  `get_settings`'s cache before and after — the shared
  `isolate_settings_cache` autouse fixture (root `tests/fixtures/settings.py`)
  already does this for every test in the suite.
- Run this package's unit tests with the `shared` layer marker (auto-derived
  from file path by the root `conftest.py`, since `config/` maps to the
  `shared` layer):

```bash
uv run pytest -m "unit and shared"
```
