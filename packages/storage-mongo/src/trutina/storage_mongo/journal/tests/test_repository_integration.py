"""Integration tests for MongoJournalRepo against a real MongoDB instance.

These tests require a running MongoDB database configured via
``TRUTINA_TEST_MONGO__URI`` and ``TRUTINA_TEST_MONGO__DB`` in ``.env.test``.
Mark: ``@pytest.mark.integration`` — excluded from the fast unit-test run.

Fixture stack
-------------
test_settings (session)
    └── mongo_connection (session)
            └── beanie_init (session)
                    └── clean_db (function)  ← truncates docs, keeps indexes
                            └── mongo_journal_repo (function)

``clean_db`` uses ``delete_many({})`` rather than ``drop_collection()`` so the
unique indexes Beanie creates during ``beanie_init`` are preserved across the
session. If indexes were dropped, uniqueness tests would silently pass when
they should fail.

The ``counters`` collection is truncated by ``clean_db`` (it appears in
``list_collection_names()`` once ``next_journal_number()`` has been called),
so counter tests always start from a predictable state within a test.
However, the counter collection may not yet exist at the start of a fresh
session — the first call to ``next_journal_number()`` creates it via
``upsert=True``. This is expected behavior and does not require special
fixture handling.

Coverage
--------
- save: persist, retrieve, duplicate journal_number error.
- get_by_number: found, not found, returns JournalEntry instance.
- list_entries: empty, single, multiple, ascending order.
- next_journal_number: starts at 1, sequential, distinct.
- Decimal round-trip: amounts survive write → read with full precision.
- Embedded lines: line count, account names, amounts survive round-trip.
- Timestamps: created_at set on insert, updated_at equals created_at
    (journal entries are immutable, so these are set once and never advanced).
- Index integrity: unique journal_number enforced after clean_db.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from trutina.core.journal.repo import JournalRepo
from trutina.core.journal.schemas import JournalEntry
from trutina.infrastructure.mongo.journal import JournalDocument
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    make_credit_line,
    make_debit_line,
    make_journal_entry,
)


def _floor_to_milliseconds(dt: datetime) -> datetime:
    """Match MongoDB's BSON datetime precision.

    BSON truncates sub-millisecond precision on write. A locally captured
    ``datetime.now(UTC)`` (microsecond precision) can land in the same
    millisecond bucket as a write that happens microseconds later. Flooring
    to milliseconds prevents false assertion failures caused by this
    precision mismatch.
    """
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


@pytest.mark.integration
class TestMongoJournalRepoSave:
    async def test_persists_entry(self, mongo_journal_repo: JournalRepo):
        entry = make_journal_entry(journal_number=1)

        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)
        assert result is not None
        assert result.journal_number == 1

    async def test_persists_posting_date(self, mongo_journal_repo: JournalRepo):
        posting_date = datetime(2024, 6, 15)
        entry = make_journal_entry(journal_number=1, posting_date=posting_date)

        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)
        assert result is not None
        assert result.posting_date == posting_date

    async def test_persists_description(self, mongo_journal_repo: JournalRepo):
        entry = make_journal_entry(journal_number=1, description="Opening balance")

        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)
        assert result is not None
        assert result.description == "Opening balance"

    async def test_persists_none_description(self, mongo_journal_repo: JournalRepo):
        entry = make_journal_entry(journal_number=1, description=None)

        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)
        assert result is not None
        assert result.description is None

    async def test_raises_on_duplicate_journal_number(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        with pytest.raises(AppError) as exc_info:
            await mongo_journal_repo.save(entry)

        assert exc_info.value.code == ErrorCode.DUPLICATE_JOURNAL_NUMBER
        assert exc_info.value.context["field"] == "journal_number"
        assert exc_info.value.context["value"] == "1"
        assert exc_info.value.context["resource"] == "journal_entry"


@pytest.mark.integration
class TestMongoJournalRepoGetByNumber:
    async def test_returns_entry_when_found(self, mongo_journal_repo: JournalRepo):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        assert result.journal_number == 1

    async def test_returns_none_when_not_found(self, mongo_journal_repo: JournalRepo):
        result = await mongo_journal_repo.get_by_number(999)

        assert result is None

    async def test_returns_journal_entry_instance(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert isinstance(result, JournalEntry)

    async def test_entry_is_balanced_on_retrieval(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        assert result.is_balanced is True


@pytest.mark.integration
class TestMongoJournalRepoListEntries:
    async def test_returns_empty_list_when_no_entries(
        self, mongo_journal_repo: JournalRepo
    ):
        result = await mongo_journal_repo.list_entries()

        assert result == []

    async def test_returns_single_entry(self, mongo_journal_repo: JournalRepo):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        result = await mongo_journal_repo.list_entries()

        assert len(result) == 1
        assert result[0].journal_number == 1

    async def test_returns_all_entries(self, mongo_journal_repo: JournalRepo):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))
        await mongo_journal_repo.save(make_journal_entry(journal_number=2))
        await mongo_journal_repo.save(make_journal_entry(journal_number=3))

        result = await mongo_journal_repo.list_entries()

        assert len(result) == 3

    async def test_returns_entries_sorted_by_journal_number_ascending(
        self, mongo_journal_repo: JournalRepo
    ):
        await mongo_journal_repo.save(make_journal_entry(journal_number=3))
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))
        await mongo_journal_repo.save(make_journal_entry(journal_number=2))

        result = await mongo_journal_repo.list_entries()

        assert [e.journal_number for e in result] == [1, 2, 3]

    async def test_returns_journal_entry_instances(
        self, mongo_journal_repo: JournalRepo
    ):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        result = await mongo_journal_repo.list_entries()

        assert all(isinstance(e, JournalEntry) for e in result)


@pytest.mark.integration
class TestMongoJournalRepoNextJournalNumber:
    async def test_first_call_returns_one(self, mongo_journal_repo: JournalRepo):
        result = await mongo_journal_repo.next_journal_number()

        assert result == 1

    async def test_sequential_calls_return_incrementing_values(
        self, mongo_journal_repo: JournalRepo
    ):
        first = await mongo_journal_repo.next_journal_number()
        second = await mongo_journal_repo.next_journal_number()
        third = await mongo_journal_repo.next_journal_number()

        assert first == 1
        assert second == 2
        assert third == 3

    async def test_returns_distinct_values_on_each_call(
        self, mongo_journal_repo: JournalRepo
    ):
        numbers = [await mongo_journal_repo.next_journal_number() for _ in range(5)]

        assert len(set(numbers)) == 5

    async def test_returned_value_is_positive(self, mongo_journal_repo: JournalRepo):
        result = await mongo_journal_repo.next_journal_number()

        assert result > 0


@pytest.mark.integration
class TestDecimalRoundTrip:
    async def test_debit_amount_survives_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        amount = Decimal("123.45")
        entry = make_journal_entry(
            journal_number=1,
            lines=[
                make_debit_line(amount=amount),
                make_credit_line(amount=amount),
            ],
        )
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        debit_line = next(line for line in result.lines if line.debit_amount > 0)
        assert debit_line.debit_amount == amount

    async def test_credit_amount_survives_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        amount = Decimal("99.99")
        entry = make_journal_entry(
            journal_number=1,
            lines=[
                make_debit_line(amount=amount),
                make_credit_line(amount=amount),
            ],
        )
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        credit_line = next(line for line in result.lines if line.credit_amount > 0)
        assert credit_line.credit_amount == amount

    async def test_high_precision_amount_survives_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        amount = Decimal("1234567890.12")
        entry = make_journal_entry(
            journal_number=1,
            lines=[
                make_debit_line(amount=amount),
                make_credit_line(amount=amount),
            ],
        )
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        debit_line = next(line for line in result.lines if line.debit_amount > 0)
        assert debit_line.debit_amount == amount


@pytest.mark.integration
class TestEmbeddedLines:
    async def test_line_count_survives_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        assert len(result.lines) == 2

    async def test_account_names_survive_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(journal_number=1)
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        accounts = {line.account for line in result.lines}
        assert "Cash" in accounts
        assert "Sales Revenue" in accounts

    async def test_multi_line_entry_survives_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        entry = make_journal_entry(
            journal_number=1,
            lines=[
                make_debit_line(amount=Decimal("300")),
                make_credit_line(amount=Decimal("200")),
                make_credit_line(account="Accounts Payable", amount=Decimal("100")),
            ],
        )
        await mongo_journal_repo.save(entry)

        result = await mongo_journal_repo.get_by_number(1)

        assert result is not None
        assert len(result.lines) == 3
        assert result.total_debits == Decimal("300")
        assert result.total_credits == Decimal("300")
        assert result.is_balanced is True


@pytest.mark.integration
class TestMongoJournalRepoTimestamps:
    async def test_created_at_is_set_on_save(self, mongo_journal_repo: JournalRepo):
        before = _floor_to_milliseconds(datetime.now(UTC))
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))
        after = datetime.now(UTC)

        doc = await JournalDocument.find_one(JournalDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at is not None

        created_at = doc.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        assert before <= created_at <= after

    async def test_updated_at_equals_created_at_after_save(
        self, mongo_journal_repo: JournalRepo
    ):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        doc = await JournalDocument.find_one(JournalDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at == doc.updated_at

    async def test_timestamps_are_naive_after_database_round_trip(
        self, mongo_journal_repo: JournalRepo
    ):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        doc = await JournalDocument.find_one(JournalDocument.journal_number == 1)

        assert doc is not None
        assert doc.created_at is not None
        assert doc.created_at.tzinfo is None


@pytest.mark.integration
class TestAmountNotStoredAsFloat:
    async def test_amounts_not_stored_as_float_in_bson(
        self, mongo_journal_repo: JournalRepo, clean_db
    ):
        amount = Decimal("99.99")
        entry = make_journal_entry(
            journal_number=1,
            lines=[
                make_debit_line(amount=amount),
                make_credit_line(amount=amount),
            ],
        )
        await mongo_journal_repo.save(entry)

        raw = await clean_db["journal_entries"].find_one({"journal_number": 1})

        assert raw is not None
        for line in raw["lines"]:
            assert isinstance(line["debit_amount"], str)
            assert isinstance(line["credit_amount"], str)


@pytest.mark.integration
class TestIndexIntegrityAfterCleanDb:
    async def test_unique_journal_number_index_enforced_after_cleanup(
        self, mongo_journal_repo: JournalRepo
    ):
        await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        with pytest.raises(AppError) as exc_info:
            await mongo_journal_repo.save(make_journal_entry(journal_number=1))

        assert exc_info.value.code == ErrorCode.DUPLICATE_JOURNAL_NUMBER
