import uuid

import pytest

from quickassist.core.errors import Unauthorized
from quickassist.core.security import create_access_token, decode_access_token, hash_token
from quickassist.providers.ai.mock import MockAIProvider


def test_access_token_roundtrip() -> None:
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token, ttl = create_access_token(uid, sid)
    claims = decode_access_token(token)
    assert claims["sub"] == str(uid) and claims["sid"] == str(sid) and ttl > 0


def test_tampered_token_rejected() -> None:
    token, _ = create_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(Unauthorized):
        decode_access_token(token[:-2] + "xx")


def test_refresh_hash_is_stable_and_not_plaintext() -> None:
    assert hash_token("abc") == hash_token("abc") != "abc"


async def test_mock_embeddings_are_deterministic_and_normalized() -> None:
    p = MockAIProvider(dim=64)
    a = (await p.embed(["pgvector tìm kiếm"])).vectors[0]
    b = (await p.embed(["pgvector tìm kiếm"])).vectors[0]
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6
