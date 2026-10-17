"""Tests for create_app()'s factory behavior.

Unit tests verify factory construction, settings propagation, and
independence between app instances — no I/O, no lifespan entered.
Integration tests verify the real lifespan actually serves a request
end to end via real_api_client.

Does NOT re-verify FastAPI's own routing/OpenAPI generation, and does
NOT re-verify service business behavior (see modules/*/tests/) or
build_container()'s wiring (see test_container.py).
"""

import pytest
from fastapi import FastAPI
from pydantic import ValidationError as PydanticValidationError
from trutina.api.composition.app import create_app
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError

from tests.factories import make_account


@pytest.mark.unit
class TestCreateApp:
    def test_returns_fastapi_instance(self, test_settings):
        app = create_app(test_settings)

        assert isinstance(app, FastAPI)

    def test_uses_settings_title(self, test_settings):
        settings = test_settings.model_copy(deep=True)
        settings.api.title = "Custom Title"

        app = create_app(settings)

        assert app.title == "Custom Title"

    def test_uses_settings_version(self, test_settings):
        settings = test_settings.model_copy(deep=True)
        settings.api.version = "9.9.9"

        app = create_app(settings)

        assert app.version == "9.9.9"

    def test_uses_settings_description(self, test_settings):
        settings = test_settings.model_copy(deep=True)
        settings.api.description = "Custom description"

        app = create_app(settings)

        assert app.description == "Custom description"

    def test_two_calls_produce_independent_app_instances(self, test_settings):
        settings = test_settings.model_copy(deep=True)

        first = create_app(settings)
        second = create_app(settings)

        assert first is not second

    def test_independent_apps_do_not_share_state_container(self, test_settings):
        """Guards the global-registration isolation concern named
        in create_app()'s own docstring: two app instances must not leak
        mutable state (e.g. app.state.container) between each other.
        """
        settings = test_settings.model_copy(deep=True)

        first = create_app(settings)
        second = create_app(settings)

        first.state.container = object()

        assert not hasattr(second.state, "container")

    def test_falls_back_to_get_settings_when_none_provided(self, test_settings):
        """create_app(settings=None) must not raise — it resolves via
        get_settings() exactly like build_context() does for the CLI.

        isolate_settings_cache (tests/fixtures/settings.py) is
        autouse=True, so get_settings.cache_clear() has already run
        before this test without needing to be requested explicitly.
        """
        app = create_app()

        assert isinstance(app, FastAPI)


@pytest.mark.unit
class TestRegisterExceptionHandlersWiring:
    async def test_app_error_returns_standard_envelope(
        self, api_app: FastAPI, api_client
    ):
        @api_app.get("/__test/not_found")
        async def _boom_not_found():
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
            )

        response = await api_client.get("/__test/not_found")

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value
        assert "9999" in body["message"]

    async def test_validation_app_error_returns_standard_envelope(
        self, api_app: FastAPI, api_client
    ):
        @api_app.get("/__test/validation")
        async def _boom_validation():
            try:
                make_account(name="???")
            except PydanticValidationError as exc:
                raise ValidationAppError.validation(exc) from exc

        response = await api_client.get("/__test/validation")

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert len(body["details"]) > 0

    async def test_request_validation_error_returns_standard_envelope(
        self, api_app: FastAPI, api_client
    ):
        from pydantic import BaseModel

        class _Payload(BaseModel):
            required_field: str

        @api_app.post("/__test/request_validation")
        async def _boom_request_validation(payload: _Payload):
            return payload

        response = await api_client.post("/__test/request_validation", json={})

        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == "request.invalid"
        assert any(d["field"] == "required_field" for d in body["details"])

    async def test_unexpected_error_returns_standard_envelope_not_default_500(
        self, api_app: FastAPI, api_client_no_raise
    ):
        @api_app.get("/__test/unexpected")
        async def _boom_unexpected():
            raise KeyError("unexpected")

        response = await api_client_no_raise.get("/__test/unexpected")

        assert response.status_code == 500
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == ErrorCode.UNKNOWN_ERROR.value
