from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.infrastructure.mongo.posting import MongoPostingRepo, PostingDocument
from trutina.infrastructure.mongo.shared import MongoExecutor

from tests.factories import make_credit_posting, make_debit_posting


@pytest.fixture
def stub_posting_document_settings(monkeypatch):
    """Let PostingDocument's constructor succeed without init_beanie().

    Mirrors ``stub_account_document_settings`` and
    ``stub_journal_document_settings``. ``Document.__init__``
    unconditionally calls ``self.get_pymongo_collection()``, which raises
    ``CollectionWasNotInitialized`` unless ``init_beanie()`` has
    registered the model. ``_to_document()`` never performs I/O, so a
    stub settings object is sufficient.
    """
    monkeypatch.setattr(
        PostingDocument,
        "get_settings",
        classmethod[Any, [], SimpleNamespace](
            lambda cls: SimpleNamespace(pymongo_collection=None)
        ),
    )


@pytest.mark.unit
class TestToDocument:
    def test_returns_document_with_account(self, stub_posting_document_settings):
        posting = make_debit_posting(account="Cash")

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.account == "Cash"

    def test_returns_document_with_computed_account_key(
        self, stub_posting_document_settings
    ):
        posting = make_debit_posting(account="Cash")

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.account_key == "cash"

    def test_encodes_debit_amount_as_string(self, stub_posting_document_settings):
        posting = make_debit_posting(amount=Decimal("100"))

        doc = MongoPostingRepo._to_document(posting, 0)

        assert isinstance(doc.debit_amount, str)
        assert doc.debit_amount == "100"

    def test_encodes_zero_credit_amount_as_string_zero_for_debit_posting(
        self, stub_posting_document_settings
    ):
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.credit_amount == "0"

    def test_encodes_credit_amount_as_string(self, stub_posting_document_settings):
        posting = make_credit_posting(amount=Decimal("250.75"))

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.credit_amount == "250.75"

    def test_encodes_zero_debit_amount_as_string_zero_for_credit_posting(
        self, stub_posting_document_settings
    ):
        posting = make_credit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.debit_amount == "0"

    def test_returns_document_with_journal_number(self, stub_posting_document_settings):
        posting = make_debit_posting(journal_number=7)

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.journal_number == 7

    def test_returns_document_with_posting_date(self, stub_posting_document_settings):
        posting_date = datetime(2024, 6, 15)
        posting = make_debit_posting(posting_date=posting_date)

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.posting_date == posting_date

    def test_returns_document_with_supplied_line_index(
        self, stub_posting_document_settings
    ):
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 3)

        assert doc.line_index == 3

    def test_sets_updated_at_to_a_recent_timestamp(
        self, stub_posting_document_settings
    ):
        before = datetime.now(UTC)
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        after = datetime.now(UTC)
        assert doc.updated_at is not None
        assert before <= doc.updated_at <= after

    def test_sets_created_at_to_a_recent_timestamp(
        self, stub_posting_document_settings
    ):
        before = datetime.now(UTC)
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        after = datetime.now(UTC)
        assert doc.created_at is not None
        assert before <= doc.created_at <= after

    def test_created_at_equals_updated_at(self, stub_posting_document_settings):
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.created_at == doc.updated_at

    def test_returns_posting_document_instance(self, stub_posting_document_settings):
        posting = make_debit_posting()

        doc = MongoPostingRepo._to_document(posting, 0)

        assert isinstance(doc, PostingDocument)

    def test_preserves_decimal_precision_in_encoding(
        self, stub_posting_document_settings
    ):
        posting = make_debit_posting(amount=Decimal("99.9999"))

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.debit_amount == "99.9999"

    def test_computes_account_key_as_unicode_casefold(
        self, stub_posting_document_settings
    ):
        posting = make_debit_posting(account="Accounts Receivable")

        doc = MongoPostingRepo._to_document(posting, 0)

        assert doc.account_key == "accounts receivable"


@pytest.mark.unit
class TestToDomain:
    def _make_doc(
        self,
        *,
        account: str = "Cash",
        debit_amount: str = "100",
        credit_amount: str = "0",
        journal_number: int = 1,
        posting_date: datetime | None = None,
        line_index: int = 0,
    ) -> PostingDocument:
        if posting_date is None:
            posting_date = datetime(2025, 1, 1)

        return PostingDocument.model_construct(
            account=account,
            account_key=account.casefold(),
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            journal_number=journal_number,
            posting_date=posting_date,
            line_index=line_index,
        )

    def test_returns_posting_with_document_account(self):
        doc = self._make_doc(account="Cash")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.account == "Cash"

    def test_decodes_debit_amount_as_decimal(self):
        doc = self._make_doc(debit_amount="250.75", credit_amount="0")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.debit_amount == Decimal("250.75")

    def test_decodes_credit_amount_as_decimal(self):
        doc = self._make_doc(debit_amount="0", credit_amount="100.00")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.credit_amount == Decimal("100.00")

    def test_returns_posting_with_document_journal_number(self):
        doc = self._make_doc(journal_number=5)

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.journal_number == 5

    def test_returns_posting_with_document_posting_date(self):
        posting_date = datetime(2024, 3, 10)
        doc = self._make_doc(posting_date=posting_date)

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.posting_date == posting_date

    def test_is_debit_is_true_for_debit_posting(self):
        doc = self._make_doc(debit_amount="100", credit_amount="0")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.is_debit is True

    def test_is_debit_is_false_for_credit_posting(self):
        doc = self._make_doc(debit_amount="0", credit_amount="100")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.is_debit is False

    def test_returns_ledger_posting_instance(self):
        doc = self._make_doc()

        posting = MongoPostingRepo._to_domain(doc)

        assert isinstance(posting, LedgerPosting)

    def test_does_not_carry_line_index_onto_domain_object(self):
        doc = self._make_doc(line_index=4)

        posting = MongoPostingRepo._to_domain(doc)

        assert not hasattr(posting, "line_index")

    def test_preserves_decimal_precision_on_decode(self):
        doc = self._make_doc(debit_amount="99.9999", credit_amount="0")

        posting = MongoPostingRepo._to_domain(doc)

        assert posting.debit_amount == Decimal("99.9999")


@pytest.mark.unit
class TestMongoPostingRepoConstruction:
    def test_stores_executor(self):
        executor = MongoExecutor()

        repo = MongoPostingRepo(executor)

        assert repo._executor is executor

    async def test_save_many_with_empty_list_is_a_no_op(self):
        repo = MongoPostingRepo(MongoExecutor())

        result = await repo.save_many([])

        assert result is None
