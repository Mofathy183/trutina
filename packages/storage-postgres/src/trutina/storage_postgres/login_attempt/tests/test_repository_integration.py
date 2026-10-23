from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
IP = "10.0.0.1"
EMAIL = "ann@example.com"


@pytest.mark.integration
class TestPostgresLoginAttemptRepoCount:
    async def test_returns_zero_when_nothing_recorded(
        self, postgres_login_attempt_repo
    ):
        count = await postgres_login_attempt_repo.count_failures(
            ip=IP, email=EMAIL, since=NOW
        )

        assert count == 0

    async def test_counts_matching_failures(self, postgres_login_attempt_repo):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW + timedelta(minutes=1))

        count = await repo.count_failures(ip=IP, email=EMAIL, since=NOW)

        assert count == 2

    async def test_since_is_inclusive(self, postgres_login_attempt_repo):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)

        at_bound = await repo.count_failures(ip=IP, email=EMAIL, since=NOW)
        after_bound = await repo.count_failures(
            ip=IP, email=EMAIL, since=NOW + timedelta(microseconds=1)
        )

        assert (at_bound, after_bound) == (1, 0)

    async def test_isolates_by_ip(self, postgres_login_attempt_repo):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)
        await repo.record_failure(ip="10.0.0.2", email=EMAIL, at=NOW)

        count = await repo.count_failures(ip=IP, email=EMAIL, since=NOW)

        assert count == 1

    async def test_isolates_by_email(self, postgres_login_attempt_repo):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)
        await repo.record_failure(ip=IP, email="bob@example.com", at=NOW)

        count = await repo.count_failures(ip=IP, email=EMAIL, since=NOW)

        assert count == 1

    async def test_matches_email_ignoring_case_and_whitespace(
        self, postgres_login_attempt_repo
    ):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email="  ANN@Example.COM ", at=NOW)

        count = await repo.count_failures(ip=IP, email="ann@example.com", since=NOW)

        assert count == 1


@pytest.mark.integration
class TestPostgresLoginAttemptRepoStorage:
    async def test_stores_the_normalized_email_and_given_ip(
        self, postgres_login_attempt_repo, postgres_connection
    ):
        await postgres_login_attempt_repo.record_failure(
            ip="unknown", email="  ANN@Example.COM ", at=NOW
        )

        async with postgres_connection.engine.connect() as conn:
            row = (
                await conn.execute(text("SELECT ip, email_key FROM login_attempts"))
            ).one()

        assert (row.ip, row.email_key) == ("unknown", "ann@example.com")

    async def test_round_trips_an_aware_timestamp(
        self, postgres_login_attempt_repo, postgres_connection
    ):
        await postgres_login_attempt_repo.record_failure(ip=IP, email=EMAIL, at=NOW)

        async with postgres_connection.engine.connect() as conn:
            stored = (
                await conn.execute(text("SELECT attempted_at FROM login_attempts"))
            ).scalar_one()

        assert stored.tzinfo is not None
        assert stored == NOW


@pytest.mark.integration
class TestPostgresLoginAttemptRepoClear:
    async def test_clears_only_the_given_ip_and_email(
        self, postgres_login_attempt_repo
    ):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)
        await repo.record_failure(ip="10.0.0.2", email=EMAIL, at=NOW)
        await repo.record_failure(ip=IP, email="bob@example.com", at=NOW)

        await repo.clear(ip=IP, email=" ANN@example.com")

        assert await repo.count_failures(ip=IP, email=EMAIL, since=NOW) == 0
        assert await repo.count_failures(ip="10.0.0.2", email=EMAIL, since=NOW) == 1
        assert await repo.count_failures(ip=IP, email="bob@example.com", since=NOW) == 1

    async def test_clearing_an_unknown_pair_is_a_no_op(
        self, postgres_login_attempt_repo
    ):
        await postgres_login_attempt_repo.clear(ip=IP, email=EMAIL)  # must not raise


@pytest.mark.integration
class TestPostgresLoginAttemptRepoPurge:
    async def test_removes_only_rows_strictly_older_than_the_cutoff(
        self, postgres_login_attempt_repo
    ):
        repo = postgres_login_attempt_repo
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW - timedelta(seconds=1))
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW)
        await repo.record_failure(ip=IP, email=EMAIL, at=NOW + timedelta(seconds=1))

        removed = await repo.purge_before(NOW)
        remaining = await repo.count_failures(
            ip=IP, email=EMAIL, since=NOW - timedelta(days=1)
        )

        assert (removed, remaining) == (1, 2)

    async def test_purges_across_every_ip_and_email(self, postgres_login_attempt_repo):
        repo = postgres_login_attempt_repo
        old = NOW - timedelta(hours=2)
        await repo.record_failure(ip=IP, email=EMAIL, at=old)
        await repo.record_failure(ip="10.0.0.2", email="bob@example.com", at=old)

        removed = await repo.purge_before(NOW)

        assert removed == 2

    async def test_returns_zero_when_nothing_is_old_enough(
        self, postgres_login_attempt_repo
    ):
        assert await postgres_login_attempt_repo.purge_before(NOW) == 0


@pytest.mark.integration
class TestPostgresLoginAttemptRepoLogging:
    async def test_logs_neither_the_ip_nor_the_email(
        self, postgres_login_attempt_repo, caplog
    ):
        repo = postgres_login_attempt_repo
        ip, email = "203.0.113.7", "secret.person@example.com"

        with caplog.at_level("DEBUG"):
            await repo.record_failure(ip=ip, email=email, at=NOW)
            await repo.count_failures(ip=ip, email=email, since=NOW)
            await repo.clear(ip=ip, email=email)
            await repo.purge_before(NOW)

        assert ip not in caplog.text
        assert "secret.person" not in caplog.text
