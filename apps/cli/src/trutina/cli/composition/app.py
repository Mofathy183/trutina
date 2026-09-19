"""
Root command-line application for Trutina.

This module defines the main CLI entry point and registers the
available command groups. Each command group represents a bounded
area of accounting functionality, such as journal entry management.

The CLI layer is responsible only for user interaction and command
routing. Business rules and accounting validations belong to the
domain and service layers.

This module constructs the Typer app and registers an ``app.callback()``
that ensures ``ctx.obj`` carries a usable ``CliContext`` before any
command body runs. In production, ``main.py`` already constructs the
``CliContext`` inside its own async lifecycle (see ``main.py``'s
``_run()``) and passes it in via ``app(obj=context)``, so the callback's
own construction path never runs for a real invocation -- it exists as
an explicit fallback and test seam, documented on the callback itself.

``trial-balance`` is registered as a single flat command via
``app.command(...)`` rather than ``app.add_typer(...)``, unlike
account/journal/posting -- it has exactly one action (producing a
report), so a one-command Typer sub-app group would add indirection
with no benefit. See ``cli/features/trial_balance/command.py``'s module
docstring for the full rationale and the note on converting it to a
group later if group-consistency is preferred instead.
"""

import typer
from trutina.cli.features.account import app as account_app
from trutina.cli.features.journal import app as journal_app
from trutina.cli.features.posting import app as posting_app
from trutina.cli.features.trial_balance import trial_balance

from .bootstrap import build_context

app = typer.Typer(
    name="Trutina",
    help="CLI for managing ledger operations, accounts, and journal entries.",
    context_settings={"help_option_names": ["-h", "--help"]},
    suggest_commands=True,
)

app.add_typer(journal_app, name="journal")
app.add_typer(account_app, name="account")
app.add_typer(posting_app, name="posting")
app.command("trial-balance")(trial_balance)


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Ensure ``ctx.obj`` carries a ``CliContext`` before a command runs.

    In production, ``main.py`` already constructs the ``CliContext``
    inside ``async with build_context() as context: app(obj=context)``,
    so ``ctx.obj`` is never ``None`` when this callback runs for a real
    invocation, and the ``if`` branch below never executes.

    The guard exists as an explicit fallback and test seam: callers that
    invoke ``app`` through ``CliRunner`` without supplying ``obj=``
    (i.e. outside ``main.py``'s managed lifecycle) still get a usable
    ``CliContext`` here. Building it here still performs no I/O --
    ``CliContext``'s own accessors remain the only place that lazily
    open a MongoDB connection -- but a context built via this fallback
    path is *not* wrapped in ``main.py``'s ``async with`` block, so
    nothing calls ``aclose()`` on it afterward. Only rely on this
    fallback with a context that can never open a real connection (see
    ``fake_cli_context`` / ``make_fake_cli_context``); never with a path
    that might lazily touch MongoDB.

    Click/Typer resolves eager options such as ``--help`` before
    invoking this callback, so ``trutina --help`` never reaches this
    function and therefore never builds a context at all.

    Args:
        ctx: The Typer/Click context for the current invocation.
    """
    if ctx.obj is None:
        ctx.obj = build_context()
