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
    that silently drifts from the code's real location — the same kind
    of staleness this repo has already documented elsewhere (e.g.
    `cli/constants/errors.py` vs. `shared/errors`).
"""

import pathlib

import pytest

pytest_plugins = [
    "tests.fixtures.account",
    "tests.fixtures.posting",
    "tests.fixtures.journal",
    "tests.fixtures.mongo",
    "tests.fixtures.settings",
    "tests.fixtures.services",
    "tests.fixtures.cli",
    "tests.fixtures.api",
]

# ── Marker taxonomy ──────────────────────────────────────────────────────
#
# Every collected test must resolve to exactly one speed marker (hand-
# written) and exactly one layer marker (derived from its file path).
# Infra-layer tests additionally resolve to exactly one backend marker
# (also derived from path). Non-infra tests must never carry a backend
# marker at all.
#
#   Speed axis    {"unit", "integration"} — hand-written on the test
#                 itself. Whether a test performs real I/O is a fact
#                 about its own body, not its file location, so it can
#                 never be derived and must always be written explicitly.
#
#   Layer axis    {"core", "infra", "cli", "api", "shared"} — derived
#                 from the test file's path and applied automatically.
#                 Hand-writing a layer marker is a collection error: the
#                 marker must always agree with where the file actually
#                 lives, so letting it be derived is what keeps it from
#                 rotting. "infra" is the architectural layer from the
#                 workspace's layered-architecture contract
#                 (cli|api -> infrastructure -> core -> shared|config) —
#                 it names a role, not a specific package, which is
#                 exactly why it stays "infra" even as the packages that
#                 fill that role change (trutina-infrastructure ->
#                 trutina-storage-mongo, with trutina-storage-postgres
#                 joining it).
#
#   Backend axis  {"mongo", "postgres"} — derived from path, but only
#                 meaningful for infra-layer tests. Two storage adapters
#                 implementing the same repository contracts need
#                 different real backing services in CI (a mongo:8
#                 container vs. a postgres:16 container), so integration
#                 tests need a way to be selected per-backend that the
#                 layer axis alone can't express. A non-infra test must
#                 never carry a backend marker — there is nothing for it
#                 to mean outside the infra layer.
#
# The layer and speed axes are fully orthogonal to each other, exactly as
# before. The backend axis is not orthogonal to layer — it only applies
# where layer == "infra" — which is why it's derived and validated
# separately rather than folded into _LAYER_DIRS as another peer entry.

_SPEED_MARKERS: frozenset[str] = frozenset({"unit", "integration"})
_LAYER_MARKERS: frozenset[str] = frozenset({"core", "infra", "cli", "api", "shared"})

# Directory name -> layer marker, checked in this order, for layers that
# map 1:1 onto a single owning directory. Order only matters for the
# (currently hypothetical) case where a path could contain more than one
# of these directory names — e.g. a future apps/api/core/ package. The
# first match wins, so more specific/authoritative directory names should
# be listed first if that situation ever arises.
#
# "infra" is deliberately NOT listed here — it has more than one owning
# directory (one per storage backend), so it's derived from _BACKEND_DIRS
# below instead, the same reason "shared" is derived from _SHARED_DIRS
# rather than listed here directly.
_LAYER_DIRS: dict[str, str] = {
    "core": "core",
    "cli": "cli",
    "api": "api",
}

# Directory names that both map to the single "shared" layer marker.
# Kept as a separate set (rather than folded into _LAYER_DIRS) because
# "shared" is the one layer with more than one owning directory
# (root shared/ and config/), and because the marker name intentionally
# does not match either directory name 1:1.
_SHARED_DIRS: frozenset[str] = frozenset({"shared", "config"})

# Storage-backend package directory -> backend marker. Every entry here
# implies BOTH the "infra" layer marker and the named backend marker —
# adding a new storage adapter (e.g. trutina-storage-postgres) means
# adding exactly one line here, nothing else in this file changes.
_BACKEND_DIRS: dict[str, str] = {
    "storage_mongo": "mongo",
    "storage_postgres": "postgres",
}

_BACKEND_MARKERS: frozenset[str] = frozenset(_BACKEND_DIRS.values())


def _derive_layer(path_parts: tuple[str, ...]) -> str | None:
    """Infer a test's layer marker from its file path.

    Checks the single-directory layer mappings first (`_LAYER_DIRS`),
    then falls back to "infra" if the path passes through a known
    storage-backend directory (`_BACKEND_DIRS`), then falls back to
    "shared" if the path passes through one of `_SHARED_DIRS`. Returns
    None when the path matches none of these, which the caller treats as
    a hard collection error rather than an unmarked test — an
    unrecognized location almost always means one of these mappings
    needs a new entry for a new package, not that the test should go
    unclassified.

    Args:
        path_parts: The test file's path, pre-split via `Path.parts` so
            matching is exact-segment (e.g. "core") rather than a raw
            substring search that could false-positive on something like
            "cliff/".

    Returns:
        The derived layer marker name, or None if no known directory
        segment was found.
    """
    for dirname, marker in _LAYER_DIRS.items():
        if dirname in path_parts:
            return marker

    if any(backend_dir in path_parts for backend_dir in _BACKEND_DIRS):
        return "infra"

    if any(shared_dir in path_parts for shared_dir in _SHARED_DIRS):
        return "shared"

    return None


def _derive_backend(path_parts: tuple[str, ...]) -> str | None:
    """Infer a test's backend marker from its file path, if any.

    Returns None for any test outside a known storage-backend directory —
    this is the expected, common case for the large majority of tests
    (core, cli, api, shared all return None here), not an error condition
    on its own. The caller decides whether None is actually valid given
    the test's derived layer.

    Args:
        path_parts: The test file's path, pre-split via `Path.parts`.

    Returns:
        The derived backend marker name ("mongo", "postgres", ...), or
        None if the path doesn't pass through a known storage-backend
        directory.
    """
    for dirname, marker in _BACKEND_DIRS.items():
        if dirname in path_parts:
            return marker

    return None


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Enforce and auto-apply Trutina's three-axis test marker discipline.

    Every collected test must resolve to exactly one speed marker
    (hand-written) and exactly one layer marker (derived from its file
    path and applied here). A test whose derived layer is "infra" must
    additionally resolve to exactly one backend marker (also derived and
    applied here); a test whose derived layer is anything else must
    resolve to no backend marker at all. This hook is the single source
    of truth for all three checks, so a mis-tagged or unclassified test
    fails collection loudly, in one batched report, rather than silently
    producing a marker filter (`pytest -m "unit and infra and postgres"`)
    that quietly excludes or includes the wrong tests.

    Deliberately fails the whole collection (via `pytest.UsageError`)
    rather than warning, mirroring `--strict-markers` already configured
    in pytest.ini: marker hygiene here is a correctness gate, not a
    lint suggestion, because every other convention in this document
    (targeted `-m` runs in CI, `tools/pre-push.sh`) depends on markers
    being accurate.

    Args:
        config: The pytest session config (required by the hook
            signature; unused here).
        items: All collected test items, mutated in place by adding the
            derived layer marker, and the derived backend marker where
            applicable, to each.

    Raises:
        pytest.UsageError: If any item is missing a speed marker, carries
            more than one speed marker, has a hand-written layer marker
            that disagrees with its derived path-based marker, lives at
            a path that doesn't resolve to any known layer, carries a
            backend marker its derived layer doesn't call for, or (for
            an infra-layer test) has a hand-written backend marker that
            disagrees with its derived path-based backend.
    """
    violations: list[str] = []

    for item in items:
        path_parts = pathlib.Path(str(item.fspath)).parts
        own_markers = {marker.name for marker in item.iter_markers()}

        # --- Speed axis: must be hand-written, exactly one. ---
        declared_speed = _SPEED_MARKERS.intersection(own_markers)
        if len(declared_speed) != 1:
            violations.append(
                f"{item.nodeid}: must carry exactly one of "
                f"{sorted(_SPEED_MARKERS)}, found {sorted(declared_speed)}"
            )

        # --- Layer axis: derived from path, exactly one, never hand-written. ---
        derived_layer = _derive_layer(path_parts)
        declared_layer = _LAYER_MARKERS.intersection(own_markers)

        if derived_layer is None:
            violations.append(
                f"{item.nodeid}: path does not map to any known layer "
                f"{sorted(_LAYER_MARKERS)}; move the file under a "
                f"recognized package directory or update _LAYER_DIRS/"
                f"_BACKEND_DIRS/_SHARED_DIRS in conftest.py"
            )
        elif declared_layer and declared_layer != {derived_layer}:
            violations.append(
                f"{item.nodeid}: path implies layer marker "
                f"'{derived_layer}' but test declares "
                f"{sorted(declared_layer)} — remove the hand-written "
                f"layer marker; layer markers are derived from file "
                f"path, never authored on the test"
            )
        else:
            item.add_marker(getattr(pytest.mark, derived_layer))

        # --- Backend axis: derived from path, only meaningful for infra. ---
        derived_backend = _derive_backend(path_parts)
        declared_backend = _BACKEND_MARKERS.intersection(own_markers)

        if derived_layer == "infra" and derived_backend is None:
            violations.append(
                f"{item.nodeid}: resolves to the 'infra' layer but its "
                f"path doesn't match any entry in _BACKEND_DIRS — every "
                f"infra-layer test must live under a known storage-"
                f"backend directory"
            )
        elif derived_layer != "infra" and (derived_backend or declared_backend):
            violations.append(
                f"{item.nodeid}: carries or implies a backend marker "
                f"{sorted(declared_backend) or [derived_backend]} but "
                f"its layer is '{derived_layer}', not 'infra' — backend "
                f"markers only apply to infra-layer tests"
            )
        elif declared_backend and declared_backend != {derived_backend}:
            violations.append(
                f"{item.nodeid}: path implies backend marker "
                f"'{derived_backend}' but test declares "
                f"{sorted(declared_backend)} — remove the hand-written "
                f"backend marker; backend markers are derived from file "
                f"path, never authored on the test"
            )
        elif derived_backend is not None:
            item.add_marker(getattr(pytest.mark, derived_backend))

    if violations:
        report = "\n".join(f"  - {violation}" for violation in violations)
        raise pytest.UsageError(f"Marker validation failed:\n{report}")
