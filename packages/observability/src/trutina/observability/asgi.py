"""Pure ASGI correlation-id middleware.

No FastAPI or Starlette import, so a future GraphQL app can reuse this
with zero framework coupling -- the same reasoning trutina-cli's own
CONTEXT.md gives for keeping Rich UI code out of anything shared.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from .correlation import correlation_scope, is_valid_correlation_id

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

logger = logging.getLogger(__name__)

_HEADER_NAME = b"x-request-id"


class CorrelationIdMiddleware:
    """Binds one correlation id for the lifetime of one ASGI request.

    Reuses a valid inbound X-Request-ID header if present; otherwise
    generates a new id. The id is echoed back on the response header,
    stored at scope["state"]["correlation_id"] (readable by a catch-all
    exception handler running outside this middleware's own
    correlation_scope -- see apps/api/CONTEXT.md's documented pitfall
    about context variables reset before a 500-path handler runs), and
    one "request.completed" line is emitted per request.

    "request.completed" is emitted even when the wrapped app raises,
    with status 500 if no response had started yet. An unhandled
    exception therefore still produces a completion line with a
    duration, alongside the single failure line the API's catch-all
    handler logs. The exception is always re-raised unchanged.

    A response produced by a handler that runs *outside* this
    middleware (Starlette's catch-all Exception handler) does not pass
    through the send wrapper below and so carries no X-Request-ID
    header from here; that handler adds the header itself from
    scope["state"]["correlation_id"].
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == _HEADER_NAME:
                candidate = value.decode("latin-1")
                if is_valid_correlation_id(candidate):
                    incoming = candidate
                break

        status_holder: dict[str, int] = {}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", []).append(
                    (_HEADER_NAME, cid.encode("latin-1"))
                )
            await send(message)

        with correlation_scope(incoming) as cid:
            scope.setdefault("state", {})
            scope["state"]["correlation_id"] = cid

            start = time.monotonic()
            try:
                await self._app(scope, receive, send_wrapper)
            finally:
                duration_ms = round((time.monotonic() - start) * 1000, 2)

                logger.info(
                    "request.completed",
                    extra={
                        "context": {
                            "method": scope.get("method"),
                            "path": scope.get("path"),
                            "status": status_holder.get("status", 500),
                            "duration_ms": duration_ms,
                        }
                    },
                )
