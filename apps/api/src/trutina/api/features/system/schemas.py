"""Response models for the system feature.

Defines the read-only, non-domain response contracts returned by the
root and health endpoints. These carry no accounting meaning — they
describe the API process itself, not Trutina's bookkeeping domain —
so they intentionally have no relationship to any modules/*/dtos.py
view model.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ApiInfo(BaseModel):
    """Static identity of the running API process.

    Named for the process, not for a Trutina domain service — "service"
    is already claimed by AccountService/JournalService/PostingService,
    and this describes something unrelated: the running API itself.
    Transport-agnostic by design so a future GraphQL entry point can
    return the same shape rather than inventing a parallel one.
    """

    title: str
    description: str
    version: str
    transport: Literal["rest"] = "rest"


class RootResponse(BaseModel):
    """Response body for ``GET /``.

    Confirms the API is listening and points callers at both the
    human-readable docs and the machine-readable OpenAPI schema.
    Carries no business data and requires no authentication.
    """

    service: ApiInfo
    docs: str
    openapi: str = "/openapi.json"


class HealthResponse(BaseModel):
    """Response body for ``GET /health``.

    A liveness signal only — it confirms the process is running and
    able to respond, not that its dependencies are
    reachable. Add a dependency check here only by introducing a
    distinct readiness endpoint; do not overload this one.
    """

    status: Literal["ok"] = Field(default="ok")
