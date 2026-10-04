import os

import pytest
from pydantic import ValidationError
from trutina.config import AuthSettings, Settings
from trutina.config import TestSettings as ConfigTestSettings

_KEY = "k" * 32


@pytest.fixture(autouse=True)
def _clear_trutina_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("TRUTINA_"):
            monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
class TestAuthSettingsDefaults:
    def test_has_no_keys_and_no_active_kid_by_default(self):
        auth = AuthSettings()

        assert auth.signing_keys == {}
        assert auth.active_kid is None

    def test_root_settings_constructs_without_signing_keys(self):
        settings = Settings(_env_file=None)

        assert settings.auth.signing_keys == {}
        assert settings.auth.active_kid is None

    def test_test_settings_constructs_without_signing_keys(self):
        settings = ConfigTestSettings(_env_file=None)

        assert settings.auth.signing_keys == {}
        assert settings.auth.active_kid is None


@pytest.mark.unit
class TestAuthSettingsEnvLoading:
    def test_loads_signing_key_and_active_kid_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__SIGNING_KEYS__k1", _KEY)
        monkeypatch.setenv("TRUTINA_AUTH__ACTIVE_KID", "k1")

        settings = Settings(_env_file=None)

        assert list(settings.auth.signing_keys) == ["k1"]
        assert settings.auth.signing_keys["k1"].get_secret_value() == _KEY
        assert settings.auth.active_kid == "k1"

    def test_active_kid_matches_key_regardless_of_env_case(self, monkeypatch):
        # pydantic-settings lower-cases dict keys read from env vars but
        # not plain string values; AuthSettings folds both so they agree.
        monkeypatch.setenv("TRUTINA_AUTH__SIGNING_KEYS__K1", _KEY)
        monkeypatch.setenv("TRUTINA_AUTH__ACTIVE_KID", "K1")

        settings = Settings(_env_file=None)

        assert settings.auth.active_kid in settings.auth.signing_keys

    def test_folds_key_ids_on_direct_construction(self):
        auth = AuthSettings(signing_keys={"Key-A": _KEY}, active_kid="KEY-A")

        assert list(auth.signing_keys) == ["key-a"]
        assert auth.active_kid == "key-a"

    def test_test_settings_reads_only_the_test_namespace(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__ACTIVE_KID", "prod")
        monkeypatch.setenv("TRUTINA_TEST_AUTH__ACTIVE_KID", "test")

        settings = ConfigTestSettings(_env_file=None)

        assert settings.auth.active_kid == "test"


@pytest.mark.unit
class TestAuthSettingsSecrecy:
    def test_repr_does_not_reveal_signing_key(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__SIGNING_KEYS__k1", _KEY)

        settings = Settings(_env_file=None)

        assert _KEY not in repr(settings.auth)
        assert _KEY not in repr(settings)
        assert _KEY not in str(settings.auth)


@pytest.mark.unit
class TestEnvironment:
    def test_defaults_to_production(self):
        assert Settings(_env_file=None).environment == "production"

    def test_test_settings_also_defaults_to_production(self):
        # Deliberate (decision D2): the test namespace opts in via
        # TRUTINA_TEST_ENVIRONMENT=test; TestSettings does not override.
        assert ConfigTestSettings(_env_file=None).environment == "production"

    @pytest.mark.parametrize("value", ["production", "development", "test"])
    def test_accepts_each_known_environment(self, monkeypatch, value):
        monkeypatch.setenv("TRUTINA_ENVIRONMENT", value)

        assert Settings(_env_file=None).environment == value

    def test_test_settings_opts_in_via_test_prefix(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_TEST_ENVIRONMENT", "test")

        assert ConfigTestSettings(_env_file=None).environment == "test"

    def test_rejects_unknown_environment(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_ENVIRONMENT", "staging")

        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        assert exc_info.value.errors()[0]["loc"] == ("environment",)
