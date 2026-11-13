import hashlib

import pytest
from pydantic import SecretStr
from trutina.authentication import SessionTokenHasher, Sha256SessionTokenHasher


@pytest.mark.unit
class TestSha256SessionTokenHasher:
    def test_is_a_session_token_hasher(self):
        assert isinstance(Sha256SessionTokenHasher(), SessionTokenHasher)

    def test_matches_the_known_sha256_vector(self):
        digest = Sha256SessionTokenHasher().hash(SecretStr("abc"))

        assert digest == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_is_deterministic(self):
        hasher = Sha256SessionTokenHasher()

        assert hasher.hash(SecretStr("t")) == hasher.hash(SecretStr("t"))

    def test_different_tokens_hash_differently(self):
        hasher = Sha256SessionTokenHasher()

        assert hasher.hash(SecretStr("a")) != hasher.hash(SecretStr("b"))

    def test_hashes_the_utf8_encoding(self):
        token = "tökén"

        assert Sha256SessionTokenHasher().hash(SecretStr(token)) == (
            hashlib.sha256(token.encode("utf-8")).hexdigest()
        )

    def test_output_is_64_lowercase_hex_characters_and_hides_the_token(self):
        digest = Sha256SessionTokenHasher().hash(SecretStr("plain-token"))

        assert len(digest) == 64
        assert digest == digest.lower()
        assert "plain-token" not in digest
