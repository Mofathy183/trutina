import pytest
from trutina.core.posting.schemas.ledger_posting import LedgerPosting

from tests.factories import make_credit_posting, make_debit_posting


@pytest.fixture
def debit_posting() -> LedgerPosting:
    return make_debit_posting()


@pytest.fixture
def credit_posting() -> LedgerPosting:
    return make_credit_posting()
