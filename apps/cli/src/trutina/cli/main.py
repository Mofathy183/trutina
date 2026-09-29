"""Console-script entry point for the Trutina CLI.

This is the only place in the application that opens the CLI's single
event loop, via ``start_blocking_portal()``. No command, service, or
repository may create a second loop -- there is exactly one, for the
life of the process.

Logging is configured once here, in ``main()``, next to where the
portal is later opened in ``run()`` -- mirroring the API's own
composition-root wiring in ``composition/app.py``. Every one-shot
invocation is wrapped in its own ``correlation_scope()`` so every log
line it emits -- including ones logged from service/repository code
running inside the portal's event loop -- shares one id. The
interactive shell does the equivalent per dispatched line, in
``shell/dispatch.py``, rather than once for the whole session, so one
long-running shell process never has every command sharing a single
id. Phase 0 confirmed a context variable set on the calling (main)
thread reaches code run through ``BlockingPortal.call(...)`` without
needing an explicit re-bind inside ``CliState.call()``.
"""

import sys

from anyio.from_thread import start_blocking_portal
from trutina.cli.composition import CliContext, CliState, app, build_context
from trutina.cli.shell import run_shell
from trutina.config import get_settings
from trutina.observability import configure_logging, correlation_scope


def _known_commands(typer_app) -> set[str]:
    """Return the top-level command/group names Typer will dispatch directly.

    Derived from ``typer_app.registered_groups`` so a new feature (a
    future ``reporting`` group, say) is picked up automatically --
    nothing here needs to change when app.py registers a new group.
    """
    return {group.name for group in typer_app.registered_groups if group.name}


def _help_flags(typer_app) -> set[str]:
    """Return the flag strings that trigger Typer/Click's own help output.

    Derived from ``typer_app.info.context_settings["help_option_names"]``
    -- the same setting app.py already declares
    (``context_settings={"help_option_names": ["-h", "--help"]}``) --
    rather than a second, hand-maintained ``{"--help", "-h"}`` literal
    here that could silently drift out of sync with app.py's own
    configuration.
    """
    context_settings = typer_app.info.context_settings or {}
    return set(context_settings.get("help_option_names", ["--help"]))


def _should_enter_shell(argv: list[str], typer_app) -> bool:
    """Decide whether argv should drop into the shell or dispatch normally.

    Revised from the plan's original D1: a bare invocation enters the
    shell, matching the ``claude``/``codex``/``mongosh`` pattern. A
    help flag (``--help``/``-h``) no longer enters the shell -- it
    dispatches straight to Typer so the top-level usage text prints
    and the process exits immediately, the same way those tools'
    ``--help`` behaves. Only a first token that isn't a registered
    command name (and isn't a help flag) falls through to the shell.
    A recognized command name (``account``, etc.) always dispatches
    normally, including ``account --help``, which Typer/Click handles
    on its own once inside that command's parsing.
    """
    if not argv:
        return True
    if argv[0] in _help_flags(typer_app):
        return False
    return argv[0] not in _known_commands(typer_app)


def run(context: CliContext, *, backend: str = "asyncio") -> None:
    """Dispatch either into the shell or into Typer, and guarantee cleanup.

    A one-shot dispatch is wrapped in ``correlation_scope()`` here so
    the whole invocation -- parsing, the service call made through
    ``state.call(...)``, and ``error_boundary()``'s own failure log --
    shares one id. The shell path does not wrap here: ``run_shell()``
    dispatches many commands per process, so each one binds its own
    scope in ``shell/dispatch.py`` instead of sharing this one.
    """
    with start_blocking_portal(backend=backend) as portal:
        state = CliState(context=context, portal=portal)
        try:
            if _should_enter_shell(sys.argv[1:], app):
                run_shell(state)
            else:
                with correlation_scope():
                    app(obj=state)
        finally:
            portal.call(context.aclose)


def main() -> None:
    configure_logging(get_settings().logging, app="cli")
    context = build_context()
    run(context)


if __name__ == "__main__":
    main()
