import os

import pytest
from pydantic import ValidationError
from trutina.config import AuthSettings, Settings
from trutina.config import TestSettings as ConfigTestSettings

_SESSION_FIELDS = (
    "session_api_idle_hours",
    "session_api_absolute_days",
    "session_cli_idle_days",
    "session_cli_absolute_days",
    "session_touch_interval_seconds",
    "reauth_window_minutes",
)


@pytest.fixture(autouse=True)
def _clear_trutina_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("TRUTINA_"):
            monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
class TestAuthSettingsDefaults:
    def test_root_settings_constructs_with_an_empty_environment(self):
        settings = Settings(_env_file=None)

        assert isinstance(settings.auth, AuthSettings)

    def test_test_settings_constructs_with_an_empty_environment(self):
        settings = ConfigTestSettings(_env_file=None)

        assert isinstance(settings.auth, AuthSettings)


@pytest.mark.unit
class TestSessionSettings:
    def test_defaults(self):
        auth = AuthSettings()

        assert (
            auth.session_api_idle_hours,
            auth.session_api_absolute_days,
            auth.session_cli_idle_days,
            auth.session_cli_absolute_days,
            auth.session_touch_interval_seconds,
            auth.reauth_window_minutes,
        ) == (24, 7, 14, 30, 300, 30)

    @pytest.mark.parametrize("field", _SESSION_FIELDS)
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_a_value_below_one(self, field, value):
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings.model_validate({field: value})

        assert exc_info.value.errors()[0]["loc"] == (field,)

    @pytest.mark.parametrize("field", _SESSION_FIELDS)
    def test_accepts_the_minimum_of_one(self, field):
        auth = AuthSettings.model_validate({field: 1})

        assert getattr(auth, field) == 1

    def test_accepts_an_idle_lifetime_above_the_absolute_lifetime(self):
        auth = AuthSettings(session_api_idle_hours=24 * 30, session_api_absolute_days=1)

        assert auth.session_api_idle_hours == 24 * 30

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__SESSION_API_IDLE_HOURS", "12")
        monkeypatch.setenv("TRUTINA_AUTH__REAUTH_WINDOW_MINUTES", "10")

        settings = Settings(_env_file=None)

        assert settings.auth.session_api_idle_hours == 12
        assert settings.auth.reauth_window_minutes == 10

    def test_test_settings_reads_only_the_test_namespace(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__REAUTH_WINDOW_MINUTES", "5")
        monkeypatch.setenv("TRUTINA_TEST_AUTH__REAUTH_WINDOW_MINUTES", "7")

        settings = ConfigTestSettings(_env_file=None)

        assert settings.auth.reauth_window_minutes == 7


@pytest.mark.unit
class TestTrustedProxies:
    def test_defaults_to_empty(self):
        assert AuthSettings().trusted_proxies == []

    def test_accepts_addresses_and_networks(self):
        entries = ["203.0.113.7", "10.0.0.0/8", "2001:db8::/32"]

        auth = AuthSettings(trusted_proxies=entries)

        assert auth.trusted_proxies == entries

    def test_trims_surrounding_whitespace(self):
        auth = AuthSettings(trusted_proxies=[" 10.0.0.1 "])

        assert auth.trusted_proxies == ["10.0.0.1"]

    @pytest.mark.parametrize("entry", ["", "not-an-ip", "10.0.0.0/33"])
    def test_rejects_an_entry_that_is_not_an_address_or_network(self, entry):
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings(trusted_proxies=[entry])

        assert exc_info.value.errors()[0]["loc"] == ("trusted_proxies",)

    def test_loads_a_json_list_from_env(self, monkeypatch):
        monkeypatch.setenv(
            "TRUTINA_AUTH__TRUSTED_PROXIES", '["10.0.0.0/8", "203.0.113.7"]'
        )

        settings = Settings(_env_file=None)

        assert settings.auth.trusted_proxies == ["10.0.0.0/8", "203.0.113.7"]


@pytest.mark.unit
class TestRemovedSigningKeySettings:
    def test_auth_settings_has_no_signing_key_fields(self):
        auth = AuthSettings()

        assert not hasattr(auth, "signing_keys")
        assert not hasattr(auth, "active_kid")

    def test_stale_environment_variables_are_ignored(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__SIGNING_KEYS__k1", "k" * 32)
        monkeypatch.setenv("TRUTINA_AUTH__ACTIVE_KID", "k1")

        settings = Settings(_env_file=None)

        assert not hasattr(settings.auth, "signing_keys")
        assert not hasattr(settings.auth, "active_kid")

    def test_stale_dotenv_entries_are_ignored(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"TRUTINA_AUTH__SIGNING_KEYS__k1={'k' * 32}\nTRUTINA_AUTH__ACTIVE_KID=k1\n",
            encoding="utf-8",
        )

        settings = Settings(_env_file=env_file)

        assert not hasattr(settings.auth, "signing_keys")
        assert not hasattr(settings.auth, "active_kid")


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


@pytest.mark.unit
class TestPasswordHashingSettings:
    def test_defaults(self):
        auth = AuthSettings()

        assert (
            auth.password_time_cost,
            auth.password_memory_cost_kib,
            auth.password_parallelism,
            auth.password_hash_concurrency,
        ) == (3, 65536, 1, 4)

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__PASSWORD_TIME_COST", "2")
        monkeypatch.setenv("TRUTINA_AUTH__PASSWORD_HASH_CONCURRENCY", "8")

        settings = Settings(_env_file=None)

        assert settings.auth.password_time_cost == 2
        assert settings.auth.password_hash_concurrency == 8

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("password_time_cost", 0),
            ("password_memory_cost_kib", 7),
            ("password_parallelism", 0),
            ("password_hash_concurrency", 0),
        ],
    )
    def test_rejects_out_of_range_values(self, field, value):
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings.model_validate({field: value})

        assert exc_info.value.errors()[0]["loc"] == (field,)

    def test_rejects_less_than_eight_kib_of_memory_per_lane(self):
        with pytest.raises(ValidationError):
            AuthSettings(password_parallelism=4, password_memory_cost_kib=16)

    def test_defaults_meet_the_owasp_argon2id_minimum(self):
        # OWASP Password Storage Cheat Sheet minimum: 19 MiB, 2 iterations,
        # 1 lane. Re-read the source when this test is touched.
        auth = AuthSettings()

        assert auth.password_memory_cost_kib >= 19456
        assert auth.password_time_cost >= 2
        assert auth.password_parallelism >= 1


@pytest.mark.unit
class TestLoginThrottleSettings:
    def test_defaults(self):
        auth = AuthSettings()

        assert (auth.login_max_failures, auth.login_window_seconds) == (5, 900)

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUTINA_AUTH__LOGIN_MAX_FAILURES", "3")
        monkeypatch.setenv("TRUTINA_AUTH__LOGIN_WINDOW_SECONDS", "60")

        settings = Settings(_env_file=None)

        assert settings.auth.login_max_failures == 3
        assert settings.auth.login_window_seconds == 60

    @pytest.mark.parametrize("field", ["login_max_failures", "login_window_seconds"])
    def test_rejects_zero(self, field):
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings.model_validate({field: 0})

        assert exc_info.value.errors()[0]["loc"] == (field,)
