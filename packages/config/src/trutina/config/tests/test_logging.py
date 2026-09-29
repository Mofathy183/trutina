import pytest
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings
from trutina.config.logging import LoggingSettings


@pytest.mark.unit
class TestLoggingSettings:
    def test_uses_documented_defaults(self):
        settings = LoggingSettings()

        assert settings.level == "INFO"
        assert settings.format == "auto"
        assert settings.sink == "auto"
        assert settings.file_path is None
        assert settings.file_max_bytes == 5_000_000
        assert settings.file_backup_count == 3

    def test_is_a_plain_base_model_not_base_settings(self):
        assert issubclass(LoggingSettings, BaseModel)
        assert not issubclass(LoggingSettings, BaseSettings)

    def test_normalizes_level_to_upper_case(self):
        assert LoggingSettings(level="debug").level == "DEBUG"

    def test_rejects_unknown_level(self):
        with pytest.raises(ValidationError):
            LoggingSettings(level="LOUD")

    @pytest.mark.parametrize("field", ["format", "sink"])
    def test_rejects_unknown_choice(self, field):
        with pytest.raises(ValidationError):
            LoggingSettings(**{field: "carrier-pigeon"})  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_non_positive_file_max_bytes(self, value):
        with pytest.raises(ValidationError):
            LoggingSettings(file_max_bytes=value)

    def test_accepts_zero_backups(self):
        assert LoggingSettings(file_backup_count=0).file_backup_count == 0

    def test_rejects_negative_backup_count(self):
        with pytest.raises(ValidationError):
            LoggingSettings(file_backup_count=-1)

    def test_holds_sqlalchemy_at_warning_by_default(self):
        levels = LoggingSettings().logger_levels

        assert levels["sqlalchemy.engine"] == "WARNING"
        assert levels["sqlalchemy.pool"] == "WARNING"

    def test_does_not_configure_uvicorn_access_by_default(self):
        assert "uvicorn.access" not in LoggingSettings().logger_levels

    def test_normalizes_logger_override_levels(self):
        settings = LoggingSettings(logger_levels={"sqlalchemy.engine": "info"})

        assert settings.logger_levels == {"sqlalchemy.engine": "INFO"}

    def test_rejects_unknown_logger_override_level(self):
        with pytest.raises(ValidationError):
            LoggingSettings(logger_levels={"asyncio": "LOUD"})

    def test_overriding_logger_levels_replaces_the_whole_mapping(self):
        settings = LoggingSettings(logger_levels={"httpx": "ERROR"})

        assert settings.logger_levels == {"httpx": "ERROR"}

    def test_does_not_share_logger_levels_between_instances(self):
        first = LoggingSettings()
        second = LoggingSettings()

        first.logger_levels["httpx"] = "DEBUG"

        assert second.logger_levels["httpx"] == "WARNING"
