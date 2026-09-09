from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError
from trutina.core.account.schemas.account import Account, AccountCategory
from trutina.infrastructure.mongo.account import AccountDocument, MongoAccountRepo
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.errors import ErrorCode
from trutina.shared.rule import account_lookup_key

from tests.factories import make_account


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
    def test_returns_duplicate_account_code_when_code_constraint_is_violated(self):
        repo = MongoAccountRepo(MongoExecutor())
        account = make_account(code="1001")
        exc = _make_duplicate_key_error({"code": 1})

        result = repo._on_duplicate(exc, account)

        assert result.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
        assert result.context["field"] == "code"
        assert result.context["value"] == "1001"
        assert result.context["resource"] == "account"

    def test_returns_duplicate_account_name_when_name_key_constraint_is_violated(self):
        repo = MongoAccountRepo(MongoExecutor())
        account = make_account(name="Cash")
        exc = _make_duplicate_key_error({"name_key": 1})

        result = repo._on_duplicate(exc, account)

        assert result.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert result.context["field"] == "name"
        assert result.context["value"] == "Cash"
        assert result.context["resource"] == "account"

    def test_returns_unknown_error_when_key_pattern_is_unrecognized(self):
        repo = MongoAccountRepo(MongoExecutor())
        account = make_account()
        exc = _make_duplicate_key_error({"some_other_field": 1})

        result = repo._on_duplicate(exc, account)

        assert result.code == ErrorCode.UNKNOWN_ERROR
        assert result.cause is exc

    def test_returns_unknown_error_when_key_pattern_is_empty(self):
        repo = MongoAccountRepo(MongoExecutor())
        account = make_account()
        exc = _make_duplicate_key_error({})

        result = repo._on_duplicate(exc, account)

        assert result.code == ErrorCode.UNKNOWN_ERROR

    def test_returns_unknown_error_when_duplicate_key_error_has_no_details(self):
        repo = MongoAccountRepo(MongoExecutor())
        account = make_account()
        exc = DuplicateKeyError("E11000")

        result = repo._on_duplicate(exc, account)

        assert result.code == ErrorCode.UNKNOWN_ERROR


@pytest.mark.unit
class TestToDocument:
    def test_returns_document_with_account_code(self, stub_account_document_settings):
        account = make_account(code="1001")

        doc = MongoAccountRepo._to_document(account)

        assert doc.code == "1001"

    def test_returns_document_with_account_name(self, stub_account_document_settings):
        account = make_account(name="Cash")

        doc = MongoAccountRepo._to_document(account)

        assert doc.name == "Cash"

    def test_returns_document_with_computed_name_key(
        self, stub_account_document_settings
    ):
        account = make_account(name="Cash")

        doc = MongoAccountRepo._to_document(account)

        assert doc.name_key == account_lookup_key("Cash")
        assert doc.name_key == "cash"

    def test_returns_document_with_account_category(
        self, stub_account_document_settings
    ):
        account = make_account(category=AccountCategory.REVENUE)

        doc = MongoAccountRepo._to_document(account)

        assert doc.category == AccountCategory.REVENUE

    def test_sets_updated_at_to_a_recent_timestamp(
        self, stub_account_document_settings
    ):
        before = datetime.now(UTC)
        account = make_account()

        doc = MongoAccountRepo._to_document(account)

        after = datetime.now(UTC)
        assert doc.updated_at is not None
        assert before <= doc.updated_at <= after

    def test_does_not_set_created_at(self, stub_account_document_settings):
        account = make_account()

        doc = MongoAccountRepo._to_document(account)

        assert doc.created_at is None

    def test_returns_account_document_instance(self, stub_account_document_settings):
        account = make_account()

        doc = MongoAccountRepo._to_document(account)

        assert isinstance(doc, AccountDocument)


@pytest.mark.unit
class TestToDomain:
    def _make_doc(
        self,
        code: str = "1001",
        name: str = "Cash",
        category: AccountCategory = AccountCategory.ASSET,
    ) -> AccountDocument:
        return AccountDocument.model_construct(
            code=code,
            name=name,
            name_key=account_lookup_key(name),
            category=category,
        )

    def test_returns_account_with_document_code(self):
        doc = self._make_doc(code="2001")

        account = MongoAccountRepo._to_domain(doc)

        assert account.code == "2001"

    def test_returns_account_with_document_name(self):
        doc = self._make_doc(name="Cash")

        account = MongoAccountRepo._to_domain(doc)

        assert account.name == "Cash"

    def test_returns_account_with_document_category(self):
        doc = self._make_doc(category=AccountCategory.LIABILITY)

        account = MongoAccountRepo._to_domain(doc)

        assert account.category is AccountCategory.LIABILITY

    def test_returns_account_with_debit_normal_balance_for_asset_category(self):
        doc = self._make_doc(category=AccountCategory.ASSET)

        account = MongoAccountRepo._to_domain(doc)

        assert account.normal_balance == "debit"

    def test_returns_account_with_credit_normal_balance_for_revenue_category(self):
        doc = self._make_doc(category=AccountCategory.REVENUE)

        account = MongoAccountRepo._to_domain(doc)

        assert account.normal_balance == "credit"

    def test_returns_account_instance(self):
        doc = self._make_doc()

        account = MongoAccountRepo._to_domain(doc)

        assert isinstance(account, Account)

    def test_returns_account_with_normalized_name(self):
        doc = self._make_doc(name="  Cash  ")

        account = MongoAccountRepo._to_domain(doc)

        assert account.name == "Cash"

    @pytest.mark.parametrize("category", list(AccountCategory))
    def test_returns_account_with_same_category_when_category_is_round_tripped(
        self,
        category: AccountCategory,
    ):
        doc = self._make_doc(category=category)

        account = MongoAccountRepo._to_domain(doc)

        assert account.category is category

    def test_raises_validation_error_when_document_contains_invalid_name(self):
        doc = AccountDocument.model_construct(
            code="1001",
            name="!!!",
            name_key="!!!",
            category=AccountCategory.ASSET,
        )

        with pytest.raises(ValidationError):
            MongoAccountRepo._to_domain(doc)
