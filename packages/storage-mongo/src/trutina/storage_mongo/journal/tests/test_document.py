import pytest
from pymongo import IndexModel
from trutina.infrastructure.mongo.journal import (
    JournalDocument,
    JournalLineSubDocument,
)


@pytest.mark.unit
class TestJournalDocument:
    def test_uses_journal_entries_collection(self):
        assert JournalDocument.Settings.name == "journal_entries"

    def test_defines_unique_journal_number_index(self):
        indexes = JournalDocument.Settings.indexes

        index = next(
            i
            for i in indexes
            if isinstance(i, IndexModel) and i.document["name"] == "uq_journal_number"
        )

        assert index.document["key"] == {"journal_number": 1}
        assert index.document["unique"] is True

    def test_defines_posting_date_index(self):
        indexes = JournalDocument.Settings.indexes

        index = next(
            i
            for i in indexes
            if isinstance(i, IndexModel)
            and i.document["name"] == "idx_journal_posting_date"
        )

        assert index.document["key"] == {"posting_date": 1}
        assert index.document.get("unique") is not True

    def test_description_defaults_to_none(self, stub_journal_document_settings):
        doc = JournalDocument.model_construct(
            journal_number=1,
            posting_date=None,
            lines=[],
        )

        assert doc.description is None

    def test_does_not_include_total_debits_field(self, stub_journal_document_settings):
        doc = JournalDocument.model_construct(
            journal_number=1,
            posting_date=None,
            lines=[],
        )

        data = doc.model_dump()

        assert "total_debits" not in data

    def test_does_not_include_total_credits_field(self, stub_journal_document_settings):
        doc = JournalDocument.model_construct(
            journal_number=1,
            posting_date=None,
            lines=[],
        )

        data = doc.model_dump()

        assert "total_credits" not in data

    def test_does_not_include_is_balanced_field(self, stub_journal_document_settings):
        doc = JournalDocument.model_construct(
            journal_number=1,
            posting_date=None,
            lines=[],
        )

        data = doc.model_dump()

        assert "is_balanced" not in data


@pytest.mark.unit
class TestJournalLineSubDocument:
    def test_stores_account_as_string(self):
        line = JournalLineSubDocument(
            account="Cash",
            debit_amount="100.00",
            credit_amount="0",
        )

        assert line.account == "Cash"

    def test_stores_amounts_as_strings(self):
        line = JournalLineSubDocument(
            account="Cash",
            debit_amount="100.50",
            credit_amount="0",
        )

        assert isinstance(line.debit_amount, str)
        assert isinstance(line.credit_amount, str)
        assert line.debit_amount == "100.50"
        assert line.credit_amount == "0"
