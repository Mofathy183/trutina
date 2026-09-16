import pytest
from pydantic_settings import BaseSettings
from trutina.config import ApiSettings


@pytest.mark.unit
class TestApiSettingsDefaults:
    def test_default_title(self):
        settings = ApiSettings()
        assert settings.title == "Trutina API"

    def test_default_version(self):
        settings = ApiSettings()
        assert settings.version == "0.1.0"

    def test_default_description(self):
        settings = ApiSettings()
        assert settings.description == "REST API for the Trutina accounting engine."

    def test_default_host(self):
        settings = ApiSettings()
        assert settings.host == "127.0.0.1"

    def test_default_port(self):
        settings = ApiSettings()
        assert settings.port == 8000

    def test_default_reload_is_false(self):
        settings = ApiSettings()
        assert settings.reload is False


@pytest.mark.unit
class TestApiSettingsOverrides:
    def test_overrides_title(self):
        settings = ApiSettings(title="Custom API")
        assert settings.title == "Custom API"

    def test_overrides_version(self):
        settings = ApiSettings(version="2.0.0")
        assert settings.version == "2.0.0"

    def test_overrides_description(self):
        settings = ApiSettings(description="A custom description.")
        assert settings.description == "A custom description."

    def test_overrides_host(self):
        settings = ApiSettings(host="0.0.0.0")
        assert settings.host == "0.0.0.0"

    def test_overrides_port(self):
        settings = ApiSettings(port=9100)
        assert settings.port == 9100

    def test_overrides_reload(self):
        settings = ApiSettings(reload=True)
        assert settings.reload is True


@pytest.mark.unit
class TestApiSettingsIsPlainBaseModel:
    def test_is_not_a_settings_subclass(self):
        assert not issubclass(ApiSettings, BaseSettings)
