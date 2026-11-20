"""R01 + R03 + Phase 1 — hybrid retrieval + grouping source-first: tìm không dấu, cô lập dữ liệu
user, contract grouped (nguồn → ghi chú), ngưỡng OR (similarity HOẶC RRF), "Không rõ nguồn" cuối."""

import pytest

from quickassist.infrastructure.config import get_settings
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


def _flat(body: dict) -> list[dict]:
    """Phẳng hoá grouped → danh sách note theo thứ hạng nguồn rồi thứ hạng note."""
    return [n for s in body["sources"] for n in s["notes"]]


@pytest.mark.parametrize(("query", "expected_title"), [
    ("cong thuc nau pho", "Phở bò"),          # không dấu
    ("CÔNG THỨC PHỞ", "Phở bò"),               # viết hoa
    ("da nang cau rong", "Du lịch Đà Nẵng"),  # đ → d
    ("kubernetes deployment", "K8s"),
])
async def test_accent_insensitive_keyword_branch(client, query: str, expected_title: str) -> None:
    h = await login(client)
    await _seed(client, h)
    notes = _flat((await client.post("/search", json={"query": query}, headers=h)).json())
    assert notes and notes[0]["title"] == expected_title


async def test_grouped_contract_and_sources_ranked(client) -> None:
    h = await login(client)
    notes = await _seed(client, h)
    r = await client.post("/search", json={"query": "phở bò"}, headers=h)
    body = r.json()
    assert r.status_code == 200 and 1 <= len(body["sources"]) <= 5
    src = body["sources"][0]
    assert set(src) == {"domain", "label", "source_rank", "note_count", "notes",
                        "document_id", "source_type"}
    assert src["source_rank"] == 1 and src["domain"] == "amthuc.example" and src["label"] == "amthuc.example"
    assert src["document_id"] is None and src["source_type"] == "selection"
    note = src["notes"][0]
    assert set(note) == {"note_id", "title", "url", "summary", "snippet", "score", "similarity",
                         "part_index", "part_count"}
    assert note["part_index"] == 0 and note["part_count"] == 1
    assert note["note_id"] == notes[0]["id"] and note["title"] == "Phở bò"
    assert note["url"] == "https://amthuc.example/pho" and "phở bò" in note["snippet"].lower()
    assert 0.0 <= note["similarity"] <= 1.0 and note["score"] > 0
    assert (await client.post("/search", json={"query": "x", "max_sources": 21},
                              headers=h)).status_code == 422
    assert (await client.post("/search", json={"query": ""}, headers=h)).status_code == 422


async def test_unknown_source_group_last(client) -> None:
    h = await login(client)
    await _seed(client, h)
    body = (await client.post("/search", json={"query": "phở kubernetes đà nẵng cầu rồng"},
                              headers=h)).json()
    assert len(body["sources"]) >= 2
    labels = [s["label"] for s in body["sources"]]
    assert labels[-1] == "Không rõ nguồn"  # note không URL luôn xếp cuối
    unknown = body["sources"][-1]
    assert unknown["domain"] is None and unknown["notes"][0]["title"] == "Du lịch Đà Nẵng"
    assert unknown["notes"][0]["url"] is None


async def test_max_sources_limits_number_of_groups(client) -> None:
    h = await login(client)
    await _seed(client, h)
    body = (await client.post("/search", json={"query": "phở kubernetes đà nẵng cầu rồng",
                                               "max_sources": 1}, headers=h)).json()
    assert len(body["sources"]) == 1


async def test_notes_per_source_cap_and_note_count(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "search_notes_per_source", 1)
    h = await login(client)
    # 2 note cùng domain amthuc.example → nguồn đó note_count=2 nhưng chỉ trả 1 note
    await client.post("/notes", json={"content": "Phở bò Hà Nội hầm xương 8 tiếng.",
                                      "title": "Phở bò", "url": "https://amthuc.example/pho"},
                      headers=h)
    await client.post("/notes", json={"content": "Bún bò Huế cay, dùng xương bò hầm nước lèo.",
                                      "title": "Bún bò", "url": "https://amthuc.example/bun-bo"},
                      headers=h)
    await drain()
    body = (await client.post("/search", json={"query": "bò hầm xương nấu"}, headers=h)).json()
    assert len(body["sources"]) == 1
    src = body["sources"][0]
    assert src["domain"] == "amthuc.example"
    assert src["note_count"] == 2 and len(src["notes"]) == 1


async def test_below_threshold_returns_no_sources(client) -> None:
    h = await login(client)
    await _seed(client, h)
    # Câu hỏi chẳng liên quan gì 3 ghi chú: mock embedding gần như không trùng từ,
    # cosine < 0.5 và RRF < 0.03 → rỗng (empty state "không có nguồn đủ tin cậy").
    body = (await client.post("/search", json={"query": "blockchain bitcoin ví điện tử"},
                              headers=h)).json()
    assert body["sources"] == []


async def test_isolation_even_with_guessed_folder_id(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    notes_a = await _seed(client, a)
    folder_a = notes_a[0]["folder_id"]
    r = await client.post("/search", json={"query": "phở bò", "folder_id": folder_a}, headers=b)
    assert r.status_code == 200 and r.json()["sources"] == []
    r = await client.post("/search", json={"query": "phở bò kubernetes đà nẵng"}, headers=b)
    assert r.json()["sources"] == []


async def test_deleted_notes_disappear_from_results(client) -> None:
    h = await login(client)
    notes = await _seed(client, h)
    await client.delete(f"/notes/{notes[0]['id']}", headers=h)
    # ngay cả khi job xoá chunk CHƯA chạy, kết quả đã lọc note đã xoá
    flat = _flat((await client.post("/search", json={"query": "phở bò"}, headers=h)).json())
    assert all(n["note_id"] != notes[0]["id"] for n in flat)


async def test_each_search_charges_quota(client) -> None:
    h = await login(client)
    await _seed(client, h)
    before = (await client.get("/me/quota", headers=h)).json()["used_tokens"]
    await client.post("/search", json={"query": "phở"}, headers=h)
    after = (await client.get("/me/quota", headers=h)).json()
    assert after["used_tokens"] > before and after["reserved_tokens"] == 0
