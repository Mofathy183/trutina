"""Password login use case.

Verifies an email and password against stored users and returns the
authenticated ``Identity``. Depends only on the user repository and
password hasher contracts, so it has no storage, web or CLI knowledge.
It does no throttling itself; ThrottledAuthenticator wraps it for that.
No token or route exists yet, and nothing outside tests uses it.
"""

import secrets

from pydantic import SecretStr
from trutina.authentication.credentials.passwords import (
    MAX_PASSWORD_LENGTH,
    PasswordHasher,
    normalize_password,
)
from trutina.authentication.credentials.users import (
    MAX_EMAIL_LENGTH,
    UserRepo,
    normalize_email,
)
from trutina.authentication.identity import Identity
from trutina.shared.errors import AppError, ErrorCode

from .authenticator import Authenticator


class PasswordAuthenticator(Authenticator):
    """Checks an email and password against stored users.

    Unknown email, wrong password, disabled account and over-limit input
    all raise the same ``AUTH_INVALID_CREDENTIALS`` error with an empty
    context, so a caller cannot tell which half of the credentials was
    wrong or whether an account exists. For a known or unknown email the
    password is always verified against some hash: the unknown-user path
    verifies against a dummy hash made with the hasher's current
    parameters, so it costs the same as a real verify. Verification runs
    before the disabled check for the same reason.

    The password is passed through ``normalize_password`` before hashing,
    exactly as registration does. The registration-only minimum length and
    email shape check are deliberately not applied, so a user whose
    credentials were accepted under an earlier rule can still sign in.

    A successful login of an active user whose hash uses outdated
    parameters stores a fresh hash. It does not throttle and does not use the client IP;
    ThrottledAuthenticator wraps it for that.
    """

    def __init__(
        self,
        *,
        users: UserRepo,
        hasher: PasswordHasher,
        dummy_hash: str,
    ) -> None:
        """Wire the authenticator to its collaborators.

        Prefer ``create``. Pass only a hash produced by ``hasher.hash`` at
        startup: a hardcoded literal stops costing the same as a real
        verify once the parameters change.

        Args:
            users: Where users are looked up and rehashed.
            hasher: Verifies and hashes passwords.
            dummy_hash: A hash nobody's password matches, verified against
                on the unknown-user path.
        """
        self._users = users
        self._hasher = hasher
        self._dummy_hash = dummy_hash

    @classmethod
    async def create(
        cls, *, users: UserRepo, hasher: PasswordHasher
    ) -> PasswordAuthenticator:
        """Build an authenticator, making its dummy hash once.

        Args:
            users: Where users are looked up and rehashed.
            hasher: Verifies and hashes passwords.

        Returns:
            An authenticator whose dummy hash uses the hasher's current
            parameters.
        """
        dummy_hash = await hasher.hash(SecretStr(secrets.token_urlsafe(32)))
        return cls(users=users, hasher=hasher, dummy_hash=dummy_hash)

    async def authenticate(
        self,
        *,
        email: str,
        password: SecretStr,
        client_ip: str | None,
    ) -> Identity:
        """Verify credentials.

        ``client_ip`` is accepted for the contract and not used here;
        `ThrottledAuthenticator` uses it.

        Args:
            email: The login email, as typed.
            password: The plaintext password, as typed.
            client_ip: Resolved client address, or ``None`` if unknown.

        Returns:
            The authenticated identity.

        Raises:
            AppError: AUTH_INVALID_CREDENTIALS for an unknown email, a
                wrong password, a disabled account, a blank password or
                input over ``MAX_EMAIL_LENGTH`` or ``MAX_PASSWORD_LENGTH``,
                always with an empty context. Over-limit and blank input
                is rejected before any lookup or hashing. Storage errors
                from the repository (STORAGE_UNAVAILABLE, STORAGE_TIMEOUT)
                and UNKNOWN_USER from a rehash write propagate unchanged.
        """
        raw = password.get_secret_value()
        if len(raw) > MAX_PASSWORD_LENGTH:
            raise _invalid_credentials()

        secret = normalize_password(raw)
        key = normalize_email(email)
        if not secret or len(secret) > MAX_PASSWORD_LENGTH:
            raise _invalid_credentials()
        if len(key) > MAX_EMAIL_LENGTH:
            raise _invalid_credentials()

        candidate = SecretStr(secret)
        user = await self._users.get_by_email(key)

        if user is None:
            await self._hasher.verify(candidate, self._dummy_hash)
            raise _invalid_credentials()

        matches = await self._hasher.verify(candidate, user.password_hash)
        if not matches or not user.is_active:
            raise _invalid_credentials()

        if self._hasher.needs_rehash(user.password_hash):
            await self._users.update_password_hash(
                user.id, await self._hasher.hash(candidate)
            )

        return Identity(subject_id=user.id)


def _invalid_credentials() -> AppError:
    """Build the single failure every bad login reports.

    The context stays empty: the CLI formatter lets a ``field`` key
    override its label, which would reveal which credential was wrong.
    """
    return AppError(code=ErrorCode.AUTH_INVALID_CREDENTIALS)
