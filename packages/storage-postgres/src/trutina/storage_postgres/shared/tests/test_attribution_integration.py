"""End-to-end test that an actor given to a service reaches the database.

Wires the real services to the real PostgreSQL repositories (the
``services`` fixture) and reads ``created_by`` back with raw SQL, since
it is not part of any domain model. Unlike the repository tests, which
supply ``created_by`` directly, this proves the whole path: caller ->
service -> repository -> column.

It lives in this package rather than in trutina-core because it reads
tables with SQLAlchemy, which trutina-core must never import.

The entry and the postings are written with different actors on
purpose, so a wiring mistake that crossed the two would fail.
"""

import pytest
from sqlalchemy import text

ENTRY_ACTOR = "system:pre-auth:api"
POSTING_ACTOR = "system:pre-auth:cli"


@pytest.mark.integration
class TestActorAttributionEndToEnd:
    async def test_actor_is_recorded_on_the_entry_and_every_posting(
        self, services, simple_accounts, postgres_connection, create_input
    ):
        _account_service, journal_service, posting_service = services

        entry = await journal_service.create_journal_entry(
            create_input, actor=ENTRY_ACTOR
        )
        await posting_service.post_journal_entry(
            entry.journal_number, actor=POSTING_ACTOR
        )

        async with postgres_connection.engine.connect() as conn:
            entry_result = await conn.execute(
                text(
                    "SELECT created_by FROM journal_entries WHERE journal_number = :n"
                ),
                {"n": entry.journal_number},
            )
            posting_result = await conn.execute(
                text(
                    "SELECT created_by FROM postings "
                    "WHERE journal_number = :n ORDER BY line_index"
                ),
                {"n": entry.journal_number},
            )
            entry_actor = entry_result.scalar_one()
            posting_actors = list(posting_result.scalars().all())

        assert entry_actor == ENTRY_ACTOR
        assert posting_actors == [POSTING_ACTOR] * 2
