"""Integration P3 — rebuild orchestration khi đổi cấu hình embedding (ADR-0016 §4.6).

Quyết định 14/11: KHÔNG xoá chunk hàng loạt (nhánh từ khoá hybrid cũng đọc note_chunks) —
chunk cũ được thay dần theo note khi job tới lượt; search không bị gián đoạn.

Cần PostgreSQL + pgvector (TEST_DATABASE_URL) — không có thì tự skip.
"""

import uuid

import pytest
from sqlalchemy import text

from quickassist.business.ai_settings import embedding_fingerprint
from quickassist.data.database import get_sessionmaker
from quickassist.infrastructure.jobs import drain
from tests.conftest import login

pytestmark = pytest.mark.integration

BYOK = {"mode": "byok", "provider": "openai", "base_url": "http://127.0.0.1:9/v1",
        "chat_model": "llama3.1", "embedding_model": "nomic-embed-text", "timeout_seconds": 180}
FP_BYOK = embedding_fingerprint("openai", "http://127.0.0.1:9/v1", "nomic-embed-text")


async def _jobs(client_headers_user: str) -> list[dict]:  # type: ignore[type-arg]
    async with get_sessionmaker()() as s:
        rows = await s.execute(text(
            "SELECT kind, payload, status, dedupe_key FROM jobs WHERE kind = 'semantic_search.index_note'"
        ))
        return [dict(r._mapping) for r in rows]


async def _chunk_count(user_id: str) -> int:
    async with get_sessionmaker()() as s:
        return (await s.execute(text(
            "SELECT count(*) FROM note_chunks WHERE user_id = :u"), {"u": user_id})).scalar_one()


async def _note_status(note_id: str) -> str:
    async with get_sessionmaker()() as s:
        return (await s.execute(text(
            "SELECT index_status FROM notes WHERE id = :i"), {"i": note_id})).scalar_one()


async def _create_note(client, headers: dict[str, str], content: str) -> str:
    r = await client.post("/notes", json={"content": content}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_full_rebuild_flow(client) -> None:
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    note_id = await _create_note(client, h, "Ghi chú về phở Hà Nội. " * 20)
    await drain()
    assert await _note_status(note_id) == "READY"
    assert await _chunk_count(uid) > 0

    # --- lưu BYOK (provider trỏ nơi không có server) → fingerprint đổi → rebuild ---
    r = await client.put("/me/ai-settings", json=BYOK, headers=h)
    assert r.status_code == 200, r.text
    rebuild = r.json()["rebuild"]
    assert rebuild == {"required": True, "notes": 1}
    assert await _note_status(note_id) == "PROCESSING"  # mark ngay
    byok_jobs = [j for j in await _jobs(h)
                 if j["payload"].get("embedding_fingerprint") == FP_BYOK]
    assert len(byok_jobs) == 1
    assert byok_jobs[0]["dedupe_key"] == f"semantic_search.index_note:{note_id}:{FP_BYOK[:12]}"
    assert await _chunk_count(uid) > 0  # chunk cũ CÒN NGUYÊN (không xoá hàng loạt)

    # search trong lúc rebuild vẫn trả kết quả (BYOK trỏ nơi chết → xoá hết sẽ fail 502 ở embed;
    # đã DELETE về inherit trước khi search — xem dưới)
    r = await client.delete("/me/ai-settings", headers=h)
    rebuild = r.json()["rebuild"]
    assert rebuild == {"required": True, "notes": 1}  # byok → inherit: fingerprint server khác
    r = await client.post("/search", json={"query": "phở Hà Nội"}, headers=h)
    assert r.status_code == 200 and len(r.json()["items"]) > 0  # chunk cũ vẫn phục vụ search

    # --- drain: job byok (fingerprint lệch) bị guard BỎ; job fingerprint server re-index ---
    await drain()
    assert await _note_status(note_id) == "READY"
    assert await _chunk_count(uid) > 0
    rebuild_jobs = [j for j in await _jobs(h) if j["payload"].get("embedding_fingerprint")]
    assert len(rebuild_jobs) == 2
    assert all(j["status"] == "DONE" for j in rebuild_jobs)  # guard bỏ job stale (không DEAD)
    assert {j["payload"]["embedding_fingerprint"] for j in rebuild_jobs} == {
        FP_BYOK, embedding_fingerprint("mock", "mock://server", "mock-embed")}


async def test_same_config_twice_no_rebuild(client) -> None:
    h = await login(client)
    r1 = await client.put("/me/ai-settings", json=BYOK, headers=h)
    assert r1.json()["rebuild"] == {"required": True, "notes": 0}  # chưa có note nào
    r2 = await client.put("/me/ai-settings", json=BYOK, headers=h)
    assert r2.json()["rebuild"] is None  # fingerprint không đổi → không rebuild


async def test_key_only_change_no_rebuild(client) -> None:
    """Nghiệm thu #6: đổi RIÊNG key → không rebuild."""
    h = await login(client)
    await client.put("/me/ai-settings", json={**BYOK, "api_key": "sk-1"}, headers=h)
    r = await client.put("/me/ai-settings", json={**BYOK, "api_key": "sk-2"}, headers=h)
    assert r.json()["rebuild"] is None


async def test_get_reports_rebuild_note_count(client) -> None:
    h = await login(client)
    await _create_note(client, h, "note một " * 10)
    await _create_note(client, h, "note hai " * 10)
    r = await client.get("/me/ai-settings", headers=h)
    assert r.json()["rebuild_note_count"] == 2


async def test_stale_fingerprint_job_writes_nothing(client) -> None:
    """Guard: job với fingerprint KHÔNG còn hiện hành → bỏ, không ghi chunk mới/sai model."""
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    note_id = await _create_note(client, h, "Nội dung ổn định. " * 20)
    await drain()
    before = await _chunk_count(uid)

    from quickassist.data.database import get_sessionmaker as mk
    from quickassist.infrastructure.jobs import SEMANTIC_SEARCH_INDEX_NOTE, enqueue
    async with mk()() as s:
        await enqueue(s, SEMANTIC_SEARCH_INDEX_NOTE,
                      {"note_id": note_id, "embedding_fingerprint": "stale" + "0" * 59},
                      dedupe_key=None)
        await s.commit()
    await drain()
    assert await _chunk_count(uid) == before  # không ghi thêm/không xoá
    assert await _note_status(note_id) == "READY"  # note vẫn ổn (job thường trước đó đã READY)


async def test_enqueue_many_dedupes(client) -> None:
    """enqueue_many: trùng dedupe_key còn QUEUED → chỉ 1 job (lô 500 không nhân đôi)."""
    from quickassist.data.database import get_sessionmaker as mk
    from quickassist.infrastructure.jobs import SEMANTIC_SEARCH_INDEX_NOTE, enqueue_many

    async with mk()() as s:
        await enqueue_many(
            s, SEMANTIC_SEARCH_INDEX_NOTE,
            [{"note_id": "11111111-1111-1111-1111-111111111111", "embedding_fingerprint": "f" * 64},
             {"note_id": "11111111-1111-1111-1111-111111111111", "embedding_fingerprint": "f" * 64}],
            dedupe_keys=["k1", "k1"])
        await s.commit()
    rows = await _jobs("")
    assert len(rows) == 1
    uuid.UUID(rows[0]["payload"]["note_id"])  # payload hợp lệ
