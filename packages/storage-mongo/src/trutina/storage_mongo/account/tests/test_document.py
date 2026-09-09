import pytest
from pymongo import IndexModel
from trutina.core.account.schemas import AccountCategory
from trutina.infrastructure.mongo.account import AccountDocument


@pytest.mark.unit
class TestAccountDocument:
    def test_uses_accounts_collection(self):
        assert AccountDocument.Settings.name == "accounts"

    def test_defines_unique_code_index(self):
        indexes = AccountDocument.Settings.indexes

        code_index = next(
            index
            for index in indexes
            if isinstance(index, IndexModel)
            and index.document["name"] == "uq_account_code"
        )

        assert code_index.document["key"] == {"code": 1}
        assert code_index.document["unique"] is True

    def test_defines_unique_name_key_index(self):
        indexes = AccountDocument.Settings.indexes

        name_key_index = next(
            index
            for index in indexes
            if isinstance(index, IndexModel)
            and index.document["name"] == "uq_account_name_key"
        )

        assert name_key_index.document["key"] == {"name_key": 1}
        assert name_key_index.document["unique"] is True

    def test_keeps_category_as_enum_member(self):
        document = AccountDocument.model_construct(
            code="1000",
            name="Cash",
            name_key="cash",
            category=AccountCategory.ASSET,
        )

        assert isinstance(document.category, AccountCategory)
        assert document.category is AccountCategory.ASSET

    def test_does_not_include_normal_balance_field(self):
        document = AccountDocument.model_construct(
            code="1000",
            name="Cash",
            name_key="cash",
            category=AccountCategory.ASSET,
        )

        data = document.model_dump()

        assert "normal_balance" not in data
