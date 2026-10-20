"""A rejected credential never reaches a response body or a log record.

Uses test-only routes on the fake-backed api_app, one per path by which
a validation failure can reach an exception handler:

    request  FastAPI rejects the body (RequestValidationError)
    mapper   a mapper-stage pydantic.ValidationError escapes the route
    service  a service raises ValidationAppError.validation(...)
"""

import logging

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from trutina.shared.errors import ValidationAppError

from tests.factories.secret import (
    SECRET_SENTINEL,
    SecretProbe,
    make_secret_probe_payload,
)

_PATHS = ["/_probe/request", "/_probe/mapper", "/_probe/service"]


@pytest.fixture
def probe_app(api_app: FastAPI) -> FastAPI:
    async def request_probe(body: SecretProbe) -> dict[str, str]:
        return {"ok": "1"}

    async def mapper_probe(payload: dict[str, object]) -> None:
        SecretProbe.model_validate(payload)

    async def service_probe(payload: dict[str, object]) -> None:
        try:
            SecretProbe.model_validate(payload)
        except ValidationError as exc:
            raise ValidationAppError.validation(exc) from exc

    api_app.add_api_route("/_probe/request", request_probe, methods=["POST"])
    api_app.add_api_route("/_probe/mapper", mapper_probe, methods=["POST"])
    api_app.add_api_route("/_probe/service", service_probe, methods=["POST"])
    return api_app


@pytest.mark.unit
class TestRejectedCredentialsNeverLeak:
    @pytest.mark.parametrize("path", _PATHS)
    async def test_sentinel_absent_from_422_body(self, probe_app, api_client, path):
        response = await api_client.post(path, json=make_secret_probe_payload())

        assert response.status_code == 422
        assert SECRET_SENTINEL not in response.text

    @pytest.mark.parametrize("path", _PATHS)
    async def test_details_still_name_the_failed_fields(
        self, probe_app, api_client, path
    ):
        response = await api_client.post(path, json=make_secret_probe_payload())

        fields = {d["field"] for d in response.json()["details"]}
        assert {"email", "new_password"} <= fields

    @pytest.mark.parametrize("path", _PATHS)
    async def test_sentinel_absent_from_every_log_record(
        self, probe_app, api_client, caplog, path
    ):
        with caplog.at_level(logging.DEBUG):
            await api_client.post(path, json=make_secret_probe_payload())

        assert caplog.records
        for record in caplog.records:
            assert SECRET_SENTINEL not in record.getMessage()
            assert SECRET_SENTINEL not in str(record.__dict__)
