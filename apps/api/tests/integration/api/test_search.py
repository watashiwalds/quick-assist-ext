"""R01 + R03 — hybrid retrieval: tìm không dấu, cô lập dữ liệu user (kể cả khi đoán folder_id
của người khác), top-k kèm score + tiêu đề/URL nguồn, quota trừ đúng, contract."""

import pytest

from quickassist.infrastructure.jobs import drain
from tests.conftest import login

pytestmark = pytest.mark.integration

NOTES = [
    {"content": "Công thức nấu phở bò Hà Nội: hầm xương 8 tiếng, thêm quế hồi.", "title": "Phở bò",
     "url": "https://amthuc.example/pho"},
    {"content": "Kubernetes dùng Deployment để quản lý ReplicaSet và Pod.", "title": "K8s",
     "url": "https://k8s.example/deploy"},
    {"content": "Đà Nẵng có cầu Rồng phun lửa vào tối thứ bảy và chủ nhật.", "title": "Du lịch Đà Nẵng"},
]


async def _seed(client, h) -> list[dict]:  # type: ignore[no-untyped-def]
    ids = [(await client.post("/notes", json=n, headers=h)).json() for n in NOTES]
    await drain()
    return ids


@pytest.mark.parametrize(("query", "expected_title"), [
    ("cong thuc nau pho", "Phở bò"),          # không dấu
    ("CÔNG THỨC PHỞ", "Phở bò"),               # viết hoa
    ("da nang cau rong", "Du lịch Đà Nẵng"),  # đ → d
    ("kubernetes deployment", "K8s"),
])
async def test_accent_insensitive_keyword_branch(client, query: str, expected_title: str) -> None:
    h = await login(client)
    await _seed(client, h)
    items = (await client.post("/search", json={"query": query}, headers=h)).json()["items"]
    assert items and items[0]["note_title"] == expected_title


async def test_result_contract_and_scores_sorted(client) -> None:
    h = await login(client)
    notes = await _seed(client, h)
    r = await client.post("/search", json={"query": "phở bò", "top_k": 2}, headers=h)
    items = r.json()["items"]
    assert r.status_code == 200 and 1 <= len(items) <= 2
    assert set(items[0]) == {"chunk_id", "note_id", "text", "score", "note_title", "note_url", "folder_id"}
    assert items[0]["note_url"] == "https://amthuc.example/pho" and items[0]["note_id"] == notes[0]["id"]
    assert all(a["score"] >= b["score"] > 0 for a, b in zip(items, items[1:], strict=False))
    assert (await client.post("/search", json={"query": "x", "top_k": 21}, headers=h)).status_code == 422
    assert (await client.post("/search", json={"query": ""}, headers=h)).status_code == 422


async def test_isolation_even_with_guessed_folder_id(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    notes_a = await _seed(client, a)
    folder_a = notes_a[0]["folder_id"]
    r = await client.post("/search", json={"query": "phở bò", "folder_id": folder_a}, headers=b)
    assert r.status_code == 200 and r.json()["items"] == []
    r = await client.post("/search", json={"query": "phở bò kubernetes đà nẵng"}, headers=b)
    assert r.json()["items"] == []


async def test_deleted_notes_disappear_from_results(client) -> None:
    h = await login(client)
    notes = await _seed(client, h)
    await client.delete(f"/notes/{notes[0]['id']}", headers=h)
    # ngay cả khi job xoá chunk CHƯA chạy, kết quả đã lọc note đã xoá
    items = (await client.post("/search", json={"query": "phở bò"}, headers=h)).json()["items"]
    assert all(i["note_id"] != notes[0]["id"] for i in items)


async def test_each_search_charges_quota(client) -> None:
    h = await login(client)
    await _seed(client, h)
    before = (await client.get("/me/quota", headers=h)).json()["used_tokens"]
    await client.post("/search", json={"query": "phở"}, headers=h)
    after = (await client.get("/me/quota", headers=h)).json()
    assert after["used_tokens"] > before and after["reserved_tokens"] == 0
