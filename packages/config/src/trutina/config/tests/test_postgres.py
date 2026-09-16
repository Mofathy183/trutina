import pytest
from pydantic_settings import BaseSettings
from trutina.config import PostgresSettings


@pytest.mark.unit
class TestPostgresSettingsDefaults:
    def test_default_uri(self):
        settings = PostgresSettings()
        assert settings.uri == "postgresql+asyncpg://localhost:5432/trutina"

    def test_default_connect_timeout_s(self):
        settings = PostgresSettings()
        assert settings.connect_timeout_s == 5.0

    def test_default_pool_size(self):
        settings = PostgresSettings()
        assert settings.pool_size == 1

    def test_default_max_overflow(self):
        settings = PostgresSettings()
        assert settings.max_overflow == 10

    def test_default_pool_pre_ping_is_true(self):
        settings = PostgresSettings()
        assert settings.pool_pre_ping is True


@pytest.mark.unit
class TestPostgresSettingsOverrides:
    def test_overrides_uri(self):
        settings = PostgresSettings(uri="postgresql+asyncpg://example-host:5432/other")
        assert settings.uri == "postgresql+asyncpg://example-host:5432/other"

    def test_overrides_connect_timeout_s(self):
        settings = PostgresSettings(connect_timeout_s=2.5)
        assert settings.connect_timeout_s == 2.5

    def test_overrides_pool_size(self):
        settings = PostgresSettings(pool_size=5)
        assert settings.pool_size == 5

    def test_overrides_max_overflow(self):
        settings = PostgresSettings(max_overflow=20)
        assert settings.max_overflow == 20

    def test_overrides_pool_pre_ping(self):
        settings = PostgresSettings(pool_pre_ping=False)
        assert settings.pool_pre_ping is False


@pytest.mark.unit
class TestPostgresSettingsIsPlainBaseModel:
    def test_is_not_a_settings_subclass(self):
        assert not issubclass(PostgresSettings, BaseSettings)
