import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import trutina.authentication as authentication
from trutina.authentication import (
    AccessState,
    ClientKind,
    SessionRecord,
    SessionRepo,
    SessionTokenHasher,
    ValidSession,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _record(token_hash: str = "h1") -> SessionRecord:
    return SessionRecord(
        token_hash=token_hash,
        user_id=uuid4(),
        client_kind=ClientKind.API,
        created_at=NOW,
        last_used_at=NOW,
        authenticated_at=NOW,
        idle_expires_at=NOW + timedelta(days=1),
        absolute_expires_at=NOW + timedelta(days=7),
    )


@pytest.mark.unit
class TestClientKind:
    def test_has_exactly_the_api_and_cli_kinds(self):
        assert {kind.value for kind in ClientKind} == {"api", "cli"}


@pytest.mark.unit
class TestSessionRecord:
    def test_is_frozen(self):
        record = _record()

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.revoked_at = NOW  # ty: ignore[invalid-assignment]

    def test_repr_hides_the_token_hash(self):
        assert "secret-hash" not in repr(_record("secret-hash"))

    def test_is_not_revoked_by_default(self):
        assert _record().revoked_at is None


@pytest.mark.unit
class TestValidSession:
    def test_is_frozen(self):
        valid = ValidSession(session=_record(), access=AccessState(is_active=True))

        with pytest.raises(dataclasses.FrozenInstanceError):
            valid.access = AccessState(is_active=False)  # ty: ignore[invalid-assignment]


@pytest.mark.unit
class TestContractSurface:
    def test_session_repo_declares_exactly_the_frozen_methods(self):
        assert SessionRepo.__abstractmethods__ == frozenset(
            {
                "create",
                "get_valid",
                "touch",
                "mark_reauthenticated",
                "revoke",
                "revoke_all_for_user",
                "purge_before",
            }
        )

    def test_session_token_hasher_declares_only_hash(self):
        assert SessionTokenHasher.__abstractmethods__ == frozenset({"hash"})

    @pytest.mark.parametrize(
        "name",
        [
            "TokenIssuer",
            "TokenVerifier",
            "AccessToken",
            "RefreshTokenHasher",
            "RefreshTokenRecord",
            "RefreshTokenRepo",
            "RotationOutcome",
            "RotationResult",
        ],
    )
    def test_removed_token_contracts_are_not_exported(self, name):
        assert not hasattr(authentication, name)
