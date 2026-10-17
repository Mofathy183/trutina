"""Router for the system feature: root and health endpoints.

Structural exception to the standard API workflow (Router → Handler →
Mapper/Service → Presenter). That pipeline exists to translate between
HTTP request/response shapes and domain DTOs — these two endpoints do
neither: there's no request body, no domain model, no AppError to
translate. Keeping this flat avoids three files that would each just
pass a value through unchanged. Promote to the full pattern only if an
endpoint here starts doing real work (e.g. aggregating dependency
health checks).

No prefix on this router by design — "/" and "/health" are root-level
paths, not namespaced under "/system". Don't copy this file's lack of
a prefix as a template for a real feature router.
"""

from fastapi import APIRouter, Depends
from trutina.api.composition.dependencies import get_settings_dep
from trutina.config import ApiSettings

from .schemas import ApiInfo, HealthResponse, RootResponse

router = APIRouter(tags=["system"])


@router.get("/", response_model=RootResponse)
async def root(
    settings: ApiSettings = Depends(get_settings_dep),
) -> RootResponse:
    """Confirm the API is listening and point callers at the docs.

    Args:
        settings: Injected API-layer settings (title, description,
            version).

    Returns:
        The service identity plus links to the interactive docs and
        the machine-readable OpenAPI schema. No authentication
        required, no business data involved.
    """
    service = ApiInfo(
        title=settings.title,
        description=settings.description,
        version=settings.version,
    )
    return RootResponse(service=service, docs="/docs")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check: confirm the process is running and responsive.

    ``HealthResponse`` for why that belongs to a future readiness
    endpoint instead.

    Returns:
        A fixed "ok" status. No authentication required.
    """
    return HealthResponse()
