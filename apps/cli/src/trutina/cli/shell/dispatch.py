"""Dispatch helpers for the Trutina interactive shell.

Owns exactly two things: turning a raw stripped line into parsed
argv (`parse_line`), and running it through the real Typer app,
either as a normal command (`dispatch`) or as `--help` for some
target path (`run_help`, shared by both the leading `help <target>`
and trailing `<target> help` shorthands). Split out of loop.py so the
loop itself reads as a plain read-a-line -> decide-what-it-is ->
run-it sequence, with no Click/Typer exception handling in view.

Correlation: `dispatch()` and `run_help()` each wrap their own
`app(...)` call in `correlation_scope()`, so every line typed in the
shell -- including a bare `help <target>` -- gets its own id, the same
as a one-shot invocation gets in `main.py::run()`. This is what keeps
a long-running shell session from having every command share a single
correlation id.

Confirmed empirically (see diag_milestone2.py, not assumed):

- A command that fails at the domain/validation level (AppError,
    ValidationAppError, pydantic.ValidationError) is already fully
    handled by that command's own error_boundary() before control
    returns here -- the panel is printed and app(...) returns normally.
    Neither function below does anything extra for that case.
- The only case that raises back to the caller is a genuine Click
    usage error (unknown command, bad/missing flag). This Typer version
    (0.27.2) vendors its own Click fork internally rather than routing
    through the public `click` package, so `click.UsageError` does NOT
    match it -- confirmed via MRO inspection. The public, stable ancestor
    across that whole vendored exception family is
    `typer.exceptions.TyperException`, which both functions below catch.
"""

import shlex

from rich.text import Text
from trutina.cli.composition import CliState, app
from trutina.cli.shared.ui import console
from trutina.observability import correlation_scope
from typer.exceptions import TyperException


def run_help(state: CliState, target: list[str]) -> None:
    """Show help for `target`, exactly as `<target...> --help` would.

    Shared by both help shorthands the shell accepts -- leading
    `help <target...>` and trailing `<target...> help` -- so there is
    exactly one place that turns a target into a real `--help`
    dispatch through the app.

    Args:
        state: The CliState for this session, passed through unchanged
            to the underlying app(...) dispatch.
        target: The command path to show help for, e.g. `[]` for
            top-level help, `["account"]`, or `["journal", "create"]`.
    """
    with correlation_scope():
        try:
            app([*target, "--help"], obj=state, standalone_mode=False)
        except TyperException as exc:
            console.print(Text(str(exc) or type(exc).__name__, style="warning"))


def parse_line(stripped: str) -> list[str] | None:
    """Shlex-split an already-stripped line into argv.

    Args:
        stripped: The line with a leading '/' already removed and
            surrounding whitespace already trimmed.

    Returns:
        The parsed argument list, or None if `stripped` contains
        unbalanced quoting -- the warning is already printed to the
        console in that case, so the caller only needs to check for
        None and continue its loop.
    """
    try:
        return shlex.split(stripped)
    except ValueError as exc:
        console.print(Text(f"Could not parse input: {exc}", style="warning"))
        return None


def dispatch(state: CliState, args: list[str]) -> None:
    """Dispatch already-parsed args through the real Typer app.

    This is the only place a normal (non-help) line reaches the app --
    every one-shot invocation goes through the same `app(...)` call
    via main.py, so behavior here is identical to running
    `trutina-cli <args>` directly, apart from the correlation id
    being bound per shell line here rather than once for the whole
    one-shot invocation.

    Args:
        state: The CliState for this session.
        args: The shlex-parsed argument list, e.g. `["account", "list"]`.
    """
    with correlation_scope():
        try:
            app(args, obj=state, standalone_mode=False)
        except TyperException as exc:
            console.print(Text(str(exc) or type(exc).__name__, style="warning"))
