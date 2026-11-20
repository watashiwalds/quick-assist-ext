"""D2 — tài liệu dài gồm nhiều part: tạo atomic, lấy theo document_id, lan metadata,
grouping một nguồn trong search/RAG, xoá/di chuyển theo danh sách part."""

import json
import uuid

import pytest

from quickassist.infrastructure.jobs import drain
from tests.conftest import login

pytestmark = pytest.mark.integration


def headers() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _create_document(client, h, *, parts: list[str], title: str = "Bài báo dài",
                           url: str | None = None) -> dict:  # type: ignore[no-untyped-def]
    body = {"title": title, "document_id": str(uuid.uuid4()), "parts": parts}
    if url:
        body["url"] = url
    r = await client.post("/notes", json=body, headers=h | headers())
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_document_parts_and_list_by_document(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    parts = ["Phần một: mở đầu.", "Phần hai: nội dung giữa.", "Phần ba: kết luận."]
    r = await client.post("/notes", json={
        "title": "Tài liệu dài", "document_id": str(uuid.uuid4()), "parts": parts},
        headers=h | headers())
    assert r.status_code == 201
    created = r.json()
    assert created["document_id"] is not None
    assert created["part_index"] == 0 and created["part_count"] == 3
    assert created["source_type"] == "document"
    assert created["original_chars"] == sum(map(len, parts))
    assert len(created["part_ids"]) == 3

    page = (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()
    assert [p["part_index"] for p in page["items"]] == [0, 1, 2]
    assert [p["id"] for p in page["items"]] == created["part_ids"]
    assert [p["content"] for p in page["items"]] == parts

    # Retry cùng document_id (key khác) → idempotent, không tạo thêm part.
    again = await client.post("/notes", json={
        "title": "Tài liệu dài", "document_id": created["document_id"], "parts": parts},
        headers=h | headers())
    assert again.status_code == 201 and again.json()["id"] == created["part_ids"][0]
    all_notes = (await client.get("/notes", headers=h)).json()["items"]
    assert len(all_notes) == 3


async def test_create_document_is_atomic_and_validates_input(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    doc = str(uuid.uuid4())

    # Part quá dài → 413, không để lại part mồ côi.
    bad = await client.post("/notes", json={"document_id": doc, "parts": ["x", "a" * 20_001]},
                            headers=h | headers())
    assert bad.status_code == 413 and bad.json()["error"]["code"] == "NOTE_TOO_LONG"
    assert (await client.get("/notes", headers=h)).json()["items"] == []

    # parts phải đi cùng document_id; không gửi đồng thời content và parts.
    assert (await client.post("/notes", json={"parts": ["x"]}, headers=h)).status_code == 422
    assert (await client.post("/notes", json={"content": "x", "document_id": doc, "parts": ["y"]},
                              headers=h)).status_code == 422
    assert (await client.post("/notes", json={"document_id": doc, "parts": ["  "]},
                              headers=h)).status_code == 422

    created = await client.post("/notes", json={"document_id": doc, "parts": ["a", "b"]},
                                headers=h | headers())
    assert created.status_code == 201
    # Cùng document_id nhưng khác số part → 409, không tạo thêm.
    conflict = await client.post("/notes", json={"document_id": doc, "parts": ["a", "b", "c"]},
                                 headers=h | headers())
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "DOCUMENT_ID_CONFLICT"


async def test_update_part_propagates_document_metadata(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    parts = ["Nội dung một.", "Nội dung hai.", "Nội dung ba."]
    created = await _create_document(client, h, parts=parts)
    folder = (await client.post("/folders", json={"name": "Tài liệu"}, headers=h)).json()

    # Sửa title + folder trên part 1 → lan sang mọi part.
    r = await client.patch(f"/notes/{created['part_ids'][1]}", json={
        "version": 1, "title": "Tên mới", "folder_id": folder["id"],
    }, headers=h)
    assert r.status_code == 200 and r.json()["title"] == "Tên mới"
    page = (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()["items"]
    assert {p["title"] for p in page} == {"Tên mới"}
    assert {p["folder_id"] for p in page} == {folder["id"]}
    assert {p["version"] for p in page} == {2}

    await drain()
    assert {p["index_status"] for p in
            (await client.get("/notes", params={"document_id": created["document_id"]},
                              headers=h)).json()["items"]} == {"READY"}

    # Sửa nội dung chỉ ảnh hưởng part được chọn.
    r = await client.patch(f"/notes/{created['part_ids'][2]}", json={
        "version": 2, "content": "Nội dung ba đã sửa.",
    }, headers=h)
    assert r.status_code == 200
    page = (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()["items"]
    assert [p["content"] for p in page] == [parts[0], parts[1], "Nội dung ba đã sửa."]
    assert [p["version"] for p in page] == [2, 2, 3]


async def test_search_and_chat_group_document_as_one_source(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    parts = [
        "Phần đầu nói về thời tiết và du lịch.",
        "Phần giữa hướng dẫn công thức nấu phở bò Hà Nội: hầm xương 8 tiếng, thêm quế hồi.",
        "Phần cuối nói về lịch sử và văn hoá.",
    ]
    created = await _create_document(client, h, parts=parts, title="Tài liệu nấu phở")
    await drain()

    body = (await client.post("/search", json={"query": "phở bò hầm xương"}, headers=h)).json()
    assert len(body["sources"]) == 1
    src = body["sources"][0]
    assert src["document_id"] == created["document_id"]
    assert src["source_type"] == "document" and src["label"] == "Tài liệu nấu phở"
    assert src["note_count"] >= 1  # chỉ part đạt ngưỡng, nhưng vẫn là MỘT nguồn tài liệu
    assert {n["part_count"] for n in src["notes"]} == {3}
    assert any(n["part_index"] == 1 for n in src["notes"])

    # RAG SSE: nguồn tài liệu mang label + part metadata; legacy vẫn giữ source_domain.
    r = await client.post("/ai/chat", json={"question": "phở bò hầm xương"}, headers=h)
    assert r.status_code == 200
    first = r.text.strip().split("\n\n")[0]
    sources = json.loads(first.split("data: ", 1)[1])
    assert sources and sources[0]["source_label"] == "Tài liệu nấu phở"
    assert sources[0]["part_count"] == 3 and 0 <= sources[0]["part_index"] < 3


async def test_legacy_note_keeps_old_contract(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    note = (await client.post("/notes", json={"content": "Ghi chú cũ ≤ 20k"},
                              headers=h | headers())).json()
    assert note["document_id"] is None
    assert note["part_index"] == 0 and note["part_count"] == 1
    assert note["source_type"] == "selection"
    assert note["original_chars"] is None and note["part_ids"] is None


def _part_text(index: int, size: int) -> str:
    """Part đúng ``size`` ký tự (không vượt 20k) để dựng tài liệu 157k."""
    head = f"Phần {index}: "
    filler = ("nội dung thường gặp trong tài liệu dài " * 2000)[: size - len(head)]
    return head + filler


async def test_document_157k_all_parts_ready_and_moved(client) -> None:  # type: ignore[no-untyped-def]
    """Acceptance Lát 1: tài liệu 156.885 ký tự → 8 part ≤ 20k, tất cả READY, move cả document."""
    h = await login(client)
    total, count = 156_885, 8
    base, remainder = divmod(total, count)
    parts = [_part_text(i, base + (1 if i < remainder else 0)) for i in range(count)]
    assert max(map(len, parts)) <= 20_000

    created = await _create_document(client, h, parts=parts, title="Tài liệu 157k")
    assert created["part_count"] == count
    assert created["original_chars"] == total
    assert len(created["part_ids"]) == count

    await drain()
    page = (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()["items"]
    assert [p["index_status"] for p in page] == ["READY"] * count
    assert sum(len(p["content"]) for p in page) == total

    folder = (await client.post("/folders", json={"name": "Tài liệu dài"}, headers=h)).json()
    moved = await client.post("/notes/move", json={
        "ids": created["part_ids"], "folder_id": folder["id"]}, headers=h)
    assert moved.status_code == 200 and moved.json() == {"moved": count, "missing": []}
    page = (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()["items"]
    assert {p["folder_id"] for p in page} == {folder["id"]}


async def test_bulk_delete_document_parts(client) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    created = await _create_document(client, h, parts=["a", "b", "c"])
    r = await client.post("/notes/bulk-delete", json={"ids": created["part_ids"]}, headers=h)
    assert r.status_code == 200 and r.json()["deleted"] == 3
    assert (await client.get("/notes", params={"document_id": created["document_id"]},
                             headers=h)).json()["items"] == []
