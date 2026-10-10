"""Integration tests for MongoPostingRepo against a real MongoDB instance.

These tests require a running MongoDB database configured via
``TRUTINA_TEST_MONGO__URI`` and ``TRUTINA_TEST_MONGO__DB`` in
``.env.test``. Mark: ``@pytest.mark.integration`` — excluded from the
fast unit-test run.

Fixture stack
-------------
test_settings (session)
    └── mongo_connection (session)
            └── beanie_init (session)
                    └── clean_db (function)  ← truncates docs, keeps indexes
                            └── mongo_posting_repo (function)

``clean_db`` truncates collections rather than dropping them, so the
session-scoped indexes created by ``beanie_init`` are preserved across
the session.

Coverage
--------
- save_many: persist, empty batch no-op, single posting, multiple
    postings, account_key/line_index/amount BSON shape.
- get_by_account: hit, miss, isolation, case-insensitivity, posting_date
    ascending order, display-cased name preserved.
- get_by_journal_number: hit, miss, isolation, line_index ascending
    order.
- Decimal round-trip including high-precision amounts.
- Timestamps: created_at set on insert, equals updated_at, naive after
    round-trip.
- Index integrity after clean_db.
- Frozen attribution: save_many() accepts the contract's ``created_by``
    and does not store it. This adapter is frozen and records no
    attribution; this test pins that as deliberate, not accidental.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from trutina.core.posting.repo import PostingRepo
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.storage_mongo.posting import PostingDocument

from tests.factories import make_credit_posting, make_debit_posting
from tests.factories.actor import TEST_ACTOR


def _floor_to_milliseconds(dt: datetime) -> datetime:
    """Match MongoDB's BSON datetime precision.

    BSON truncates sub-millisecond precision on write. Flooring a locally
    captured timestamp to the same precision avoids false failures caused
    by this mismatch.
    """
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


@pytest.mark.integration
class TestMongoPostingRepoSaveMany:
    async def test_persists_two_postings(self, mongo_posting_repo: PostingRepo):
        debit = make_debit_posting(journal_number=1)
        credit = make_credit_posting(journal_number=1)

        await mongo_posting_repo.save_many([debit, credit], created_by=TEST_ACTOR)

        result = await mongo_posting_repo.get_by_journal_number(1)
        assert len(result) == 2

    async def test_empty_list_is_a_no_op(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        await mongo_posting_repo.save_many([], created_by=TEST_ACTOR)

        count = await clean_db["postings"].count_documents({})
        assert count == 0

    async def test_persists_single_posting(self, mongo_posting_repo: PostingRepo):
        debit = make_debit_posting(journal_number=1)

        await mongo_posting_repo.save_many([debit], created_by=TEST_ACTOR)

        result = await mongo_posting_repo.get_by_journal_number(1)
        assert len(result) == 1

    async def test_persists_three_postings(self, mongo_posting_repo: PostingRepo):
        postings = [
            make_debit_posting(journal_number=1, amount=Decimal("300")),
            make_credit_posting(journal_number=1, amount=Decimal("200")),
            make_credit_posting(
                journal_number=1,
                account="Accounts Payable",
                amount=Decimal("100"),
            ),
        ]

        await mongo_posting_repo.save_many(postings, created_by=TEST_ACTOR)

        result = await mongo_posting_repo.get_by_journal_number(1)
        assert len(result) == 3

    async def test_stores_account_key_in_raw_bson(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(account="Cash")], created_by=TEST_ACTOR
        )

        raw = await clean_db["postings"].find_one({"account": "Cash"})

        assert raw is not None
        assert raw["account_key"] == "cash"

    async def test_does_not_store_is_debit_in_raw_bson(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting()], created_by=TEST_ACTOR
        )

        raw = await clean_db["postings"].find_one({})

        assert raw is not None
        assert "is_debit" not in raw

    async def test_stores_amounts_as_strings_in_raw_bson(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting()], created_by=TEST_ACTOR
        )

        raw = await clean_db["postings"].find_one({})

        assert raw is not None
        assert isinstance(raw["debit_amount"], str)
        assert isinstance(raw["credit_amount"], str)

    async def test_stores_line_index_starting_at_zero(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        debit = make_debit_posting(journal_number=1)
        credit = make_credit_posting(journal_number=1)

        await mongo_posting_repo.save_many([debit, credit], created_by=TEST_ACTOR)

        docs = (
            await clean_db["postings"]
            .find({"journal_number": 1})
            .sort("line_index", 1)
            .to_list()
        )

        assert [d["line_index"] for d in docs] == [0, 1]


@pytest.mark.integration
class TestMongoPostingRepoFrozenCreatedBy:
    async def test_accepts_created_by_and_does_not_store_it(
        self, mongo_posting_repo: PostingRepo, clean_db
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(), make_credit_posting()], created_by=TEST_ACTOR
        )

        docs = await clean_db["postings"].find({}).to_list()

        assert len(docs) == 2
        assert all("created_by" not in doc for doc in docs)


@pytest.mark.integration
class TestMongoPostingRepoGetByAccount:
    async def test_returns_empty_list_when_no_postings(
        self, mongo_posting_repo: PostingRepo
    ):
        result = await mongo_posting_repo.get_by_account("Cash")

        assert result == []

    async def test_returns_postings_for_matching_account(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(account="Cash")], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_account("Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"

    async def test_does_not_return_postings_for_other_accounts(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [
                make_debit_posting(account="Cash"),
                make_credit_posting(account="Sales Revenue"),
            ],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_account("Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"

    @pytest.mark.parametrize("variant", ["cash", "CASH", "cAsH"])
    async def test_matches_case_insensitively(
        self, mongo_posting_repo: PostingRepo, variant: str
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(account="Cash")], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_account(variant)

        assert len(result) == 1

    async def test_returns_postings_sorted_ascending_by_posting_date(
        self, mongo_posting_repo: PostingRepo
    ):
        later = make_debit_posting(account="Cash", posting_date=datetime(2024, 6, 1))
        earlier = make_debit_posting(account="Cash", posting_date=datetime(2024, 1, 1))

        await mongo_posting_repo.save_many([later, earlier], created_by=TEST_ACTOR)

        result = await mongo_posting_repo.get_by_account("Cash")

        assert [p.posting_date for p in result] == [
            datetime(2024, 1, 1),
            datetime(2024, 6, 1),
        ]

    async def test_returns_ledger_posting_instances(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting()], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_account("Cash")

        assert all(isinstance(p, LedgerPosting) for p in result)

    async def test_returns_original_display_cased_account_name(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(account="Accounts Receivable")],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_account("accounts receivable")

        assert result[0].account == "Accounts Receivable"


@pytest.mark.integration
class TestMongoPostingRepoGetByJournalNumber:
    async def test_returns_empty_list_when_no_postings(
        self, mongo_posting_repo: PostingRepo
    ):
        result = await mongo_posting_repo.get_by_journal_number(999)

        assert result == []

    async def test_returns_all_postings_for_journal_number(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [
                make_debit_posting(journal_number=1),
                make_credit_posting(journal_number=1),
            ],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert len(result) == 2
        assert all(p.journal_number == 1 for p in result)

    async def test_returns_postings_in_line_index_order(
        self, mongo_posting_repo: PostingRepo
    ):
        debit = make_debit_posting(journal_number=1, account="Cash")
        credit = make_credit_posting(journal_number=1, account="Sales Revenue")

        await mongo_posting_repo.save_many([debit, credit], created_by=TEST_ACTOR)

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert result[0].account == "Cash"
        assert result[1].account == "Sales Revenue"

    async def test_does_not_return_postings_for_other_journal_numbers(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=2)], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert len(result) == 1
        assert result[0].journal_number == 1

    async def test_returns_ledger_posting_instances(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert all(isinstance(p, LedgerPosting) for p in result)

    async def test_separates_postings_between_journal_numbers(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [
                make_debit_posting(journal_number=1),
                make_credit_posting(journal_number=1),
            ],
            created_by=TEST_ACTOR,
        )
        await mongo_posting_repo.save_many(
            [
                make_debit_posting(journal_number=2),
                make_credit_posting(journal_number=2),
            ],
            created_by=TEST_ACTOR,
        )

        result_one = await mongo_posting_repo.get_by_journal_number(1)
        result_two = await mongo_posting_repo.get_by_journal_number(2)

        assert len(result_one) == 2
        assert len(result_two) == 2
        assert all(p.journal_number == 1 for p in result_one)
        assert all(p.journal_number == 2 for p in result_two)


@pytest.mark.integration
class TestDecimalRoundTrip:
    async def test_debit_amount_survives_round_trip(
        self, mongo_posting_repo: PostingRepo
    ):
        amount = Decimal("123.45")
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1, amount=amount)],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert result[0].debit_amount == amount

    async def test_credit_amount_survives_round_trip(
        self, mongo_posting_repo: PostingRepo
    ):
        amount = Decimal("99.99")
        await mongo_posting_repo.save_many(
            [make_credit_posting(journal_number=1, amount=amount)],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert result[0].credit_amount == amount

    async def test_high_precision_amount_survives_round_trip(
        self, mongo_posting_repo: PostingRepo
    ):
        amount = Decimal("1234567890.12")
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1, amount=amount)],
            created_by=TEST_ACTOR,
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert result[0].debit_amount == amount

    async def test_zero_side_decodes_to_zero(self, mongo_posting_repo: PostingRepo):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert result[0].credit_amount == Decimal("0")


@pytest.mark.integration
class TestMongoPostingRepoTimestamps:
    async def test_created_at_is_set_on_save(self, mongo_posting_repo: PostingRepo):
        before = _floor_to_milliseconds(datetime.now(UTC))
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )
        after = datetime.now(UTC)

        doc = await PostingDocument.find_one(PostingDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at is not None

        created_at = doc.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        assert before <= created_at <= after

    async def test_updated_at_equals_created_at_after_save(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )

        doc = await PostingDocument.find_one(PostingDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at == doc.updated_at

    async def test_timestamps_are_naive_after_database_round_trip(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )

        doc = await PostingDocument.find_one(PostingDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at is not None
        assert doc.created_at.tzinfo is None


@pytest.mark.integration
class TestIndexIntegrityAfterCleanDb:
    async def test_account_lookup_still_works_after_cleanup(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(account="Cash")], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_account("Cash")

        assert len(result) == 1

    async def test_journal_number_lookup_still_works_after_cleanup(
        self, mongo_posting_repo: PostingRepo
    ):
        await mongo_posting_repo.save_many(
            [make_debit_posting(journal_number=1)], created_by=TEST_ACTOR
        )

        result = await mongo_posting_repo.get_by_journal_number(1)

        assert len(result) == 1
