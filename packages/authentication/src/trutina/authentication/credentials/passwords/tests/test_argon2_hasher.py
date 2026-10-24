import asyncio
import logging
import threading

import pytest
from pydantic import SecretStr
from trutina.authentication import Argon2PasswordHasher

PW = SecretStr("correct horse battery staple")


def _hasher(
    *,
    time_cost: int = 1,
    memory_cost_kib: int = 8,
    parallelism: int = 1,
    max_concurrency: int = 2,
) -> Argon2PasswordHasher:
    # Cheapest parameters Argon2 accepts, so the suite stays fast.
    return Argon2PasswordHasher(
        time_cost=time_cost,
        memory_cost_kib=memory_cost_kib,
        parallelism=parallelism,
        max_concurrency=max_concurrency,
    )


@pytest.mark.unit
class TestArgon2PasswordHasher:
    async def test_hash_is_self_describing_argon2id_with_configured_parameters(self):
        hashed = await _hasher().hash(PW)

        assert hashed.startswith("$argon2id$")
        assert "m=8,t=1,p=1" in hashed

    async def test_hashes_the_same_password_differently_each_time(self):
        hasher = _hasher()

        assert await hasher.hash(PW) != await hasher.hash(PW)

    async def test_verifies_a_matching_password(self):
        hasher = _hasher()
        hashed = await hasher.hash(PW)

        assert await hasher.verify(PW, hashed) is True

    async def test_verifies_a_non_ascii_password(self):
        hasher = _hasher()
        password = SecretStr("pässwörd-密码-🔑")
        hashed = await hasher.hash(password)

        assert await hasher.verify(password, hashed) is True

    async def test_rejects_a_wrong_password(self):
        hasher = _hasher()
        hashed = await hasher.hash(PW)

        assert await hasher.verify(SecretStr("wrong"), hashed) is False

    @pytest.mark.parametrize(
        "malformed",
        ["", "garbage", "fake$password", "$argon2id$v=19$m=8,t=1,p=1$truncated"],
    )
    async def test_malformed_hash_verifies_false_and_needs_rehash(self, malformed):
        hasher = _hasher()

        assert await hasher.verify(PW, malformed) is False
        assert hasher.needs_rehash(malformed) is True

    async def test_fresh_hash_does_not_need_rehash(self):
        hasher = _hasher()

        assert hasher.needs_rehash(await hasher.hash(PW)) is False

    async def test_hash_made_under_other_parameters_needs_rehash(self):
        stale = await _hasher(time_cost=1).hash(PW)

        assert _hasher(time_cost=2).needs_rehash(stale) is True

    async def test_stale_hash_still_verifies(self):
        stale = await _hasher(time_cost=1).hash(PW)

        assert await _hasher(time_cost=2).verify(PW, stale) is True

    async def test_hash_runs_off_the_event_loop_thread(self, monkeypatch):
        hasher = _hasher()
        loop_thread = threading.current_thread()
        seen: list[threading.Thread] = []

        def fake_hash(secret: str) -> str:
            seen.append(threading.current_thread())
            return "fake"

        monkeypatch.setattr(hasher, "_hash_sync", fake_hash)

        await hasher.hash(PW)

        assert seen[0] is not loop_thread

    async def test_verify_runs_off_the_event_loop_thread(self, monkeypatch):
        hasher = _hasher()
        loop_thread = threading.current_thread()
        seen: list[threading.Thread] = []

        def fake_verify(secret: str, password_hash: str) -> bool:
            seen.append(threading.current_thread())
            return True

        monkeypatch.setattr(hasher, "_verify_sync", fake_verify)

        await hasher.verify(PW, "whatever")

        assert seen[0] is not loop_thread

    async def test_never_runs_more_hashes_at_once_than_the_limit(self, monkeypatch):
        limit = 2
        hasher = _hasher(max_concurrency=limit)
        lock = threading.Lock()
        entered = threading.Semaphore(0)
        gate = threading.Event()
        state = {"active": 0, "peak": 0, "started": 0}

        def fake_hash(secret: str) -> str:
            with lock:
                state["active"] += 1
                state["started"] += 1
                state["peak"] = max(state["peak"], state["active"])
            entered.release()
            gate.wait(timeout=5)
            with lock:
                state["active"] -= 1
            return "fake"

        monkeypatch.setattr(hasher, "_hash_sync", fake_hash)
        tasks = [asyncio.create_task(hasher.hash(PW)) for _ in range(6)]
        try:
            for _ in range(limit):
                assert await asyncio.to_thread(entered.acquire, True, 5)
            for _ in range(50):
                await asyncio.sleep(0)
            assert state["started"] == limit
        finally:
            gate.set()

        results = await asyncio.gather(*tasks)

        assert results == ["fake"] * 6
        assert state["peak"] <= limit

    def test_rejects_a_concurrency_limit_below_one(self):
        with pytest.raises(ValueError):
            _hasher(max_concurrency=0)

    async def test_event_loop_stays_free_while_a_hash_is_blocked(self, monkeypatch):
        hasher = _hasher()
        started = threading.Event()
        release = threading.Event()

        def fake_hash(secret: str) -> str:
            started.set()
            release.wait(timeout=5)
            return "fake"

        monkeypatch.setattr(hasher, "_hash_sync", fake_hash)
        task = asyncio.create_task(hasher.hash(PW))
        try:
            # This await can only return if the loop is free while the
            # hash worker is still blocked.
            assert await asyncio.to_thread(started.wait, 5)
        finally:
            release.set()

        assert await task == "fake"

    async def test_emits_no_logs_and_leaks_no_plaintext(self, caplog):
        hasher = _hasher()
        secret = SecretStr("s3cret-pw-value")

        with caplog.at_level(logging.DEBUG):
            hashed = await hasher.hash(secret)
            await hasher.verify(secret, hashed)
            await hasher.verify(SecretStr("other"), hashed)
            await hasher.verify(secret, "garbage")

        ours = [r for r in caplog.records if not r.name.startswith("asyncio")]
        assert ours == []
        assert "s3cret-pw-value" not in hashed
        assert "s3cret-pw-value" not in repr(hasher)
