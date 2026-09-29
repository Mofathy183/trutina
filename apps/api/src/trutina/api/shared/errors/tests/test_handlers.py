"""Unit tests for the exception-to-response translation handlers.

Exercises each handler function directly against realistic exceptions
-- including real domain ValidationErrors built via the project's own
schema factories -- rather than hand-rolled FieldViolation stand-ins,
so the `.value` recovery path in `_resolve_violation_entry()` is
proven against the actual translation bug it works around.

register_exception_handlers()'s wiring into the running app (i.e. that
these handlers are actually reached from a raised exception inside a
route) is covered separately in
`api/composition/tests/test_app_error_handling.py`, using the real
`api_app`/`api_client` fixtures rather than a bare FastAPI instance.
End-to-end correlation-id behavior on real requests is covered in
`api/composition/tests/test_app_logging.py`.
"""

import json

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from trutina.api.shared.errors.catalog import DEFAULT_ERROR_ENTRY
from trutina.api.shared.errors.handlers import (
    _handle_app_error,
    _handle_pydantic_validation_error,
    _handle_request_validation_error,
    _handle_unexpected_error,
    _handle_validation_app_error,
)
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError

from tests.factories import make_account, make_debit_line, make_journal_entry


def _make_request() -> Request:
    """A minimal Request with no correlation id on it.

    Handlers only read `request.url.path` and `request.state`, so an
    empty HTTP scope is sufficient. A bare request models the case
    where CorrelationIdMiddleware is not installed.
    """
    return Request(scope={"type": "http", "method": "GET", "path": "/", "headers": []})


def _make_request_with_correlation_id(correlation_id: str) -> Request:
    """A Request carrying an id exactly where CorrelationIdMiddleware puts it.

    The middleware writes scope["state"]["correlation_id"]; Starlette's
    Request.state reads that same dict.
    """
    return Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "state": {"correlation_id": correlation_id},
        }
    )


def _body(response) -> dict:
    return json.loads(response.body)


@pytest.mark.unit
class TestHandleAppError:
    async def test_returns_catalog_status_code(self):
        exc = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
        )

        response = await _handle_app_error(_make_request(), exc)

        assert response.status_code == 404

    async def test_interpolates_context_into_message(self):
        exc = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
        )

        response = await _handle_app_error(_make_request(), exc)

        body = _body(response)
        assert body["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value
        assert "9999" in body["message"]

    async def test_interpolates_context_into_hint(self):
        exc = AppError.conflict(
            code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
            resource="account",
            field_name="code",
            value="1001",
        )

        response = await _handle_app_error(_make_request(), exc)

        body = _body(response)
        assert "1001" in body["hint"]

    async def test_envelope_has_success_false(self):
        exc = AppError.unknown()

        response = await _handle_app_error(_make_request(), exc)

        assert _body(response)["success"] is False

    async def test_attaches_retry_after_header_for_storage_unavailable(self):
        exc = AppError.storage_unavailable()

        response = await _handle_app_error(_make_request(), exc)

        assert response.headers["retry-after"] == "5"

    async def test_no_retry_after_header_for_non_storage_errors(self):
        exc = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="1"
        )

        response = await _handle_app_error(_make_request(), exc)

        assert "retry-after" not in response.headers

    async def test_falls_back_to_default_entry_for_unmapped_code(self):
        exc = AppError.unknown()

        response = await _handle_app_error(_make_request(), exc)

        body = _body(response)
        assert response.status_code == DEFAULT_ERROR_ENTRY.status_code
        assert body["message"] == DEFAULT_ERROR_ENTRY.message


@pytest.mark.unit
class TestHandleValidationAppError:
    async def test_returns_422_for_unbalanced_entry(self):
        from decimal import Decimal

        from tests.factories import make_credit_line

        lines = [
            make_debit_line(amount=Decimal("100")),
            make_credit_line(amount=Decimal("50")),
        ]

        try:
            make_journal_entry(lines=lines)
            pytest.fail("expected ValidationError")
        except PydanticValidationError as pydantic_exc:
            exc = ValidationAppError.validation(pydantic_exc)

        response = await _handle_validation_app_error(_make_request(), exc)

        assert response.status_code == 422

    async def test_recovers_real_domain_message_for_downgraded_code(self):
        """Regression test for the `.value` recovery path: without it,
        this would read "An unexpected error occurred" instead of the
        real INVALID_ACCOUNT_NAME message, because get_field_violations()
        downgrades domain codes to UNKNOWN_ERROR on FieldViolation.code.
        """
        try:
            make_account(name="???")
            pytest.fail("expected ValidationError")
        except PydanticValidationError as pydantic_exc:
            exc = ValidationAppError.validation(pydantic_exc)

        response = await _handle_validation_app_error(_make_request(), exc)

        body = _body(response)
        detail = next(d for d in body["details"] if d["field"] == "name")
        assert detail["message"] != DEFAULT_ERROR_ENTRY.message
        assert "account name" in detail["message"].lower()

    async def test_details_include_one_entry_per_violation(self):
        try:
            make_account(name="???")
            pytest.fail("expected ValidationError")
        except PydanticValidationError as pydantic_exc:
            exc = ValidationAppError.validation(pydantic_exc)

        response = await _handle_validation_app_error(_make_request(), exc)

        assert len(_body(response)["details"]) == len(exc.errors)


@pytest.mark.unit
class TestHandlePydanticValidationError:
    async def test_returns_422(self):
        try:
            make_account(name="???")
            pytest.fail("expected ValidationError")
        except PydanticValidationError as exc:
            response = await _handle_pydantic_validation_error(_make_request(), exc)

        assert response.status_code == 422

    async def test_error_code_is_validation_error(self):
        try:
            make_account(name="???")
            pytest.fail("expected ValidationError")
        except PydanticValidationError as exc:
            response = await _handle_pydantic_validation_error(_make_request(), exc)

        assert _body(response)["error_code"] == ErrorCode.REQUEST_VALIDATION_ERROR.value

    async def test_recovers_real_domain_message_for_downgraded_code(self):
        try:
            make_account(name="???")
            pytest.fail("expected ValidationError")
        except PydanticValidationError as exc:
            response = await _handle_pydantic_validation_error(_make_request(), exc)

        detail = next(d for d in _body(response)["details"] if d["field"] == "name")
        assert detail["message"] != DEFAULT_ERROR_ENTRY.message


@pytest.mark.unit
class TestHandleRequestValidationError:
    @pytest.mark.parametrize(
        ("loc", "expected_field"),
        [
            (("body", "name"), "name"),
            (("query", "page_size"), "page_size"),
            (("path", "account_id"), "account_id"),
            (("header", "x-request-id"), "x-request-id"),
        ],
    )
    async def test_strips_known_location_prefix(self, loc, expected_field):
        exc = RequestValidationError(
            errors=[{"loc": loc, "msg": "field required", "type": "missing"}]
        )

        response = await _handle_request_validation_error(_make_request(), exc)

        detail = _body(response)["details"][0]
        assert detail["field"] == expected_field

    async def test_uses_request_invalid_error_code(self):
        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "name"), "msg": "field required", "type": "missing"}
            ]
        )

        response = await _handle_request_validation_error(_make_request(), exc)

        assert _body(response)["error_code"] == ErrorCode.REQUEST_VALIDATION_ERROR

    async def test_returns_422(self):
        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "name"), "msg": "field required", "type": "missing"}
            ]
        )

        response = await _handle_request_validation_error(_make_request(), exc)

        assert response.status_code == 422


@pytest.mark.unit
class TestHandleUnexpectedError:
    async def test_returns_500(self):
        exc = KeyError("boom")

        response = await _handle_unexpected_error(_make_request(), exc)

        assert response.status_code == 500

    async def test_uses_default_error_entry_message(self):
        exc = KeyError("boom")

        response = await _handle_unexpected_error(_make_request(), exc)

        assert _body(response)["message"] == DEFAULT_ERROR_ENTRY.message

    async def test_does_not_leak_raw_exception_text(self):
        exc = KeyError("super-secret-internal-detail")

        response = await _handle_unexpected_error(_make_request(), exc)

        body = response.body
        if isinstance(body, memoryview):
            body = body.tobytes()

        payload = json.loads(body)

        assert payload["error_code"] == ErrorCode.UNKNOWN_ERROR.value
        assert payload["message"] == "An unexpected error occurred."
        assert "super-secret-internal-detail" not in payload["message"]

    async def test_error_code_is_unknown_error(self):
        exc = KeyError("boom")

        response = await _handle_unexpected_error(_make_request(), exc)

        assert _body(response)["error_code"] == ErrorCode.UNKNOWN_ERROR.value

    async def test_echoes_correlation_id_as_request_id_header(self):
        """The catch-all runs outside CorrelationIdMiddleware, so its
        response never passes through the middleware's send wrapper --
        the handler must attach the header itself."""
        exc = KeyError("boom")
        request = _make_request_with_correlation_id("corr-hdr")

        response = await _handle_unexpected_error(request, exc)

        assert response.headers["x-request-id"] == "corr-hdr"

    async def test_no_request_id_header_when_no_correlation_id(self):
        exc = KeyError("boom")

        response = await _handle_unexpected_error(_make_request(), exc)

        assert "x-request-id" not in response.headers


@pytest.mark.unit
class TestHandlerLogging:
    async def test_app_error_below_500_logs_at_info(self, caplog):
        exc = AppError.not_found(
            code=ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999"
        )
        request = _make_request_with_correlation_id("corr-1")

        with caplog.at_level("INFO"):
            await _handle_app_error(request, exc)

        records = [r for r in caplog.records if r.message == "request.failed"]
        assert len(records) == 1
        assert records[0].levelname == "INFO"

    async def test_unexpected_error_logs_at_error_with_exc_info(self, caplog):
        exc = KeyError("boom")
        request = _make_request_with_correlation_id("corr-2")

        with caplog.at_level("INFO"):
            await _handle_unexpected_error(request, exc)

        records = [r for r in caplog.records if r.message == "request.failed"]
        assert len(records) == 1
        assert records[0].levelname == "ERROR"
        assert records[0].exc_info is not None

    async def test_storage_unavailable_logs_at_error(self, caplog):
        exc = AppError.storage_unavailable()
        request = _make_request_with_correlation_id("corr-3")

        with caplog.at_level("INFO"):
            await _handle_app_error(request, exc)

        records = [r for r in caplog.records if r.message == "request.failed"]
        assert records[0].levelname == "ERROR"

    async def test_log_line_carries_correlation_id_read_from_request_state(
        self, caplog
    ):
        exc = AppError.unknown()
        request = _make_request_with_correlation_id("corr-4")

        with caplog.at_level("INFO"):
            await _handle_app_error(request, exc)

        record = next(r for r in caplog.records if r.message == "request.failed")
        assert record.correlation_id == "corr-4"

    async def test_correlation_id_is_top_level_not_nested_in_context(self, caplog):
        """The id must sit beside event/level, not inside `context`, so
        it is queryable the same way as on every other record."""
        exc = KeyError("boom")
        request = _make_request_with_correlation_id("corr-5")

        with caplog.at_level("INFO"):
            await _handle_unexpected_error(request, exc)

        record = next(r for r in caplog.records if r.message == "request.failed")
        assert record.correlation_id == "corr-5"
        assert "correlation_id" not in record.context

    async def test_missing_correlation_id_does_not_raise(self, caplog):
        """A bare Request with no middleware-populated state must not
        crash logging -- only unit tests without create_app() hit this
        path, but it must degrade gracefully."""
        exc = AppError.unknown()
        request = _make_request()

        with caplog.at_level("INFO"):
            await _handle_app_error(request, exc)  # must not raise

        record = next(r for r in caplog.records if r.message == "request.failed")
        assert not hasattr(record, "correlation_id")
