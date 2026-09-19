"""FastAPI application factory for the Trutina API.

app.py wires the lifespan (bootstrap.py) to a FastAPI instance and
registers routers. It performs no business logic, constructs no
services or repositories directly, and never imports Mongo-specific
infrastructure types — the same rule cli/app.py already follows for the
Typer app.
"""

from fastapi import FastAPI
from trutina.api.features.account import router as account_router
from trutina.api.features.journal import router as journal_router
from trutina.api.features.posting import router as posting_router
from trutina.api.features.system import router as system_router
from trutina.api.features.trial_balance import router as trial_balance_router
from trutina.api.shared.errors import register_exception_handlers
from trutina.config import Settings, get_settings

from .bootstrap import make_lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    A factory rather than a bare module-level `app = FastAPI(...)`
    singleton, for two reasons:

    1. Tests need to construct independent app instances bound to
        TestSettings — required by the Beanie global-registration
        isolation test, which needs two app instances coexisting in one
        test session without corrupting each other's Document
        registration.
    2. `settings` is accepted explicitly, mirroring build_context(),
        so tests never have to monkeypatch get_settings().
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        description=settings.api.description,
        lifespan=make_lifespan(settings),
    )

    register_exception_handlers(app)

    app.include_router(router=system_router)
    app.include_router(router=account_router)
    app.include_router(router=journal_router)
    app.include_router(router=posting_router)
    app.include_router(router=trial_balance_router)

    return app


app = create_app()
