"""Construction boundary for ``CliContext``.

``build_context()`` is the only function defined here. It resolves which
``Settings`` instance to use and constructs a ``CliContext`` from it.

Constructing a ``CliContext`` performs no I/O of its own -- no
PostgreSQL connection is opened -- regardless of what gets imported to
define the types involved. Importing this module transitively imports
``trutina.cli.context``, which in turn imports the concrete PostgreSQL
repository classes it may later construct; those imports happen at
module load time and are not I/O. The actual network connection is only
opened the first time a command calls one of ``CliContext``'s
``get_*_repo()``/``get_*_service()`` accessors -- see ``context.py`` for
that boundary.

Callers decide which ``Settings`` subclass to use and pass it in
explicitly. In production, ``main.py`` calls ``build_context()`` with no
argument, so the returned ``CliContext`` falls back to the cached
``get_settings()`` accessor. Test fixtures call it (or construct
``CliContext`` directly) with an explicit ``TestSettings`` instance. This
module never decides between ``Settings`` and ``TestSettings`` itself.
"""

from trutina.config import Settings

from .context import CliContext


def build_context(settings: Settings | None = None) -> CliContext:
    """Construct a fresh ``CliContext`` for one CLI invocation.

    Performs no I/O. The entire body is construction only -- opening a
    PostgreSQL connection and building repositories or services are all
    deferred to ``CliContext``'s own lazy accessors and happen only on
    first use, never here.

    Args:
        settings: Configuration to use for this invocation. If ``None``,
            the constructed ``CliContext`` falls back to the cached
            ``get_settings()`` accessor.

    Returns:
        A newly constructed ``CliContext``. Each call returns an
        independent instance; there is no shared state between calls.
    """
    return CliContext(settings=settings)
