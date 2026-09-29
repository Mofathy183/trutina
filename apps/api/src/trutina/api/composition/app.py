"""FastAPI application factory for the Trutina API.

app.py wires the lifespan (bootstrap.py) to a FastAPI instance,
configures process-wide logging, attaches correlation-id middleware,
and registers routers. It performs no business logic, constructs no
services or repositories directly, and never imports Mongo-specific
infrastructure types — the same rule cli/app.py already follows for the
Typer app.

Logging is configured here, not in main.py, because the production and
dev containers both start the `uvicorn` CLI directly against
`trutina.api.composition.app:app` (see the Dockerfile) and never call
main() — importing this module is the only step guaranteed to run
before the app serves traffic. configure_logging() is idempotent, so
importing this module more than once in the same process (as tests do)
never installs a second handler.
"""

from fastapi import FastAPI
from trutina.api.features.account import router as account_router
from trutina.api.features.journal import router as journal_router
from trutina.api.features.posting import router as posting_router
from trutina.api.features.system import router as system_router
from trutina.api.features.trial_balance import router as trial_balance_router
from trutina.api.shared.errors import register_exception_handlers
from trutina.config import Settings, get_settings
from trutina.observability import CorrelationIdMiddleware, configure_logging

from .bootstrap import make_lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    A factory rather than a bare module-level `app = FastAPI(...)`
    singleton, for two reasons:

    1. Tests need to construct independent app instances bound to
        TestSettings.
    2. `settings` is accepted explicitly, mirroring build_context(),
        so tests never have to monkeypatch get_settings().

    Also the single place logging is configured for this process
    (`configure_logging`) and the correlation-id middleware is
    attached, so every route and every exception handler can rely on
    both being in place regardless of how the app was started.
    """
    if settings is None:
        settings = get_settings()

    configure_logging(settings.logging, app="api")

    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        description=settings.api.description,
        lifespan=make_lifespan(settings),
    )

    app.add_middleware(CorrelationIdMiddleware)

    register_exception_handlers(app)

    app.include_router(router=system_router)
    app.include_router(router=account_router)
    app.include_router(router=journal_router)
    app.include_router(router=posting_router)
    app.include_router(router=trial_balance_router)

    return app


app = create_app()
