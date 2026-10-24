"""Argon2id implementation of the password hashing contract.

Lives beside the ``PasswordHasher`` contract it implements. Needs only
``argon2-cffi`` and the standard library: no storage, no settings import.
The composition root maps ``AuthSettings`` onto the constructor.
"""

import asyncio

from argon2 import PasswordHasher as _Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import SecretStr

from .password import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id password hasher that runs off the event loop.

    Each hash or verify runs on a worker thread, and a semaphore bounds
    how many run at once, so a burst of logins cannot starve the loop or
    exhaust memory. Peak hashing memory is roughly
    ``max_concurrency * memory_cost_kib``.

    Hashes are self-describing (salt and parameters are embedded), so a
    hash made under older parameters still verifies; ``needs_rehash``
    reports when it should be recomputed.

    The semaphore is created at construction and binds to the first event
    loop that contends for it. Use one instance per event loop.

    Known limit: if a caller is cancelled while its hash is running, the
    worker thread finishes anyway but the slot is released immediately,
    so concurrency can briefly exceed the bound under cancellation.
    """

    def __init__(
        self,
        *,
        time_cost: int,
        memory_cost_kib: int,
        parallelism: int,
        max_concurrency: int,
    ) -> None:
        """Configure the hasher.

        Args:
            time_cost: Argon2id iterations.
            memory_cost_kib: Memory per hash, in KiB.
            parallelism: Lanes per hash.
            max_concurrency: Maximum hashes running at once.

        Raises:
            ValueError: If ``max_concurrency`` is below 1.
        """
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._argon2 = _Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
            type=Type.ID,
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def hash(self, password: SecretStr) -> str:
        secret = password.get_secret_value()
        async with self._semaphore:
            return await asyncio.to_thread(self._hash_sync, secret)

    async def verify(self, password: SecretStr, password_hash: str) -> bool:
        secret = password.get_secret_value()
        async with self._semaphore:
            return await asyncio.to_thread(self._verify_sync, secret, password_hash)

    def needs_rehash(self, password_hash: str) -> bool:
        """Report whether a stored hash differs from the current parameters.

        A malformed hash returns ``True``; it can never have verified, so
        the post-login rehash path cannot reach it.
        """
        try:
            return self._argon2.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True

    def _hash_sync(self, secret: str) -> str:
        return self._argon2.hash(secret)

    def _verify_sync(self, secret: str, password_hash: str) -> bool:
        try:
            return self._argon2.verify(password_hash, secret)
        except VerificationError, InvalidHashError:
            return False
