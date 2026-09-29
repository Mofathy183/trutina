"""Autouse test isolation for logging configuration.

Removes only the handler configure_logging() installs itself (tracked
by a marker attribute), so pytest's own caplog handler is never
disturbed, and clears any correlation id left bound if a test exits
mid-scope.
"""

import logging

import pytest
from trutina.observability.configure import _INSTALLED_HANDLER_ATTR


@pytest.fixture(autouse=True)
def _reset_observability_logging():
    yield
    root = logging.getLogger()
    handler = getattr(root, _INSTALLED_HANDLER_ATTR, None)
    if handler is not None and handler in root.handlers:
        root.removeHandler(handler)
        delattr(root, _INSTALLED_HANDLER_ATTR)
