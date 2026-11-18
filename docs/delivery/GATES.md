# Gates

| Gate              | Requirement                                                                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G0 (every ticket) | `ruff format --check`, `ruff check`, `ty check`, `lint-imports` (all contracts), marker hygiene, `check-lane-coverage.sh`, the lanes the ticket names, docs updated in the same PR, squash-merge. |
| G-DOCKER          | `tools/docker-smoke.sh` when a ticket touches a migration, a dependency, the Dockerfile or startup. On Windows Git Bash it needs `MSYS_NO_PATHCONV=1` and a free port 8000.                       |
| `alembic check`   | Run by hand for every migration ticket; not yet in CI or `pre-push.sh` (known gap above).                                                                                                         |
| R1                | No production deploy before M5.7 (P1). There is no auth-disabled mode at any point.                                                                                                               |
| R2                | M4a.2 and M4b.1 are never released apart, and M4a.3 is in place before either.                                                                                                                    |
| R3                | Every ticket leaves `main` valid: a contract change that temporarily drops a value (M1c.1) says so and names the ticket that stores it.                                                           |
| R4                | A unit test for one component is not evidence for a security feature. Each security criterion in the milestones above is closed only by its milestone's integration ticket (M2.8, M3.8, M5.7).    |
| R5                | Provisional contracts and thresholds are frozen only by the ticket that names them (M2.4, M3.1, M4c.2).                                                                                           |
