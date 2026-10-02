"""
Root pytest configuration: fixture plugin registration and marker enforcement.

This file is collected once per test session (pytest.ini's `pythonpath = .`
makes it discoverable from the repo root) and is responsible for two
cross-cutting concerns that no individual package should have to repeat:

1. Registering the shared fixture plugins used across packages/apps.
2. Enforcing Trutina's three-axis marker discipline (see
    `pytest_collection_modifyitems` below) so `pytest -m "unit and cli"`,
    `pytest -m "integration and infra and postgres"`, etc. remain
    trustworthy filters instead of decorative, hand-maintained metadata
    that silently drifts from the code's real location.
"""

import pathlib

import pytest

pytest_plugins = [
    "tests.fixtures.account",
    "tests.fixtures.posting",
    "tests.fixtures.journal",
    "tests.fixtures.mongo",
    "tests.fixtures.postgres",
    "tests.fixtures.settings",
    "tests.fixtures.services",
    "tests.fixtures.cli",
    "tests.fixtures.api",
    "tests.fixtures.logging",
]

# ── Marker taxonomy ──────────────────────────────────────────────────────
#
#   Speed axis    {"unit", "integration"} -- hand-written on the test. Whether
#                 a test performs real I/O is a fact about its body, not its
#                 location, so it can never be derived.
#
#   Layer axis    derived from the test file's location, never hand-written.
#                 "infra" names the architectural role of a storage adapter
#                 (cli|api -> infra -> core -> shared|config), not a specific
#                 package.
#
#   Backend axis  {"mongo", "postgres"} -- derived from location, and only
#                 for "infra" tests. Storage adapters need different real
#                 services in CI, which the layer axis cannot express.
#
# Derivation uses ONE table keyed by the first two segments of the test's
# path RELATIVE TO THE REPO ROOT ("apps/cli", "packages/storage-postgres").
# Matching on the relative two-segment prefix (rather than any path segment
# of the absolute path) means a checkout living under a directory called
# "core" or "config", or a stray "core/" folder inside another package,
# can never change a test's markers.
#
# Adding a package = one line here + one line in pytest.ini's `markers`
# (if it introduces a new layer marker). A test under an unlisted prefix
# fails collection loudly.
_PACKAGE_MARKERS: dict[str, tuple[str, str | None]] = {
    # prefix: (layer marker, backend marker | None)
    "apps/cli": ("cli", None),
    "apps/api": ("api", None),
    "packages/core": ("core", None),
    "packages/shared": ("shared", None),
    "packages/config": ("config", None),
    "packages/observability": ("observability", None),
    "packages/authentication": ("authentication", None),
    "packages/storage-mongo": ("infra", "mongo"),
    "packages/storage-postgres": ("infra", "postgres"),
}

_SPEED_MARKERS: frozenset[str] = frozenset({"unit", "integration"})
_LAYER_MARKERS: frozenset[str] = frozenset(
    layer for layer, _backend in _PACKAGE_MARKERS.values()
)
_BACKEND_MARKERS: frozenset[str] = frozenset(
    backend for _layer, backend in _PACKAGE_MARKERS.values() if backend is not None
)


def _classify(rel_parts: tuple[str, ...]) -> tuple[str, str | None] | None:
    """Map a repo-relative test path to its (layer, backend) markers.

    Args:
        rel_parts: The test file's path relative to the repo root, split
            via ``Path.parts``.

    Returns:
        ``(layer, backend)`` where ``backend`` is None for non-infra
        layers, or None if the path's first two segments are not a known
        package/app directory.
    """
    if len(rel_parts) < 2:
        return None
    return _PACKAGE_MARKERS.get(f"{rel_parts[0]}/{rel_parts[1]}")


def pytest_configure(config: pytest.Config) -> None:
    """Fail fast if the taxonomy and pytest.ini's registered markers diverge.

    ``--strict-markers`` already rejects an unregistered marker once
    something tries to apply it, but only at the moment a matching test is
    collected. Checking here makes adding a package to ``_PACKAGE_MARKERS``
    without registering its layer marker fail immediately, with a message
    that says what to fix.

    Raises:
        pytest.UsageError: If any taxonomy marker is not registered in
            pytest.ini's ``markers``.
    """
    registered = {
        line.split(":", 1)[0].split("(", 1)[0].strip()
        for line in config.getini("markers")
    }
    expected = _SPEED_MARKERS | _LAYER_MARKERS | _BACKEND_MARKERS
    missing = sorted(expected - registered)
    if missing:
        raise pytest.UsageError(
            f"conftest.py taxonomy markers not registered in pytest.ini: {missing}"
        )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Enforce and auto-apply Trutina's three-axis test marker discipline.

    Every collected test must carry exactly one hand-written speed marker.
    Its layer marker (and, for infra tests, backend marker) is derived from
    its location and applied here. Hand-writing a layer or backend marker is
    an error, even when it happens to agree with the location: the marker
    must come from where the file lives, so it cannot rot. A test outside
    any known package directory is also an error.

    All violations are collected and reported in one batch via
    ``pytest.UsageError``, mirroring ``--strict-markers``: marker hygiene is
    a correctness gate, because targeted ``-m`` runs in CI and
    ``tools/pre-push.sh`` depend on markers being accurate.

    Args:
        config: The pytest session config; ``rootpath`` anchors the
            repo-relative path used for derivation.
        items: All collected test items, mutated in place by adding the
            derived layer (and backend) markers.

    Raises:
        pytest.UsageError: If any item lacks exactly one speed marker,
            hand-writes a layer or backend marker, or lives outside every
            known package directory.
    """
    violations: list[str] = []

    for item in items:
        own_markers = {marker.name for marker in item.iter_markers()}

        # --- Speed axis: hand-written, exactly one. ---
        declared_speed = _SPEED_MARKERS & own_markers
        if len(declared_speed) != 1:
            violations.append(
                f"{item.nodeid}: must carry exactly one of "
                f"{sorted(_SPEED_MARKERS)}, found {sorted(declared_speed)}"
            )

        # --- Layer/backend axes: derived, never hand-written. ---
        hand_written = (_LAYER_MARKERS | _BACKEND_MARKERS) & own_markers
        if hand_written:
            violations.append(
                f"{item.nodeid}: hand-writes {sorted(hand_written)} -- remove it; "
                f"layer and backend markers are derived from the file's location"
            )

        try:
            rel_parts = pathlib.Path(item.path).relative_to(config.rootpath).parts
        except ValueError:
            violations.append(f"{item.nodeid}: file is outside the repo root")
            continue

        classified = _classify(rel_parts)
        if classified is None:
            violations.append(
                f"{item.nodeid}: path does not start with a known package "
                f"directory; move it under one of {sorted(_PACKAGE_MARKERS)} "
                f"or add its prefix to _PACKAGE_MARKERS in conftest.py"
            )
            continue

        layer, backend = classified
        item.add_marker(getattr(pytest.mark, layer))
        if backend is not None:
            item.add_marker(getattr(pytest.mark, backend))

    if violations:
        report = "\n".join(f"  - {violation}" for violation in violations)
        raise pytest.UsageError(f"Marker validation failed:\n{report}")
