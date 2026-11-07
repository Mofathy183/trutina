# trutina-config

> Typed, environment-driven configuration for Trutina's PostgreSQL, API, and logging layers.

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
from — a PostgreSQL connection, API bind settings, and
the logging pipeline's own settings — instead of each one reading `os.environ`
directly. It sits at the root of the workspace dependency graph: every other
package may depend on it, and it depends on nothing else in the workspace. See
[CONTEXT.md](CONTEXT.md) for why it's shaped this way.

## API at a Glance

| Symbol                       | Purpose                                                                                                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Settings`                   | Root production configuration model. Loads from `TRUTINA_`-prefixed env vars and `.env`.                                                                                                 |
| `TestSettings`               | `Settings` subclass. Loads from `TRUTINA_TEST_`-prefixed env vars and `.env.test`.                                                                                                       |
| `PostgresSettings`           | Nested PostgreSQL connection settings (SQLAlchemy async URI, pool sizing).                                                                                                               |
| `ApiSettings`                | Nested API-layer settings (host, port, reload, OpenAPI metadata).                                                                                                                        |
| `LoggingSettings`            | Nested logging-pipeline settings, consumed by `trutina-observability`'s `configure_logging()`.                                                                                           |
| `AuthSettings`               | Nested authentication settings: session lifetimes, the re-authentication window, trusted proxies, password-hashing cost and concurrency, and login-throttle limits. No app reads it yet. |
| `get_settings() -> Settings` | `lru_cache`-wrapped accessor returning a cached `Settings` instance.                                                                                                                     |

### `PostgresSettings` fields

| Field               | Default                                       | Description                                                                                                                 |
| ------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `uri`               | `postgresql+asyncpg://localhost:5432/trutina` | SQLAlchemy async connection URI (path carries the DB name).                                                                 |
| `connect_timeout_s` | `5.0`                                         | Max seconds to wait for a new connection before raising.                                                                    |
| `pool_timeout_s`    | `5.0`                                         | Max seconds a caller waits for a pooled connection. Must be greater than 0. Declared only: the engine does not read it yet. |
| `pool_size`         | `1`                                           | Minimum connections SQLAlchemy's pool keeps open.                                                                           |
| `max_overflow`      | `10`                                          | Additional connections allowed above `pool_size` under load.                                                                |
| `pool_pre_ping`     | `True`                                        | Liveness-check a pooled connection before handing it to a caller.                                                           |

### `ApiSettings` fields

| Field           | Default              | Description                                          |
| --------------- | -------------------- | ---------------------------------------------------- |
| `title`         | `Trutina API`        | Title shown in the OpenAPI schema.                   |
| `version`       | `0.1.0`              | API version string.                                  |
| `host` / `port` | `127.0.0.1` / `8000` | Interface and port the API server binds to.          |
| `reload`        | `False`              | Enable uvicorn auto-reload (local development only). |

### `LoggingSettings` fields

| Field               | Default                           | Description                                                                                                                                                                                       |
| ------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `level`             | `INFO`                            | Root logger's minimum level. Case-insensitive on input; normalized to upper-case.                                                                                                                 |
| `format`            | `auto`                            | `json`, `console`, or `auto` (resolves per app/tty at configure time — see `trutina-observability`).                                                                                              |
| `sink`              | `auto`                            | `stdout`, `stderr`, `file`, or `auto` (API defaults to stdout, CLI to a rotating file).                                                                                                           |
| `file_path`         | `None`                            | Destination path when `sink` resolves to `file`. `None` lets `configure_logging()` pick a platform log directory. Accepts a `pathlib.Path` — coerced to `str` before validation (see CONTEXT.md). |
| `file_max_bytes`    | `5_000_000`                       | Rotation threshold in bytes. Must be positive.                                                                                                                                                    |
| `file_backup_count` | `3`                               | Rotated backups retained. `0` is valid (no backups); negative is rejected.                                                                                                                        |
| `logger_levels`     | third-party defaults (see source) | Per-logger level overrides, keyed by logger name. Overriding from the environment replaces the whole mapping, not a per-key merge.                                                                |

`LoggingSettings` itself performs no logging setup — it only describes shape.
`trutina-observability`'s `configure_logging()` is its only consumer.

### `AuthSettings` fields

| Field                            | Default | Description                                                                                                                                                              |
| -------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `password_time_cost`             | `3`     | Argon2id iterations. Minimum 1.                                                                                                                                          |
| `password_memory_cost_kib`       | `65536` | Argon2id memory per hash in KiB (64 MiB). Minimum 8, and at least 8 times `password_parallelism`.                                                                        |
| `password_parallelism`           | `1`     | Argon2id lanes per hash. Minimum 1.                                                                                                                                      |
| `password_hash_concurrency`      | `4`     | Maximum concurrent password hashes per process. Minimum 1. Peak hashing memory is about this times `password_memory_cost_kib`.                                           |
| `login_max_failures`             | 5       | Failed logins per client IP and email, within the window, before further attempts are throttled. Minimum 1.                                                              |
| `login_window_seconds`           | 900     | Failed-login window in seconds, also the retry delay reported when throttled. Minimum 1.                                                                                 |
| `session_api_idle_hours`         | `24`    | Hours an `api` session may sit unused before it expires. Minimum 1.                                                                                                      |
| `session_api_absolute_days`      | `7`     | Days an `api` session lives from creation, however active. Minimum 1.                                                                                                    |
| `session_cli_idle_days`          | `14`    | Days a `cli` session may sit unused before it expires. Minimum 1.                                                                                                        |
| `session_cli_absolute_days`      | `30`    | Days a `cli` session lives from creation, however active. Minimum 1.                                                                                                     |
| `session_touch_interval_seconds` | `300`   | Minimum seconds between recorded uses of one session. Minimum 1.                                                                                                         |
| `reauth_window_minutes`          | `30`    | Minutes after the last password check during which a session counts as recently authenticated. Minimum 1.                                                                |
| `trusted_proxies`                | `[]`    | Proxy addresses or CIDR networks whose forwarded client address may be trusted. Each entry must be an IP address or CIDR network. Set as a JSON list in the environment. |

`AuthSettings` only describes shape. Every numeric field must be at least 1, and nothing sets an upper bound or relates an idle lifetime to its
absolute lifetime (a session's idle expiry is capped by its absolute expiry when it is created, so an idle value above the absolute value is
harmless). `trusted_proxies` entries must each be an IP address or CIDR network. `signing_keys` and `active_kid` no longer exist;
`TRUTINA_AUTH__SIGNING_KEYS__*` and `TRUTINA_AUTH__ACTIVE_KID` left in an environment or dotenv file are ignored.
The hashing fields are checked only for what Argon2 itself requires;
whether they are strong enough for production is also an API-startup concern.

### `environment`

`Settings.environment` is `production`, `development` or `test`, and defaults to `production` so a forgotten variable fails closed. Any other value is rejected. `TestSettings` does not override the default: set `TRUTINA_TEST_ENVIRONMENT=test` (in `.env.test` or the CI environment) to opt in. Nothing reads the field yet.

## Usage

```python
from trutina.config import get_settings

settings = get_settings()
settings.postgres.uri
settings.api.port
settings.logging.level
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
TRUTINA_ENVIRONMENT=development
TRUTINA_AUTH__SESSION_API_IDLE_HOURS=24
TRUTINA_AUTH__REAUTH_WINDOW_MINUTES=30
TRUTINA_AUTH__TRUSTED_PROXIES=["10.0.0.0/8"]
TRUTINA_POSTGRES__URI=postgresql+asyncpg://username:password@localhost:5432/trutina
TRUTINA_API__PORT=8000
TRUTINA_LOGGING__LEVEL=INFO
TRUTINA_AUTH__PASSWORD_TIME_COST=3
TRUTINA_AUTH__PASSWORD_MEMORY_COST_KIB=65536
TRUTINA_AUTH__LOGIN_MAX_FAILURES=5
TRUTINA_AUTH__LOGIN_WINDOW_SECONDS=900
```

`logger_levels` is overridden as a single JSON object, since the `__` nested
delimiter would otherwise mangle logger names that themselves contain dots:

```bash
TRUTINA_LOGGING__LOGGER_LEVELS={"sqlalchemy.engine": "WARNING", "uvicorn.error": "INFO"}
```

Test configuration reads the same shape under a `TRUTINA_TEST_` prefix from
`.env.test`. See `.env.example` and `.env.test.example` at the repo root for
the full set of currently supported keys.
Test configuration opts in to the test environment with `TRUTINA_TEST_ENVIRONMENT=test`.

## Testing

```bash
uv run pytest -m "unit and config"
```

The `config` layer marker is auto-derived from file path by the root
`conftest.py` — only the `unit`/`integration` speed marker needs to be
written on the test itself.

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants.
- Confirmed direct dependents (per their own `pyproject.toml`):
  `trutina-storage-postgres` [README.md](../storage-postgres/README.md),
  `trutina-cli` [README.md](../../apps/cli/README.md),
  `trutina-api` [README.md](../../apps/api/README.md),
  `trutina-observability` [README.md](../observability/README.md).
- `trutina-config` depends on nothing else in the workspace.
