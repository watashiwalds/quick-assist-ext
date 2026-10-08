"""N05 — job index: READY / SKIPPED (hết quota, không trừ) / retry rồi FAILED, quota theo usage
thật, sửa note không kẹt PROCESSING, job cũ không ghi đè trạng thái mới."""

import pytest

from quickassist.business.semantic_search import indexing_job
from quickassist.infrastructure.jobs import drain, run_one_job
from quickassist.infrastructure.openai.base import AIProviderError
from quickassist.infrastructure.openai.mock_client import MockAIClient
from tests.conftest import login

pytestmark = pytest.mark.integration


class FlakyAI(MockAIClient):
    def __init__(self, fail_times: int, *, retryable: bool = True) -> None:
        super().__init__(1536)
        self.left, self.retryable, self.calls = fail_times, retryable, 0

    async def embed(self, texts):  # type: ignore[no-untyped-def,override]
        self.calls += 1
        if self.left > 0:
            self.left -= 1
            raise AIProviderError("boom", retryable=self.retryable)
        return await super().embed(texts)


async def _make_jobs_due() -> None:
    from sqlalchemy import text

    from quickassist.data.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("UPDATE jobs SET run_after = now() WHERE status = 'QUEUED'"))


async def _note(client, h, content: str = "Hướng dẫn cấu hình pgvector HNSW."):  # type: ignore[no-untyped-def]
    return (await client.post("/notes", json={"content": content}, headers=h)).json()


async def test_transient_error_retries_then_ready_and_charges_once(client, monkeypatch) -> None:
    ai = FlakyAI(fail_times=1)
    monkeypatch.setattr(indexing_job, "get_ai_provider", lambda: ai)
    h = await login(client)
    n = await _note(client, h)
    assert await run_one_job()  # lần 1 lỗi tạm thời → job QUEUED lại, note vẫn PROCESSING
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["index_status"] == "PROCESSING"
    assert (await client.get("/me/quota", headers=h)).json()["reserved_tokens"] == 0  # đã hoàn
    await _make_jobs_due()
    assert await run_one_job()
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["index_status"] == "READY"
    q = (await client.get("/me/quota", headers=h)).json()
    assert q["used_tokens"] > 0 and q["reserved_tokens"] == 0 and ai.calls == 2


async def test_retries_exhausted_marks_failed(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "job_max_attempts", 2)
    monkeypatch.setattr(indexing_job, "get_ai_provider", lambda: FlakyAI(fail_times=99))
    h = await login(client)
    n = await _note(client, h)
    await run_one_job()
    await _make_jobs_due()
    await run_one_job()
    got = (await client.get(f"/notes/{n['id']}", headers=h)).json()
    assert got["index_status"] == "FAILED"
    assert (await client.get("/me/quota", headers=h)).json()["used_tokens"] == 0


async def test_permanent_error_fails_immediately(client, monkeypatch) -> None:
    ai = FlakyAI(fail_times=1, retryable=False)
    monkeypatch.setattr(indexing_job, "get_ai_provider", lambda: ai)
    h = await login(client)
    n = await _note(client, h)
    await run_one_job()
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["index_status"] == "FAILED"
    # người dùng bấm "Thử lại AI"
    await client.post(f"/notes/{n['id']}/reindex", headers=h)
    await drain()
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["index_status"] == "READY"


async def test_stale_job_does_not_overwrite_newer_edit(client, monkeypatch) -> None:
    """Job của bản 1 chạy SAU khi note đã sửa thành bản 2 → không được đánh READY cho bản 2 sai."""
    h = await login(client)
    n = await _note(client, h, "bản một")
    await client.patch(f"/notes/{n['id']}", json={"version": 1, "content": "bản hai"}, headers=h)
    await drain()  # 1 job (dedupe) đọc nội dung MỚI nhất → READY đúng cho bản 2
    got = (await client.get(f"/notes/{n['id']}", headers=h)).json()
    assert got["index_status"] == "READY" and got["content"] == "bản hai"
    res = (await client.post("/search", json={"query": "bản hai"}, headers=h)).json()["items"]
    assert res and all("một" not in r["text"] for r in res)


async def test_deleted_note_chunks_are_removed(client) -> None:
    from sqlalchemy import text

    from quickassist.data.database import get_engine

    h = await login(client)
    n = await _note(client, h)
    await drain()
    await client.delete(f"/notes/{n['id']}", headers=h)
    await drain()
    async with get_engine().connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM note_chunks"))).scalar() == 0


async def test_unchanged_content_reuses_index_without_quota(client) -> None:
    h = await login(client)
    f = (await client.post("/folders", json={"name": "Khác"}, headers=h)).json()
    n = await _note(client, h)
    await drain()
    used = (await client.get("/me/quota", headers=h)).json()["used_tokens"]
    await client.patch(f"/notes/{n['id']}", json={"version": 1, "folder_id": f["id"]}, headers=h)
    await drain()
    assert (await client.get("/me/quota", headers=h)).json()["used_tokens"] == used
    res = await client.post("/search", json={"query": "pgvector", "folder_id": f["id"]}, headers=h)
    assert [r["note_id"] for r in res.json()["items"]] == [n["id"]]
