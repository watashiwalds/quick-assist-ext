"""Integration P5.S5 — repair save→rebuild bị đứt (applied_fingerprint, ADR-0016 §4.6).

Crash giữa commit #1 (save config) và commit #2 (mark + enqueue) → config mới, chunk cũ.
`applied_fingerprint` lệch `embedding_fingerprint` → worker repair enqueue lại; guard trong
start_rebuild không cho save cũ đè save mới.

Cần PostgreSQL + pgvector (TEST_DATABASE_URL) — không có thì tự skip.
"""

import uuid

import pytest
from sqlalchemy import text

from quickassist.business.ai_settings import AISettingsInput, AISettingsService, embedding_fingerprint
from quickassist.business.semantic_search import start_rebuild
from quickassist.business.semantic_search.rebuild import repair_pending_rebuilds
from quickassist.data.database import get_sessionmaker
from quickassist.infrastructure.jobs import drain
from tests.conftest import login

pytestmark = pytest.mark.integration

BYOK = {"mode": "byok", "provider": "openai", "base_url": "http://127.0.0.1:9/v1",
        "chat_model": "llama3.1", "embedding_model": "nomic-embed-text", "timeout_seconds": 180}
FP_BYOK = embedding_fingerprint("openai", "http://127.0.0.1:9/v1", "nomic-embed-text")
FP_SERVER = embedding_fingerprint("mock", "mock://server", "mock-embed")


async def _row(user_id: str) -> dict:  # type: ignore[type-arg]
    async with get_sessionmaker()() as s:
        r = await s.execute(text(
            "SELECT mode, embedding_fingerprint AS fp, applied_fingerprint AS applied "
            "FROM user_ai_settings WHERE user_id = :u"), {"u": user_id})
        m = r.mappings().first()
        assert m is not None
        return dict(m)


async def _note_status(note_id: str) -> str:
    async with get_sessionmaker()() as s:
        return (await s.execute(text(
            "SELECT index_status FROM notes WHERE id = :i"), {"i": note_id})).scalar_one()


async def _jobs_with_fp(fp: str) -> list[dict]:  # type: ignore[type-arg]
    async with get_sessionmaker()() as s:
        rows = await s.execute(text(
            "SELECT payload, status FROM jobs WHERE kind = 'semantic_search.index_note' "
            "AND payload->>'embedding_fingerprint' = :fp"), {"fp": fp})
        return [dict(r._mapping) for r in rows]


async def _save_direct(uid: uuid.UUID, data: AISettingsInput) -> None:
    """Save qua service BỎ QUA controller — giả lập crash sau commit #1, trước start_rebuild."""
    async with get_sessionmaker()() as s:
        await AISettingsService(s).save(uid, data)
        await s.commit()


async def _create_note(client, headers: dict[str, str], content: str) -> str:
    r = await client.post("/notes", json={"content": content}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_crash_between_save_and_rebuild_repaired(client) -> None:
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    note_id = await _create_note(client, h, "Ghi chú repair: crash giữa save và rebuild. " * 10)
    await drain()
    assert await _note_status(note_id) == "READY"

    # Crash giả lập: save BYOK commit config nhưng không hề start_rebuild.
    await _save_direct(uuid.UUID(uid), AISettingsInput(**BYOK))
    row = await _row(uid)
    assert row["fp"] == FP_BYOK
    assert row["applied"] != FP_BYOK  # chưa bàn giao (crash)

    # Worker repair: enqueue lại → note PROCESSING, applied cập nhật cùng transaction.
    async with get_sessionmaker()() as s:
        assert await repair_pending_rebuilds(s) == 1
    assert await _note_status(note_id) == "PROCESSING"
    assert (await _row(uid))["applied"] == FP_BYOK
    assert len(await _jobs_with_fp(FP_BYOK)) == 1

    # Delete về inherit (qua controller → có start_rebuild): job byok bị guard bỏ vì
    # fingerprint lệch, job server fp chạy với provider mock → READY, applied == fp.
    r = await client.delete("/me/ai-settings", headers=h)
    assert r.status_code == 200 and r.json()["rebuild"] == {"required": True, "notes": 1}
    await drain()
    assert await _note_status(note_id) == "READY"
    row = await _row(uid)
    assert row["mode"] == "inherit" and row["fp"] == FP_SERVER and row["applied"] == FP_SERVER


async def test_re_save_same_config_after_crash_triggers_rebuild(client) -> None:
    h = await login(client)
    uid = uuid.UUID((await client.get("/me", headers=h)).json()["id"])
    await _create_note(client, h, "Re-save cùng config sau crash vẫn phải rebuild. " * 10)
    await drain()

    await _save_direct(uid, AISettingsInput(**BYOK))  # crash trước start_rebuild
    # Re-save CÙNG config: applied cũ (không phải FP_BYOK) → vẫn rebuild_required=True.
    async with get_sessionmaker()() as s:
        saved = await AISettingsService(s).save(uid, AISettingsInput(**{**BYOK, "api_key": "sk-2"}))
        await s.commit()
    assert saved.rebuild_required is True and saved.fingerprint == FP_BYOK


async def test_start_rebuild_stale_fingerprint_is_noop(client) -> None:
    h = await login(client)
    uid = (await client.get("/me", headers=h)).json()["id"]
    note_id = await _create_note(client, h, "Save A rồi save B: start_rebuild(A) phải bị bỏ. " * 10)
    await drain()
    assert await _note_status(note_id) == "READY"

    await _save_direct(uuid.UUID(uid), AISettingsInput(**BYOK))  # config A (crash)
    other = {**BYOK, "base_url": "http://127.0.0.1:10/v1", "embedding_model": "bge-m3"}
    await _save_direct(uuid.UUID(uid), AISettingsInput(**other))  # config B ghi đè A

    # start_rebuild(A): fingerprint không còn current → notes=0, không mark, không enqueue.
    async with get_sessionmaker()() as s:
        plan = await start_rebuild(s, uuid.UUID(uid), fingerprint=FP_BYOK)
    assert plan.notes == 0
    assert await _note_status(note_id) == "READY"  # không bị mark PROCESSING oan
    assert await _jobs_with_fp(FP_BYOK) == []


async def test_inherit_repair_uses_server_fingerprint(client) -> None:
    h = await login(client)
    uid_uuid = uuid.UUID((await client.get("/me", headers=h)).json()["id"])
    uid = str(uid_uuid)
    note_id = await _create_note(client, h, "BYOK về inherit nhưng crash trước rebuild. " * 10)
    await drain()

    # byok + handoff đầy đủ (như controller): applied = FP_BYOK.
    await _save_direct(uid_uuid, AISettingsInput(**BYOK))
    async with get_sessionmaker()() as s:
        await start_rebuild(s, uid_uuid, fingerprint=FP_BYOK)
    assert (await _row(uid))["applied"] == FP_BYOK

    # Delete qua service (crash — không start_rebuild): inherit, fp=server, applied=FP_BYOK cũ.
    async with get_sessionmaker()() as s:
        saved = await AISettingsService(s).delete(uid_uuid)
        await s.commit()
    assert saved.rebuild_required is True
    row = await _row(uid)
    assert row["mode"] == "inherit" and row["fp"] == FP_SERVER and row["applied"] == FP_BYOK

    # Repair: inherit → dùng server fingerprint hiện tại, enqueue lại.
    async with get_sessionmaker()() as s:
        assert await repair_pending_rebuilds(s) == 1
    row = await _row(uid)
    assert row["applied"] == FP_SERVER
    assert len(await _jobs_with_fp(FP_SERVER)) == 1
    await drain()
    assert await _note_status(note_id) == "READY"

    # Save inherit lần nữa → đã applied server fp → không rebuild.
    async with get_sessionmaker()() as s:
        saved2 = await AISettingsService(s).save(uid_uuid, AISettingsInput(mode="inherit"))
        await s.commit()
    assert saved2.rebuild_required is False
