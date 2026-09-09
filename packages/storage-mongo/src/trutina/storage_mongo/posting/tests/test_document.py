from datetime import datetime

import pytest
from pymongo import IndexModel
from trutina.infrastructure.mongo.posting import PostingDocument


@pytest.mark.unit
class TestPostingDocument:
    def test_uses_postings_collection(self):
        assert PostingDocument.Settings.name == "postings"

    def test_defines_account_key_posting_date_index(self):
        indexes = PostingDocument.Settings.indexes

        index = next(
            i
            for i in indexes
            if isinstance(i, IndexModel)
            and i.document["name"] == "idx_posting_account_key_date"
        )

        assert index.document["key"] == {"account_key": 1, "posting_date": 1}
        assert index.document.get("unique") is not True

    def test_defines_journal_number_index(self):
        indexes = PostingDocument.Settings.indexes

        index = next(
            i
            for i in indexes
            if isinstance(i, IndexModel)
            and i.document["name"] == "idx_posting_journal_number"
        )

        assert index.document["key"] == {"journal_number": 1}
        assert index.document.get("unique") is not True

    def test_defines_no_unique_indexes(self):
        indexes = PostingDocument.Settings.indexes

        assert all(index.document.get("unique") is not True for index in indexes)

    def test_does_not_include_is_debit_field(self):
        doc = PostingDocument.model_construct(
            account="Cash",
            account_key="cash",
            debit_amount="100",
            credit_amount="0",
            journal_number=1,
            posting_date=datetime(2025, 1, 1),
            line_index=0,
        )

        data = doc.model_dump()

        assert "is_debit" not in data

    def test_does_not_include_description_field(self):
        doc = PostingDocument.model_construct(
            account="Cash",
            account_key="cash",
            debit_amount="100",
            credit_amount="0",
            journal_number=1,
            posting_date=datetime(2025, 1, 1),
            line_index=0,
        )

        data = doc.model_dump()

        assert "description" not in data

    def test_created_at_defaults_to_none(self):
        doc = PostingDocument.model_construct(
            account="Cash",
            account_key="cash",
            debit_amount="100",
            credit_amount="0",
            journal_number=1,
            posting_date=datetime(2025, 1, 1),
            line_index=0,
        )

        assert doc.created_at is None

    def test_updated_at_defaults_to_none(self):
        doc = PostingDocument.model_construct(
            account="Cash",
            account_key="cash",
            debit_amount="100",
            credit_amount="0",
            journal_number=1,
            posting_date=datetime(2025, 1, 1),
            line_index=0,
        )

        assert doc.updated_at is None
