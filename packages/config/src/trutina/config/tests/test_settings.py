import os

import pytest
from trutina.config import (
    ApiSettings,
    MongoSettings,
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
    def test_mongo_defaults_to_a_mongo_settings_instance(self):
        settings = Settings(_env_file=None)
        assert isinstance(settings.mongo, MongoSettings)

    def test_api_defaults_to_an_api_settings_instance(self):
        settings = Settings(_env_file=None)
        assert isinstance(settings.api, ApiSettings)

    def test_postgres_defaults_to_a_postgres_settings_instance(self):
        settings = Settings(_env_file=None)
        assert isinstance(settings.postgres, PostgresSettings)

    def test_nested_field_defaults_match_each_group_own_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.mongo.uri == MongoSettings().uri
        assert settings.mongo.db == MongoSettings().db
        assert settings.api.port == ApiSettings().port
        assert settings.postgres.uri == PostgresSettings().uri


@pytest.mark.unit
class TestSettingsEnvPrefix:
    def test_reads_trutina_prefixed_mongo_uri(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_MONGO__URI", "mongodb://prod-host:27017")

        settings = Settings(_env_file=None)

        assert settings.mongo.uri == "mongodb://prod-host:27017"

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
        monkeypatch.setenv("MONGO__URI", "mongodb://should-not-apply:27017")

        settings = Settings(_env_file=None)

        assert settings.mongo.uri == MongoSettings().uri


@pytest.mark.unit
class TestSettingsIsolation:
    def test_test_settings_is_a_settings_subclass(self):
        assert issubclass(ConfigTestSettings, Settings)

    def test_env_prefix_is_trutina_test(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_TEST_MONGO__URI", "mongodb://test-host:27017")

        settings = ConfigTestSettings(_env_file=None)

        assert settings.mongo.uri == "mongodb://test-host:27017"

    def test_does_not_read_production_prefixed_vars(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_MONGO__URI", "mongodb://prod-host:27017")

        settings = ConfigTestSettings(_env_file=None)

        # TRUTINA_ (production) must never leak into TRUTINA_TEST_'s
        # namespace -- falls back to MongoSettings' own default instead.
        assert settings.mongo.uri == MongoSettings().uri

    def test_production_settings_does_not_read_test_prefixed_vars(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_TEST_MONGO__URI", "mongodb://test-host:27017")

        settings = Settings(_env_file=None)

        assert settings.mongo.uri == MongoSettings().uri

    def test_production_and_test_read_independent_values_simultaneously(
        self, monkeypatch
    ):
        monkeypatch.setenv("TRUTINA_MONGO__DB", "trutina")
        monkeypatch.setenv("TRUTINA_TEST_MONGO__DB", "trutina_test")

        prod = Settings(_env_file=None)
        test = ConfigTestSettings(_env_file=None)

        assert prod.mongo.db == "trutina"
        assert test.mongo.db == "trutina_test"


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
        baseline_db = get_settings().mongo.db

        monkeypatch.setenv("TRUTINA_MONGO__DB", "changed_during_test")

        assert get_settings().mongo.db == baseline_db

        get_settings.cache_clear()

        assert get_settings().mongo.db == "changed_during_test"
