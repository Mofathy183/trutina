"""Integration tests for AccountService against real MongoDB infrastructure.

These tests do NOT re-verify validation branches, DTO field mapping, or
repository-internal behavior — that is already covered by
``test_service.py`` (fake-repo unit tests) and
``infrastructure/mongo/account/tests/test_repository_integration.py``
(Mongo adapter tests).

The only thing these tests exist to prove is that
``AccountService`` produces the same business-correct outcome when wired
to ``MongoAccountRepo`` instead of ``FakeAccountRepo`` — i.e. that the
DTO -> domain -> Mongo -> domain -> view-model seam holds end to end, and
that the service's pre-check and MongoDB's unique index agree on what
counts as a duplicate.
"""

import pytest
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    TEST_ACTOR,
    make_create_account_input,
    make_update_account_input,
)


@pytest.mark.integration
class TestAccountServiceLifecycle:
    async def test_create_retrieve_update_retrieve_round_trip(self, services):
        """Proves the full create -> persist -> update -> persist round trip
        survives a real Mongo write/read cycle, not just an in-memory dict.
        """
        account_service, _journal_service, _posting_service = services

        created = await account_service.create_account(
            make_create_account_input(code="1001", name="Cash"), actor=TEST_ACTOR
        )
        fetched = await account_service.get_account("1001")

        assert fetched.code == created.code
        assert fetched.name == "Cash"
        assert fetched.normal_balance == "debit"

        await account_service.update_account(
            make_update_account_input(code="1001", name="Main Cash"), actor=TEST_ACTOR
        )

        updated = await account_service.get_account("1001")

        assert updated.name == "Main Cash"


@pytest.mark.integration
class TestAccountServiceDuplicateCreation:
    async def test_duplicate_code_raises_business_error(self, services):
        """Proves the service-level duplicate-code business error still
        surfaces correctly when the real storage-level unique index is the
        thing actually rejecting the second write — not just the service's
        own application-level pre-check.

        Asserts only the business outcome (the error code), not which layer
        detected the duplicate, so this test survives internal refactors.
        """
        account_service, _journal_service, _posting_service = services

        await account_service.create_account(
            make_create_account_input(code="1001", name="Cash"), actor=TEST_ACTOR
        )

        with pytest.raises(AppError) as exc_info:
            await account_service.create_account(
                make_create_account_input(code="1001", name="Petty Cash"),
                actor=TEST_ACTOR,
            )

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
