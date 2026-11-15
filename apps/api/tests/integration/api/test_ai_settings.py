"""Integration P2/P3 — CRUD /me/ai-settings: key không lọt response, DB chỉ lưu ciphertext,
validate 400/422, quota reset theo billing mode, auth/config + local mode.

Cần PostgreSQL + pgvector (TEST_DATABASE_URL) — không có thì tự skip.
"""


import pytest
from sqlalchemy import text

from quickassist.data.database import get_sessionmaker
from tests.conftest import login

pytestmark = pytest.mark.integration

BYOK_BODY = {
    "mode": "byok", "provider": "openai", "base_url": "http://localhost:11434/v1",
    "chat_model": "llama3.1", "embedding_model": "nomic-embed-text", "timeout_seconds": 180,
}


async def _stored_key_enc(user_id: str) -> bytes | None:
    async with get_sessionmaker()() as s:
        return (await s.execute(
            text("SELECT api_key_enc FROM user_ai_settings WHERE user_id = :u"), {"u": user_id}
        )).scalar()


async def test_get_default_is_inherit(client) -> None:
    h = await login(client)
    r = await client.get("/me/ai-settings", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "inherit" and body["has_key"] is False
    assert body["server_default"]["provider"] == "mock"  # môi trường test
    assert "api_key" not in body  # contract: không có field key


async def test_put_byok_stores_ciphertext_only(client) -> None:
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": "sk-live-1234abcd"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "byok" and body["has_key"] is True
    assert body["key_hint"] == "…abcd" and body["timeout_seconds"] == 180
    assert "sk-live-1234abcd" not in r.text  # key không lọt response

    enc = await _stored_key_enc(uid)
    assert enc is not None and b"sk-live-1234abcd" not in enc  # DB chỉ có ciphertext

    # GET cũng không lộ key
    assert "sk-live-1234abcd" not in (await client.get("/me/ai-settings", headers=h)).text


async def test_put_null_keeps_key_empty_clears(client) -> None:
    h = await login(client)
    await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": "sk-keep-me"}, headers=h)
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": None}, headers=h)
    assert r.json()["has_key"] is True  # null = giữ key cũ
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": ""}, headers=h)
    assert r.json()["has_key"] is False  # "" = xoá key (model local)


async def test_put_invalid_rejected(client) -> None:
    h = await login(client)
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "base_url": "ftp://x"}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "AI_CONFIG_INVALID"
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "timeout_seconds": 3}, headers=h)
    assert r.status_code == 422  # schema chặn [5, 600]
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "chat_model": "x" * 101}, headers=h)
    assert r.status_code == 422
    r = await client.put("/me/ai-settings", json={"mode": "byok"}, headers=h)  # thiếu hết
    assert r.status_code == 400


async def test_put_embedding_dim_rejected_over_1536(client) -> None:
    # P5.S3: client biết số chiều native >1536 (từ /test) → server từ chối sớm.
    h = await login(client)
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "embedding_dim": 4096}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "AI_CONFIG_INVALID"
    assert "4096" in r.json()["error"]["message"]
    r = await client.put("/me/ai-settings", json={**BYOK_BODY, "embedding_dim": 768}, headers=h)
    assert r.status_code == 200  # ≤1536: chấp nhận (sẽ zero-pad khi embed)
    r = await client.put("/me/ai-settings", json=BYOK_BODY, headers=h)  # không gửi dim: vẫn lưu được
    assert r.status_code == 200


async def test_delete_back_to_inherit_and_key_gone(client) -> None:
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": "sk-doomed"}, headers=h)
    r = await client.delete("/me/ai-settings", headers=h)
    assert r.status_code == 200 and r.json()["mode"] == "inherit" and r.json()["has_key"] is False
    assert await _stored_key_enc(uid) is None  # key bị xoá khỏi DB


async def test_settings_scoped_per_user(client) -> None:
    ha, hb = await login(client, "a@s.vn"), await login(client, "b@s.vn")
    await client.put("/me/ai-settings", json={**BYOK_BODY, "api_key": "sk-a"}, headers=ha)
    r = await client.get("/me/ai-settings", headers=hb)
    assert r.json()["mode"] == "inherit" and r.json()["has_key"] is False  # b không thấy của a


# --- POST /me/ai-settings/test ---


async def test_endpoint_unreachable_provider_reports_embedding_stage(client) -> None:
    """Không có server nào nghe ở cổng 9 → lỗi kết nối, trả ok=false stage=embedding (nhanh, 0 retry)."""
    h = await login(client)
    r = await client.post("/me/ai-settings/test", json={
        "provider": "openai", "base_url": "http://127.0.0.1:9/v1",
        "chat_model": "m", "embedding_model": "e"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["stage"] == "embedding"
    assert body["code"] == "AI_PROVIDER_ERROR" and body["message"]
    assert body["chat"] is None and body["embedding"] is None


async def test_endpoint_invalid_config_400(client) -> None:
    h = await login(client)
    r = await client.post("/me/ai-settings/test", json={
        "provider": "openai", "base_url": "notaurl", "chat_model": "m",
        "embedding_model": "e"}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "AI_CONFIG_INVALID"


async def test_endpoint_rate_limited(client) -> None:
    h = await login(client)
    payload = {"provider": "openai", "base_url": "http://127.0.0.1:9/v1",
               "chat_model": "m", "embedding_model": "e"}
    codes = [(await client.post("/me/ai-settings/test", json=payload, headers=h)).status_code
             for _ in range(7)]  # giới hạn mặc định 6/phút
    assert codes[-1] == 429 and codes[0] == 200
