"""Console-script entry point for the Trutina API.

Mirrors src/trutina/main.py's role for the CLI: the one place a process
manager or a developer invokes to start this presentation layer. Unlike
the CLI, this does not construct a Container or open any connection
itself — that entire sequence lives in bootstrap.py and only runs once
uvicorn actually starts serving `app` (see app.py / bootstrap.py).

log_config=None and access_log=False hand logging entirely to
configure_logging() (called from app.py at import time): uvicorn's own
default dictConfig-based setup is skipped, and its access log is
replaced by the structured `request.completed` line the correlation-id
middleware emits.

This module's only job is resolving Settings and handing uvicorn a
target. `uvicorn trutina.api.composition.app:app` works identically
without this file; this exists so there's one documented, discoverable
way to start the API, the same way `trutina` is for the CLI, rather
than requiring every developer to remember the equivalent uvicorn
invocation by hand.
"""

import uvicorn
from trutina.config import get_settings
from trutina.observability import configure_logging


def main() -> None:
    settings = get_settings()

    configure_logging(settings.logging, app="api")

    uvicorn.run(
        "trutina.api.composition.app:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
