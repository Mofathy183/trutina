import pytest
from pydantic_settings import BaseSettings
from trutina.config import MongoSettings


@pytest.mark.unit
class TestMongoSettingsDefaults:
    def test_default_uri(self):
        settings = MongoSettings()
        assert settings.uri == "mongodb://localhost:27017"

    def test_default_db(self):
        settings = MongoSettings()
        assert settings.db == "trutina"

    def test_default_server_selection_timeout_ms(self):
        settings = MongoSettings()
        assert settings.server_selection_timeout_ms == 5000

    def test_default_min_pool_size(self):
        settings = MongoSettings()
        assert settings.min_pool_size == 1

    def test_default_retry_reads_is_true(self):
        settings = MongoSettings()
        assert settings.retry_reads is True

    def test_default_retry_writes_is_true(self):
        settings = MongoSettings()
        assert settings.retry_writes is True


@pytest.mark.unit
class TestMongoSettingsOverrides:
    def test_overrides_uri(self):
        settings = MongoSettings(uri="mongodb://example-host:27017")
        assert settings.uri == "mongodb://example-host:27017"

    def test_overrides_db(self):
        settings = MongoSettings(db="other_db")
        assert settings.db == "other_db"

    def test_overrides_server_selection_timeout_ms(self):
        settings = MongoSettings(server_selection_timeout_ms=1000)
        assert settings.server_selection_timeout_ms == 1000

    def test_overrides_min_pool_size(self):
        settings = MongoSettings(min_pool_size=5)
        assert settings.min_pool_size == 5

    def test_overrides_retry_reads(self):
        settings = MongoSettings(retry_reads=False)
        assert settings.retry_reads is False

    def test_overrides_retry_writes(self):
        settings = MongoSettings(retry_writes=False)
        assert settings.retry_writes is False


@pytest.mark.unit
class TestMongoSettingsIsPlainBaseModel:
    def test_is_not_a_settings_subclass(self):
        # Only Settings/TestSettings may own environment-loading
        # configuration -- a nested group given its own BaseSettings
        # would silently ignore the parent's prefix rules.
        assert not issubclass(MongoSettings, BaseSettings)
