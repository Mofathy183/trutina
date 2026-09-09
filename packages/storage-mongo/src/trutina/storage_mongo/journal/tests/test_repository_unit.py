from datetime import datetime
from decimal import Decimal

import pytest
from pymongo.errors import DuplicateKeyError
from trutina.core.journal.schemas import JournalEntry, JournalLine
from trutina.infrastructure.mongo.journal import (
    JournalDocument,
    JournalLineSubDocument,
    MongoJournalRepo,
)
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.errors import ErrorCode

from tests.factories import make_credit_line, make_debit_line, make_journal_entry


def _make_duplicate_key_error(key_pattern: dict) -> DuplicateKeyError:
    details = {
        "keyPattern": key_pattern,
        "keyValue": {},
        "errmsg": "E11000 duplicate key error",
        "code": 11000,
        "codeName": "DuplicateKey",
    }
    return DuplicateKeyError("E11000 duplicate key error", details=details)


@pytest.mark.unit
class TestOnDuplicate:
    def test_returns_duplicate_journal_number_when_journal_number_index_is_violated(
        self,
    ):
        repo = MongoJournalRepo(MongoExecutor())
        entry = make_journal_entry(journal_number=42)
        exc = _make_duplicate_key_error({"journal_number": 1})

        result = repo._on_duplicate(exc, entry)

        assert result.code == ErrorCode.DUPLICATE_JOURNAL_NUMBER
        assert result.context["field"] == "journal_number"
        assert result.context["value"] == "42"
        assert result.context["resource"] == "journal_entry"

    def test_returns_unknown_error_when_key_pattern_is_unrecognized(self):
        repo = MongoJournalRepo(MongoExecutor())
        entry = make_journal_entry(journal_number=1)
        exc = _make_duplicate_key_error({"some_other_field": 1})

        result = repo._on_duplicate(exc, entry)

        assert result.code == ErrorCode.UNKNOWN_ERROR
        assert result.cause is exc

    def test_returns_unknown_error_when_key_pattern_is_empty(self):
        repo = MongoJournalRepo(MongoExecutor())
        entry = make_journal_entry(journal_number=1)
        exc = _make_duplicate_key_error({})

        result = repo._on_duplicate(exc, entry)

        assert result.code == ErrorCode.UNKNOWN_ERROR

    def test_returns_unknown_error_when_duplicate_key_error_has_no_details(self):
        repo = MongoJournalRepo(MongoExecutor())
        entry = make_journal_entry(journal_number=1)
        exc = DuplicateKeyError("E11000")

        result = repo._on_duplicate(exc, entry)

        assert result.code == ErrorCode.UNKNOWN_ERROR


@pytest.mark.unit
class TestToDocument:
    def test_returns_document_with_journal_number(self, stub_journal_document_settings):
        entry = make_journal_entry(journal_number=5)

        doc = MongoJournalRepo._to_document(entry)

        assert doc.journal_number == 5

    def test_returns_document_with_posting_date(self, stub_journal_document_settings):
        posting_date = datetime(2024, 6, 15)
        entry = make_journal_entry(posting_date=posting_date)

        doc = MongoJournalRepo._to_document(entry)

        assert doc.posting_date == posting_date

    def test_returns_document_with_description(self, stub_journal_document_settings):
        entry = make_journal_entry(description="Opening balance")

        doc = MongoJournalRepo._to_document(entry)

        assert doc.description == "Opening balance"

    def test_returns_document_with_none_description(
        self, stub_journal_document_settings
    ):
        entry = make_journal_entry(description=None)

        doc = MongoJournalRepo._to_document(entry)

        assert doc.description is None

    def test_returns_document_with_correct_line_count(
        self, stub_journal_document_settings
    ):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        assert len(doc.lines) == 2

    def test_encodes_debit_amount_as_string(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        debit_line = next(line for line in doc.lines if line.debit_amount != "0")
        assert isinstance(debit_line.debit_amount, str)
        assert debit_line.debit_amount == "100"

    def test_encodes_credit_amount_as_string(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        credit_line = next(line for line in doc.lines if line.credit_amount != "0")
        assert isinstance(credit_line.credit_amount, str)
        assert credit_line.credit_amount == "100"

    def test_encodes_zero_debit_as_string_zero(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        credit_line = next(line for line in doc.lines if line.credit_amount != "0")
        assert credit_line.debit_amount == "0"

    def test_preserves_decimal_precision_in_encoding(
        self, stub_journal_document_settings
    ):
        entry = make_journal_entry(
            lines=[
                make_debit_line(amount=Decimal("99.99")),
                make_credit_line(amount=Decimal("99.99")),
            ]
        )

        doc = MongoJournalRepo._to_document(entry)

        debit_line = next(line for line in doc.lines if line.debit_amount != "0")
        assert debit_line.debit_amount == "99.99"

    def test_preserves_account_name(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        accounts = {line.account for line in doc.lines}
        assert "Cash" in accounts
        assert "Sales Revenue" in accounts

    def test_sets_updated_at(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        assert doc.updated_at is not None

    def test_does_not_set_created_at(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        assert doc.created_at is None

    def test_returns_journal_document_instance(self, stub_journal_document_settings):
        entry = make_journal_entry()

        doc = MongoJournalRepo._to_document(entry)

        assert isinstance(doc, JournalDocument)


@pytest.mark.unit
class TestToDomain:
    def _make_doc(
        self,
        *,
        journal_number: int = 1,
        posting_date: datetime | None = None,
        description: str | None = "Test entry",
        debit_amount: str = "100",
        credit_amount: str = "100",
    ) -> JournalDocument:
        if posting_date is None:
            posting_date = datetime(2025, 1, 1)

        return JournalDocument.model_construct(
            journal_number=journal_number,
            posting_date=posting_date,
            description=description,
            lines=[
                JournalLineSubDocument(
                    account="Cash",
                    debit_amount=debit_amount,
                    credit_amount="0",
                ),
                JournalLineSubDocument(
                    account="Sales Revenue",
                    debit_amount="0",
                    credit_amount=credit_amount,
                ),
            ],
        )

    def test_returns_journal_entry_with_journal_number(self):
        doc = self._make_doc(journal_number=7)

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.journal_number == 7

    def test_returns_journal_entry_with_posting_date(self):
        posting_date = datetime(2024, 3, 15)
        doc = self._make_doc(posting_date=posting_date)

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.posting_date == posting_date

    def test_returns_journal_entry_with_description(self):
        doc = self._make_doc(description="Monthly close")

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.description == "Monthly close"

    def test_returns_journal_entry_with_none_description(self):
        doc = self._make_doc(description=None)

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.description is None

    def test_returns_journal_entry_with_correct_line_count(self):
        doc = self._make_doc()

        entry = MongoJournalRepo._to_domain(doc)

        assert len(entry.lines) == 2

    def test_decodes_debit_amount_as_decimal(self):
        doc = self._make_doc(debit_amount="250.75", credit_amount="250.75")

        entry = MongoJournalRepo._to_domain(doc)

        debit_line = next(line for line in entry.lines if line.debit_amount > 0)
        assert debit_line.debit_amount == Decimal("250.75")

    def test_decodes_credit_amount_as_decimal(self):
        doc = self._make_doc(debit_amount="250.75", credit_amount="250.75")

        entry = MongoJournalRepo._to_domain(doc)

        credit_line = next(line for line in entry.lines if line.credit_amount > 0)
        assert credit_line.credit_amount == Decimal("250.75")

    def test_preserves_decimal_precision_on_decode(self):
        doc = self._make_doc(debit_amount="99.99", credit_amount="99.99")

        entry = MongoJournalRepo._to_domain(doc)

        debit_line = next(line for line in entry.lines if line.debit_amount > 0)
        assert debit_line.debit_amount == Decimal("99.99")

    def test_computes_total_debits_from_lines(self):
        doc = self._make_doc(debit_amount="150", credit_amount="150")

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.total_debits == Decimal("150")

    def test_computes_total_credits_from_lines(self):
        doc = self._make_doc(debit_amount="150", credit_amount="150")

        entry = MongoJournalRepo._to_domain(doc)

        assert entry.total_credits == Decimal("150")

    def test_returns_journal_entry_instance(self):
        doc = self._make_doc()

        entry = MongoJournalRepo._to_domain(doc)

        assert isinstance(entry, JournalEntry)

    def test_returns_journal_lines_as_journal_line_instances(self):
        doc = self._make_doc()

        entry = MongoJournalRepo._to_domain(doc)

        assert all(isinstance(line, JournalLine) for line in entry.lines)
