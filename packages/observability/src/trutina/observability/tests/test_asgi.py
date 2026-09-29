import pytest
from trutina.observability.asgi import CorrelationIdMiddleware
from trutina.observability.correlation import (
    get_correlation_id,
    is_valid_correlation_id,
)


async def _app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {
        "type": "http",
        "method": "GET",
        "path": "/accounts",
        "headers": headers or [],
    }


async def _run(app, scope):
    messages = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    return messages


@pytest.mark.unit
class TestCorrelationIdMiddleware:
    async def test_generates_an_id_when_no_header_present(self):
        middleware = CorrelationIdMiddleware(_app)
        messages = await _run(middleware, _http_scope())

        start = messages[0]
        headers = dict(start["headers"])
        assert is_valid_correlation_id(headers[b"x-request-id"].decode())

    async def test_reuses_a_valid_inbound_header(self):
        middleware = CorrelationIdMiddleware(_app)
        messages = await _run(
            middleware, _http_scope([(b"x-request-id", b"client-supplied-1")])
        )

        headers = dict(messages[0]["headers"])
        assert headers[b"x-request-id"] == b"client-supplied-1"

    async def test_replaces_a_malformed_inbound_header(self):
        middleware = CorrelationIdMiddleware(_app)
        messages = await _run(
            middleware, _http_scope([(b"x-request-id", b"bad header value")])
        )

        headers = dict(messages[0]["headers"])
        assert headers[b"x-request-id"] != b"bad header value"

    async def test_id_is_not_bound_outside_the_request(self):
        middleware = CorrelationIdMiddleware(_app)
        await _run(middleware, _http_scope())
        assert get_correlation_id() is None

    async def test_two_requests_get_different_ids(self):
        middleware = CorrelationIdMiddleware(_app)
        first = await _run(middleware, _http_scope())
        second = await _run(middleware, _http_scope())

        first_id = dict(first[0]["headers"])[b"x-request-id"]
        second_id = dict(second[0]["headers"])[b"x-request-id"]
        assert first_id != second_id

    async def test_non_http_scope_passes_through_untouched(self):
        seen = {}

        async def lifespan_app(scope, receive, send):
            seen["type"] = scope["type"]

        async def receive():
            return {"type": "lifespan.startup"}

        async def send(message):
            pass

        middleware = CorrelationIdMiddleware(lifespan_app)
        await middleware({"type": "lifespan"}, receive, send)
        assert seen["type"] == "lifespan"

    async def test_stores_the_id_on_scope_state(self):
        seen = {}

        async def capturing_app(scope, receive, send):
            seen["state_id"] = scope["state"]["correlation_id"]
            await _app(scope, receive, send)

        middleware = CorrelationIdMiddleware(capturing_app)
        messages = await _run(middleware, _http_scope())

        header_id = dict(messages[0]["headers"])[b"x-request-id"].decode()
        assert seen["state_id"] == header_id


@pytest.mark.unit
class TestRequestCompletedLine:
    async def test_logs_request_completed_with_status(self, caplog):
        middleware = CorrelationIdMiddleware(_app)

        with caplog.at_level("INFO"):
            await _run(middleware, _http_scope())

        records = [r for r in caplog.records if r.message == "request.completed"]
        assert len(records) == 1
        assert records[0].context["status"] == 200

    async def test_logs_request_completed_when_the_app_raises(self, caplog):
        async def failing_app(scope, receive, send):
            raise RuntimeError("boom")

        middleware = CorrelationIdMiddleware(failing_app)

        with caplog.at_level("INFO"):
            with pytest.raises(RuntimeError):
                await _run(middleware, _http_scope())

        records = [r for r in caplog.records if r.message == "request.completed"]
        assert len(records) == 1
        assert records[0].context["status"] == 500

    async def test_still_clears_the_id_when_the_app_raises(self):
        async def failing_app(scope, receive, send):
            raise RuntimeError("boom")

        middleware = CorrelationIdMiddleware(failing_app)

        with pytest.raises(RuntimeError):
            await _run(middleware, _http_scope())

        assert get_correlation_id() is None
