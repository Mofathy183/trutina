import os
from urllib.parse import urlparse

import pytest
from trutina.config import (
    ApiSettings,
    LoggingSettings,
    PostgresSettings,
    Settings,
    get_settings,
)
from trutina.config import TestSettings as ConfigTestSettings


@pytest.fixture(autouse=True)
def _clear_trutina_env(monkeypatch):
    """Remove every TRUTINA_-prefixed env var before each test.

    Covers both the TRUTINA_ and TRUTINA_TEST_ namespaces in one pass,
    since the latter is a superset-prefix match of the former. Runs
    before the test body, so a test's own monkeypatch.setenv() calls
    (which happen inside the test) always apply on top of a genuinely
    clean slate rather than on top of whatever the host machine already
    had exported.
    """
    for key in list(os.environ):
        if key.startswith("TRUTINA_"):
            monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
class TestSettingsDefaults:
    def test_api_defaults_to_an_api_settings_instance(self):
        settings = Settings(_env_file=None)
        assert isinstance(settings.api, ApiSettings)

    def test_postgres_defaults_to_a_postgres_settings_instance(self):
        settings = Settings(_env_file=None)
        assert isinstance(settings.postgres, PostgresSettings)

    def test_nested_field_defaults_match_each_group_own_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.api.port == ApiSettings().port
        assert settings.postgres.uri == PostgresSettings().uri

    def test_nested_logging_field_defaults_match_its_own_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.logging.level == LoggingSettings().level
        assert settings.logging.format == LoggingSettings().format
        assert settings.logging.logger_levels == LoggingSettings().logger_levels


@pytest.mark.unit
class TestSettingsEnvPrefix:
    def test_reads_trutina_prefixed_nested_api_port(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_API__PORT", "9100")

        settings = Settings(_env_file=None)

        assert settings.api.port == 9100

    def test_reads_trutina_prefixed_nested_postgres_pool_size(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_POSTGRES__POOL_SIZE", "7")

        settings = Settings(_env_file=None)

        assert settings.postgres.pool_size == 7

    def test_ignores_unprefixed_env_vars(self, monkeypatch):
        # extra="ignore" plus the TRUTINA_ prefix requirement means an
        # unprefixed var sharing a field's name must never leak in.
        monkeypatch.setenv(
            "POSTGRES__URI",
            "postgresql+asyncpg://should-not-apply:password@localhost:5432/trutina",
        )

        settings = Settings(_env_file=None)

        assert settings.postgres.uri == PostgresSettings().uri


@pytest.mark.unit
class TestSettingsIsolation:
    def test_test_settings_is_a_settings_subclass(self):
        assert issubclass(ConfigTestSettings, Settings)

    def test_env_prefix_is_trutina_test(self, monkeypatch):
        monkeypatch.setenv(
            "TRUTINA_TEST_POSTGRES__URI",
            "postgresql+asyncpg://username:password@localhost:5432/trutina_test",
        )

        settings = ConfigTestSettings(_env_file=None)

        assert (
            settings.postgres.uri
            == "postgresql+asyncpg://username:password@localhost:5432/trutina_test"
        )

    def test_does_not_read_production_prefixed_vars(self, monkeypatch):
        monkeypatch.setenv(
            "TRUTINA_POSTGRES__URI",
            "postgresql+asyncpg://should-not-apply:password@localhost:5432/trutina",
        )

        settings = ConfigTestSettings(_env_file=None)

        # TRUTINA_ (production) must never leak into TRUTINA_TEST_'s
        # namespace -- falls back to PostgresSettings' own default instead.
        assert settings.postgres.uri == PostgresSettings().uri

    def test_production_settings_does_not_read_test_prefixed_vars(self, monkeypatch):
        monkeypatch.setenv(
            "TRUTINA_TEST_POSTGRES__URI",
            "postgresql+asyncpg://username:password@localhost:5432/trutina_test",
        )

        settings = Settings(_env_file=None)

        assert settings.postgres.uri == PostgresSettings().uri

    def test_production_and_test_read_independent_values_simultaneously(
        self, monkeypatch
    ):
        monkeypatch.setenv("TRUTINA_POSTGRES__URI", "trutina")
        monkeypatch.setenv("TRUTINA_TEST_POSTGRES__URI", "trutina_test")

        prod = Settings(_env_file=None)
        test = ConfigTestSettings(_env_file=None)

        assert urlparse(prod.postgres.uri).path.lstrip("/") == "trutina"
        assert urlparse(test.postgres.uri).path.lstrip("/") == "trutina_test"


@pytest.mark.unit
class TestGetSettings:
    def test_returns_a_settings_instance(self):
        assert isinstance(get_settings(), Settings)

    def test_returns_the_same_cached_instance_on_repeated_calls(self):
        first = get_settings()
        second = get_settings()

        assert first is second

    def test_cache_clear_produces_a_new_instance(self):
        first = get_settings()
        get_settings.cache_clear()
        second = get_settings()

        assert first is not second

    def test_reflects_environment_changes_only_after_cache_clear(self, monkeypatch):
        # get_settings() is lru_cache'd -- a test that mutates the
        # environment after the first call must clear the cache itself
        # to observe the new value. This pins that documented contract
        # (see CONTEXT.md's "Common mistakes to avoid").
        get_settings.cache_clear()
        baseline_db = get_settings().postgres.uri

        monkeypatch.setenv("TRUTINA_POSTGRES__URI", "changed_during_test")

        assert get_settings().postgres.uri == baseline_db

        get_settings.cache_clear()

        assert get_settings().postgres.uri == "changed_during_test"
