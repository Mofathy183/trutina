"""Test fixtures for MongoDB infrastructure integration tests.

Session-scoped fixtures (mongo_connection, beanie_init) are created once
per test session and shared across all integration tests.

clean_db is function-scoped. It truncates all collections before each
test using delete_many({}) so that indexes are preserved across the
session. Indexes must be preserved because beanie_init is session-scoped
and will not re-create them after a drop.

The ``counters`` collection used by ``MongoJournalRepo.next_journal_number()``
is not a Beanie-registered document collection and does not exist until the
first counter call. Once created, it appears in ``list_collection_names()``
and is truncated by ``clean_db`` along with all other collections, so counter
tests always start from a predictable state.

Session teardown (inside mongo_connection) drops all collections once
after the final test so the database is empty when pytest exits.
Dropping at teardown is safe because no further tests will run.
"""

import pytest_asyncio
from beanie import init_beanie
from trutina.config import TestSettings
from trutina.storage_mongo import connect, disconnect
from trutina.storage_mongo.account import AccountDocument
from trutina.storage_mongo.journal import JournalDocument
from trutina.storage_mongo.posting import PostingDocument

# ---------------------------------------------------------------------------
# All Beanie document models registered in this session.
# Add new document classes here as concrete repository adapters are built.
# ---------------------------------------------------------------------------
DOCUMENT_MODELS = [
    AccountDocument,
    JournalDocument,
    PostingDocument,
]


@pytest_asyncio.fixture(scope="session")
async def mongo_connection(test_settings: TestSettings):
    """Open a verified MongoDB connection for the entire test session.

    Teardown drops all collections so the database is empty after pytest
    exits. Dropping at session end is safe — indexes will be re-created by
    beanie_init on the next session start.
    """
    connection = await connect(test_settings.mongo)

    yield connection

    # Session teardown — runs once after the last test.
    # Drop rather than truncate: at session end indexes are no longer
    # needed, so dropping is cleaner than leaving empty collections.
    db = connection.db
    for name in await db.list_collection_names():
        await db[name].drop()

    await disconnect(connection)


@pytest_asyncio.fixture(scope="session")
async def beanie_init(mongo_connection):
    """Initialize Beanie document models exactly once per test session.

    init_beanie() registers document classes globally and creates indexes
    via createIndexes, which is idempotent for existing definitions.
    Session scope ensures this runs only once regardless of how many
    integration tests are collected.
    """
    await init_beanie(
        database=mongo_connection.db,
        document_models=DOCUMENT_MODELS,
    )
    yield


@pytest_asyncio.fixture
async def clean_db(beanie_init, mongo_connection):
    """Truncate all collections before each test, preserving indexes.

    Runs before the test body. Uses delete_many({}) rather than
    drop_collection() so that the session-scoped indexes created by
    beanie_init are preserved for the rest of the session.

    Yields the raw AsyncDatabase so tests that need raw BSON inspection
    can access collections directly:

        raw = await clean_db["accounts"].find_one({"code": "1001"})
        raw = await clean_db["journal_entries"].find_one({"journal_number": 1})
        raw = await clean_db["postings"].find_one({"journal_number": 1})
    """
    db = mongo_connection.db
    for name in await db.list_collection_names():
        await db[name].delete_many({})
    yield db
