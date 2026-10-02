"""Luồng chính end-to-end trên PostgreSQL + pgvector thật, AI = mock."""

import uuid

import pytest

from quickassist.core.jobs import drain
from quickassist.registry import load_job_handlers
from tests.conftest import login

pytestmark = pytest.mark.integration
load_job_handlers()

NOTE = {"content": "PostgreSQL pgvector hỗ trợ tìm kiếm vector với chỉ mục HNSW.",
        "url": "https://example.com/docs/pgvector", "title": "pgvector docs"}


async def test_health(client) -> None:
    assert (await client.get("/health/ready")).json()["db"] == "ok"


async def test_requires_auth(client) -> None:
    r = await client.get("/notes")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "TOKEN_MISSING"
    assert r.json()["error"]["request_id"]


async def test_create_note_goes_to_inbox_and_is_idempotent(client) -> None:
    h = await login(client)
    key = {"Idempotency-Key": str(uuid.uuid4())}
    r1 = await client.post("/notes", json=NOTE, headers=h | key)
    r2 = await client.post("/notes", json=NOTE, headers=h | key)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["index_status"] == "PROCESSING"
    assert r1.json()["domain"] == "example.com"

    folders = (await client.get("/folders", headers=h)).json()
    assert [f["name"] for f in folders] == ["Inbox"]
    assert r1.json()["folder_id"] == folders[0]["id"]

    r3 = await client.post("/notes", json=NOTE | {"content": "khác"}, headers=h | key)
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len((await client.get("/notes", headers=h)).json()["items"]) == 1


async def test_other_user_cannot_see_or_edit(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    note = (await client.post("/notes", json=NOTE, headers=a)).json()
    assert (await client.get(f"/notes/{note['id']}", headers=b)).status_code == 404
    r = await client.patch(f"/notes/{note['id']}", json={"version": 1, "title": "hack"}, headers=b)
    assert r.status_code == 404
    assert (await client.delete(f"/notes/{note['id']}", headers=b)).status_code == 404


async def test_optimistic_concurrency(client) -> None:
    h = await login(client)
    note = (await client.post("/notes", json=NOTE, headers=h)).json()
    ok = await client.patch(f"/notes/{note['id']}", json={"version": 1, "title": "v2"}, headers=h)
    assert ok.status_code == 200 and ok.json()["version"] == 2
    stale = await client.patch(f"/notes/{note['id']}", json={"version": 1, "title": "x"}, headers=h)
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == 2


async def test_index_then_search_is_user_scoped(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    n1 = (await client.post("/notes", json=NOTE, headers=a)).json()
    await client.post("/notes", json={"content": "Công thức nấu phở bò Hà Nội."}, headers=a)
    await client.post("/notes", json={"content": "pgvector HNSW bí mật của B."}, headers=b)
    assert await drain() == 3

    got = (await client.get(f"/notes/{n1['id']}", headers=a)).json()
    assert got["index_status"] == "READY"

    res = (await client.post("/search", json={"query": "pgvector HNSW"}, headers=a)).json()["items"]
    assert res and res[0]["note_id"] == n1["id"]
    assert res[0]["note_url"] == NOTE["url"]
    assert all("của B" not in r["text"] for r in res)

    quota = (await client.get("/me/quota", headers=a)).json()
    assert quota["used_tokens"] > 0 and quota["reserved_tokens"] == 0


async def test_title_edit_does_not_leave_note_stuck_processing(client) -> None:
    h = await login(client)
    note = (await client.post("/notes", json=NOTE, headers=h)).json()
    await client.patch(f"/notes/{note['id']}", json={"version": 1, "title": "mới"}, headers=h)
    await drain()
    assert (await client.get(f"/notes/{note['id']}", headers=h)).json()["index_status"] == "READY"


async def test_folder_filter_and_delete_folder_moves_notes_to_inbox(client) -> None:
    h = await login(client)
    work = (await client.post("/folders", json={"name": "Công việc"}, headers=h)).json()
    n = (await client.post("/notes", json=NOTE | {"folder_id": work["id"]}, headers=h)).json()
    await drain()
    res = await client.post("/search", json={"query": "pgvector", "folder_id": work["id"]}, headers=h)
    assert [r["note_id"] for r in res.json()["items"]] == [n["id"]]

    assert (await client.delete(f"/folders/{work['id']}", headers=h)).status_code == 204
    await drain()
    moved = (await client.get(f"/notes/{n['id']}", headers=h)).json()
    inbox = (await client.get("/folders", headers=h)).json()[0]
    assert moved["folder_id"] == inbox["id"]


async def test_quota_exhausted_marks_note_skipped(client, monkeypatch) -> None:
    from quickassist.core.config import get_settings

    monkeypatch.setattr(get_settings(), "quota_default_tokens", 1)
    h = await login(client)
    note = (await client.post("/notes", json=NOTE, headers=h)).json()
    await drain()
    got = (await client.get(f"/notes/{note['id']}", headers=h)).json()
    assert got["index_status"] == "SKIPPED"
    assert (await client.get("/me/quota", headers=h)).json()["used_tokens"] == 0
    r = await client.post("/search", json={"query": "pgvector"}, headers=h)
    assert r.status_code == 402 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"


async def test_incremental_sync_returns_tombstones(client) -> None:
    h = await login(client)
    n = (await client.post("/notes", json=NOTE, headers=h)).json()
    since = n["created_at"]
    assert (await client.delete(f"/notes/{n['id']}", headers=h)).status_code == 204
    page = (await client.get("/notes", params={"updated_since": since}, headers=h)).json()
    assert page["items"][0]["id"] == n["id"] and page["items"][0]["deleted_at"]
    assert (await client.get("/notes", headers=h)).json()["items"] == []


async def test_summary_preview_then_confirm(client) -> None:
    h = await login(client)
    n = (await client.post("/notes", json=NOTE, headers=h)).json()
    p = await client.post("/ai/summaries", json={"note_id": n["id"]}, headers=h)
    assert p.status_code == 200 and p.json()["summary"]
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["summary_text"] is None
    s = await client.put(f"/notes/{n['id']}/summary",
                         json={"version": 1, "summary_text": p.json()["summary"]}, headers=h)
    assert s.status_code == 200 and s.json()["summary_text"]


async def test_refresh_rotation_and_reuse_detection(client) -> None:
    pair = (await client.post("/auth/dev-login", json={"email": "r@x.vn"})).json()
    new = await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert new.status_code == 200
    reuse = await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "REFRESH_REUSED"
    # mọi session bị thu hồi sau khi phát hiện tái sử dụng
    again = await client.post("/auth/refresh", json={"refresh_token": new.json()["refresh_token"]})
    assert again.status_code == 401


async def test_delete_account_removes_everything(client) -> None:
    from sqlalchemy import text

    from quickassist.core.db import get_engine

    h = await login(client)
    await client.post("/notes", json=NOTE, headers=h)
    await drain()
    assert (await client.delete("/me", headers=h)).status_code == 204
    async with get_engine().connect() as conn:
        for t in ("users", "auth_sessions", "folders", "notes", "note_chunks", "quota_accounts"):
            assert (await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar() == 0, t
