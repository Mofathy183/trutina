"""End-to-end logging acceptance tests for the API composition root.

Drives real requests through create_app()'s real middleware and
exception handlers (via the fake-container `api_app`/`api_client`
fixtures, so no database is touched) and asserts on the JSON the
logging pipeline actually writes to a file -- not on stdlib
LogRecords, which never carry the correlation id (it is injected at
format time).

Uses a file sink rather than capsys/stdout, so this doesn't depend on
which stream a handler happened to bind to at configure time.

Covers Phase 3's acceptance criteria:

- the response X-Request-ID equals the correlation_id on the request's
    log line;
- a forced 500 logs exactly one ERROR line that still carries the id,
    and the 500 response itself carries the header;
- an expected domain error (404) logs no ERROR line.

Does NOT re-verify the handlers' status/body mapping (see
api/shared/errors/tests/test_handlers.py) or the middleware in
isolation (see trutina/observability/tests/test_asgi.py).
"""

import json

import pytest
from trutina.config import LoggingSettings
from trutina.observability import configure_logging
from trutina.shared.errors import AppError, ErrorCode


def _json_records(text: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (raw.strip() for raw in text.splitlines())
        if line.startswith("{")
    ]


@pytest.fixture
def json_logs(api_app, tmp_path):
    """Reconfigure logging to a JSON file sink and read it back.

    Depends on `api_app` so this runs AFTER create_app() (which itself
    calls configure_logging()) and therefore wins. A file sink avoids
    depending on which stream a handler bound to at configure time.
    The autouse reset fixture removes the handler afterwards.

    `file_path` is passed as `str(log_file)` -- LoggingSettings.file_path
    is typed `str | None`, and pytest's `tmp_path` fixture returns a
    `pathlib.Path`, which Pydantic v2 does not implicitly coerce to
    `str` for a plain string field.

    Returns:
        A zero-argument callable returning every JSON record written
        to the file so far (cumulative, not since the last call).
    """
    log_file = tmp_path / "api.log"
    configure_logging(
        LoggingSettings(
            sink="file", file_path=str(log_file), format="json", level="INFO"
        ),
        app="api",
    )

    def read() -> list[dict]:
        if not log_file.exists():
            return []
        return _json_records(log_file.read_text())

    return read


@pytest.mark.unit
class TestRequestCorrelation:
    async def test_response_header_matches_the_logged_correlation_id(
        self, api_client, json_logs
    ):
        response = await api_client.get("/health")

        header_id = response.headers["x-request-id"]
        completed = [r for r in json_logs() if r["event"] == "request.completed"]
        assert len(completed) == 1
        assert completed[0]["correlation_id"] == header_id

    async def test_honors_a_valid_inbound_request_id(self, api_client, json_logs):
        response = await api_client.get(
            "/health", headers={"X-Request-ID": "client-abc-1"}
        )

        assert response.headers["x-request-id"] == "client-abc-1"
        completed = [r for r in json_logs() if r["event"] == "request.completed"]
        assert completed[0]["correlation_id"] == "client-abc-1"

    async def test_two_requests_get_distinct_ids(self, api_client, json_logs):
        first = await api_client.get("/health")
        second = await api_client.get("/health")

        assert first.headers["x-request-id"] != second.headers["x-request-id"]
        ids = [
            r["correlation_id"]
            for r in json_logs()
            if r["event"] == "request.completed"
        ]
        assert len(set(ids)) == 2


@pytest.mark.unit
class TestFailureLogging:
    async def test_unexpected_error_logs_exactly_one_error_line_with_the_id(
        self, api_app, api_client_no_raise, json_logs
    ):
        @api_app.get("/__test/boom")
        async def _boom():
            raise KeyError("boom")

        response = await api_client_no_raise.get("/__test/boom")

        assert response.status_code == 500
        header_id = response.headers["x-request-id"]

        errors = [r for r in json_logs() if r["level"] == "error"]
        assert len(errors) == 1
        assert errors[0]["event"] == "request.failed"
        assert errors[0]["error_code"] == ErrorCode.UNKNOWN_ERROR.value
        assert errors[0]["correlation_id"] == header_id
        assert "exception" in errors[0]

    async def test_unexpected_error_still_emits_request_completed_as_500(
        self, api_app, api_client_no_raise, json_logs
    ):
        @api_app.get("/__test/boom_completed")
        async def _boom():
            raise KeyError("boom")

        response = await api_client_no_raise.get("/__test/boom_completed")

        completed = [r for r in json_logs() if r["event"] == "request.completed"]
        assert len(completed) == 1
        assert completed[0]["context"]["status"] == 500
        assert completed[0]["correlation_id"] == response.headers["x-request-id"]

    async def test_expected_domain_error_logs_no_error_line(
        self, api_app, api_client, json_logs
    ):
        @api_app.get("/__test/missing")
        async def _missing():
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
            )

        response = await api_client.get("/__test/missing")

        assert response.status_code == 404
        records = json_logs()
        assert [r for r in records if r["level"] == "error"] == []
        failed = [r for r in records if r["event"] == "request.failed"]
        assert len(failed) == 1
        assert failed[0]["level"] == "info"
        assert failed[0]["correlation_id"] == response.headers["x-request-id"]
