from uuid import UUID

import pytest
from pydantic import SecretStr
from trutina.authentication import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    Identity,
    PasswordAuthenticator,
    normalize_password,
)
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_user
from tests.factories.secret import SECRET_SENTINEL
from tests.fakes import FakePasswordHasher, FakeUserRepo

PASSWORD = "correct horse 1"
IP = "203.0.113.7"


class _RecordingUserRepo(FakeUserRepo):
    """Records every lookup and password-hash update."""

    def __init__(self) -> None:
        super().__init__()
        self.lookups: list[str] = []
        self.hash_updates: list[tuple[UUID, str]] = []

    async def get_by_email(self, email: str):
        self.lookups.append(email)
        return await super().get_by_email(email)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.hash_updates.append((user_id, password_hash))
        await super().update_password_hash(user_id, password_hash)


async def _build() -> tuple[
    PasswordAuthenticator, _RecordingUserRepo, FakePasswordHasher
]:
    users = _RecordingUserRepo()
    hasher = FakePasswordHasher()
    authenticator = await PasswordAuthenticator.create(users=users, hasher=hasher)
    return authenticator, users, hasher


async def _login(
    authenticator: PasswordAuthenticator,
    *,
    email: str = "ann@example.com",
    password: str = PASSWORD,
) -> Identity:
    return await authenticator.authenticate(
        email=email, password=SecretStr(password), client_ip=IP
    )


async def _seed(users: FakeUserRepo, hasher: FakePasswordHasher, **overrides):
    password = overrides.pop("password", PASSWORD)
    user = make_user(password_hash=await hasher.hash(SecretStr(password)), **overrides)
    await users.create(user)
    return user


async def _failure(awaitable) -> AppError:
    with pytest.raises(AppError) as exc_info:
        await awaitable
    return exc_info.value


@pytest.mark.unit
class TestCreate:
    async def test_makes_the_dummy_hash_with_the_hasher_once(self):
        _, _, hasher = await _build()

        assert hasher.hash_calls == 1
        assert hasher.verify_calls == []

    async def test_makes_a_different_dummy_hash_each_time(self):
        hasher = FakePasswordHasher()
        users = FakeUserRepo()

        first = await PasswordAuthenticator.create(users=users, hasher=hasher)
        second = await PasswordAuthenticator.create(users=users, hasher=hasher)

        assert first._dummy_hash != second._dummy_hash


@pytest.mark.unit
class TestAuthenticate:
    async def test_returns_the_identity_of_the_matching_user(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)

        identity = await _login(authenticator)

        assert identity == Identity(subject_id=user.id)

    async def test_matches_the_email_ignoring_case_and_whitespace(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)

        identity = await _login(authenticator, email="  ANN@Example.COM ")

        assert identity.subject_id == user.id
        assert users.lookups == ["ann@example.com"]

    async def test_hashes_the_normalized_password_like_registration(self):
        authenticator, users, hasher = await _build()
        raw = "  Ｐass word 1  "
        user = await _seed(users, hasher, password=normalize_password(raw))

        identity = await _login(authenticator, password=raw)

        assert identity.subject_id == user.id

    async def test_does_not_rehash_a_current_hash(self):
        authenticator, users, hasher = await _build()
        await _seed(users, hasher)

        await _login(authenticator)

        assert users.hash_updates == []
        assert hasher.hash_calls == 2  # dummy hash and the seed, nothing more

    async def test_ignores_the_client_ip(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)

        identity = await authenticator.authenticate(
            email="ann@example.com", password=SecretStr(PASSWORD), client_ip=None
        )

        assert identity.subject_id == user.id


@pytest.mark.unit
class TestAuthenticateFailures:
    async def test_unknown_email_verifies_against_the_dummy_hash(self):
        authenticator, _, hasher = await _build()

        error = await _failure(_login(authenticator))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert hasher.verify_calls == [authenticator._dummy_hash]

    async def test_wrong_password_verifies_against_the_user_hash(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)

        error = await _failure(_login(authenticator, password="wrong password"))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert hasher.verify_calls == [user.password_hash]

    async def test_disabled_user_with_the_right_password_is_rejected_after_verifying(
        self,
    ):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher, is_active=False)

        error = await _failure(_login(authenticator))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert hasher.verify_calls == [user.password_hash]

    async def test_every_failure_cause_is_indistinguishable(self):
        authenticator, users, hasher = await _build()
        await _seed(users, hasher, email="active@example.com")
        await _seed(users, hasher, email="off@example.com", is_active=False)

        unknown = await _failure(_login(authenticator, email="nobody@example.com"))
        wrong = await _failure(
            _login(authenticator, email="active@example.com", password="wrong one 1")
        )
        disabled = await _failure(_login(authenticator, email="off@example.com"))
        oversized = await _failure(
            _login(authenticator, password="a" * (MAX_PASSWORD_LENGTH + 1))
        )

        errors = [unknown, wrong, disabled, oversized]
        assert {e.code for e in errors} == {ErrorCode.AUTH_INVALID_CREDENTIALS}
        assert all(dict(e.context) == {} for e in errors)
        assert len({repr(e) for e in errors}) == 1
        assert not any(isinstance(e.cause, BaseException) for e in errors)

    async def test_never_rehashes_after_a_failed_or_disabled_login(self):
        authenticator, users, hasher = await _build()
        stale = await _seed(users, hasher, email="stale@example.com")
        off = await _seed(users, hasher, email="off@example.com", is_active=False)
        hasher.stale_hashes.update({stale.password_hash, off.password_hash})

        await _failure(
            _login(authenticator, email="stale@example.com", password="bad bad 1")
        )
        await _failure(_login(authenticator, email="off@example.com"))

        assert users.hash_updates == []

    async def test_a_failure_never_echoes_the_password(self):
        authenticator, users, hasher = await _build()
        await _seed(users, hasher)

        error = await _failure(_login(authenticator, password=SECRET_SENTINEL))

        assert SECRET_SENTINEL not in repr(error)
        assert SECRET_SENTINEL not in str(error)


@pytest.mark.unit
class TestAuthenticateRejectsOverLimitInput:
    async def _assert_rejected_without_work(self, authenticator, users, hasher, **kw):
        before = hasher.hash_calls

        error = await _failure(_login(authenticator, **kw))

        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert users.lookups == []
        assert hasher.verify_calls == []
        assert hasher.hash_calls == before

    async def test_rejects_a_password_over_the_raw_limit(self):
        authenticator, users, hasher = await _build()

        await self._assert_rejected_without_work(
            authenticator, users, hasher, password="a" * (MAX_PASSWORD_LENGTH + 1)
        )

    async def test_rejects_a_password_that_grows_past_the_limit_when_normalized(self):
        authenticator, users, hasher = await _build()

        await self._assert_rejected_without_work(
            authenticator, users, hasher, password="\ufdfa" * 8
        )

    @pytest.mark.parametrize("blank", ["", "        ", "\t\n", "\u3000\u00a0"])
    async def test_rejects_a_blank_password(self, blank):
        authenticator, users, hasher = await _build()

        await self._assert_rejected_without_work(
            authenticator, users, hasher, password=blank
        )

    async def test_rejects_an_email_over_the_limit(self):
        authenticator, users, hasher = await _build()
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c") + 1) + "@b.c"

        await self._assert_rejected_without_work(
            authenticator, users, hasher, email=email
        )

    async def test_accepts_a_password_at_the_limit(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher, password="a" * MAX_PASSWORD_LENGTH)

        identity = await _login(authenticator, password="a" * MAX_PASSWORD_LENGTH)

        assert identity.subject_id == user.id

    async def test_accepts_an_email_at_the_limit(self):
        authenticator, users, hasher = await _build()
        email = "a" * (MAX_EMAIL_LENGTH - len("@b.c")) + "@b.c"
        user = await _seed(users, hasher, email=email)

        identity = await _login(authenticator, email=email)

        assert identity.subject_id == user.id


@pytest.mark.unit
class TestAuthenticateKeepsRegistrationOnlyRulesOut:
    async def test_does_not_apply_the_registration_minimum_password_length(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher, password="abc")

        identity = await _login(authenticator, password="abc")

        assert identity.subject_id == user.id

    async def test_does_not_apply_the_email_shape_check(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher, email="not-an-email")

        identity = await _login(authenticator, email="not-an-email")

        assert identity.subject_id == user.id


@pytest.mark.unit
class TestAuthenticateRehash:
    async def test_stores_a_fresh_hash_after_a_successful_login(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)
        hasher.stale_hashes.add(user.password_hash)
        hashes_before = hasher.hash_calls

        await _login(authenticator)

        assert hasher.hash_calls == hashes_before + 1
        assert users.hash_updates == [(user.id, f"fake${PASSWORD}")]

    async def test_rehashes_the_normalized_password(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher, password="Pass word 1")
        hasher.stale_hashes.add(user.password_hash)

        await _login(authenticator, password="  Ｐass word 1  ")

        assert users.hash_updates == [(user.id, "fake$Pass word 1")]

    async def test_passes_a_rehash_storage_error_on_unchanged(self):
        authenticator, users, hasher = await _build()
        user = await _seed(users, hasher)
        hasher.stale_hashes.add(user.password_hash)
        failure = AppError.storage_unavailable()

        async def boom(user_id: UUID, password_hash: str) -> None:
            raise failure

        users.update_password_hash = boom  # ty: ignore[invalid-assignment]

        error = await _failure(_login(authenticator))

        assert error is failure
