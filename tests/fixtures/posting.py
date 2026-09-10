from types import SimpleNamespace
from typing import Any

import pytest
from trutina.core.posting.repo import PostingRepo
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.storage_mongo.posting import MongoPostingRepo, PostingDocument
from trutina.storage_mongo.shared import MongoExecutor

from tests.factories import make_credit_posting, make_debit_posting


@pytest.fixture
def debit_posting() -> LedgerPosting:
    return make_debit_posting()


@pytest.fixture
def credit_posting() -> LedgerPosting:
    return make_credit_posting()


@pytest.fixture
def mongo_posting_repo(clean_db) -> PostingRepo:
    """A MongoPostingRepo instance backed by the clean test database.

    Declares ``clean_db`` as a dependency to guarantee:
    1. Beanie is initialized (``clean_db`` depends on ``beanie_init``).
    2. The database is empty before the test runs.

    Returns the abstract ``PostingRepo`` type so integration tests are
    written against the contract rather than the implementation, mirroring
    ``mongo_account_repo`` and ``mongo_journal_repo``.
    """
    return MongoPostingRepo(MongoExecutor())


@pytest.fixture
def stub_posting_document_settings(monkeypatch):
    """Let PostingDocument's constructor succeed without init_beanie().

    Mirrors ``stub_account_document_settings`` and
    ``stub_journal_document_settings``. ``Document.__init__``
    unconditionally calls ``self.get_pymongo_collection()``, which raises
    ``CollectionWasNotInitialized`` unless ``init_beanie()`` has
    registered the model. ``MongoPostingRepo._to_document()`` never
    performs I/O, so a stub settings object is sufficient.
    """
    monkeypatch.setattr(
        PostingDocument,
        "get_settings",
        classmethod[Any, [], SimpleNamespace](
            lambda cls: SimpleNamespace(pymongo_collection=None)
        ),
    )
