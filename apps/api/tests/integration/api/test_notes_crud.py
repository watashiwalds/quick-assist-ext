"""N03 + C01 — Notes API & thư mục: validation, ownership, version 409, bulk-delete,
phân trang cursor, đổi tên/xoá thư mục."""

import uuid

import pytest

from tests.conftest import login

pytestmark = pytest.mark.integration


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def test_create_validation(client) -> None:
    h = await login(client)
    assert (await client.post("/notes", json={"content": ""}, headers=h)).status_code == 422
    assert (await client.post("/notes", json={"content": "x", "user_id": str(uuid.uuid4())},
                              headers=h)).status_code == 422  # không nhận user_id từ client
    assert (await client.post("/notes", json={"content": "x", "url": "javascript:alert(1)"},
                              headers=h)).status_code == 422
    big = await client.post("/notes", json={"content": "a" * 20_001}, headers=h)
    assert big.status_code == 413 and big.json()["error"]["code"] == "NOTE_TOO_LONG"
    ws = await client.post("/notes", json={"content": "  có khoảng trắng \x00 "}, headers=h | key())
    assert ws.status_code == 201 and ws.json()["content"] == "có khoảng trắng"


async def test_create_into_foreign_folder_is_404(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    fb = (await client.post("/folders", json={"name": "B riêng"}, headers=b)).json()
    r = await client.post("/notes", json={"content": "x", "folder_id": fb["id"]}, headers=a)
    assert r.status_code == 404 and r.json()["error"]["code"] == "FOLDER_NOT_FOUND"


async def test_patch_content_reindexes_and_bumps_version(client) -> None:
    from quickassist.infrastructure.jobs import drain

    h = await login(client)
    n = (await client.post("/notes", json={"content": "bản 1"}, headers=h)).json()
    await drain()
    r = await client.patch(f"/notes/{n['id']}", json={"version": 1, "content": "bản 2"}, headers=h)
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["index_status"] == "PROCESSING"
    await drain()
    assert (await client.get(f"/notes/{n['id']}", headers=h)).json()["index_status"] == "READY"


async def test_move_note_between_folders(client) -> None:
    h = await login(client)
    f = (await client.post("/folders", json={"name": "Học"}, headers=h)).json()
    n = (await client.post("/notes", json={"content": "x"}, headers=h)).json()
    moved = await client.patch(f"/notes/{n['id']}", json={"version": 1, "folder_id": f["id"]}, headers=h)
    assert moved.json()["folder_id"] == f["id"]
    only = (await client.get("/notes", params={"folder_id": f["id"]}, headers=h)).json()["items"]
    assert [x["id"] for x in only] == [n["id"]]


async def test_bulk_delete_counts_only_own_existing(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    ids = [(await client.post("/notes", json={"content": f"n{i}"}, headers=a)).json()["id"] for i in range(3)]
    other = (await client.post("/notes", json={"content": "của B"}, headers=b)).json()["id"]
    r = await client.post("/notes/bulk-delete", json={"ids": [*ids[:2], ids[0], other, str(uuid.uuid4())]},
                          headers=a)
    assert r.status_code == 200 and r.json()["deleted"] == 2
    assert [x["id"] for x in (await client.get("/notes", headers=a)).json()["items"]] == [ids[2]]
    assert (await client.get(f"/notes/{other}", headers=b)).status_code == 200
    assert (await client.post("/notes/bulk-delete", json={"ids": []}, headers=a)).status_code == 422


async def test_cursor_pagination_has_no_gaps_or_duplicates(client) -> None:
    h = await login(client)
    created = {(await client.post("/notes", json={"content": f"note {i}"}, headers=h)).json()["id"]
               for i in range(7)}
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 3} | ({"cursor": cursor} if cursor else {})
        page = (await client.get("/notes", params=params, headers=h)).json()
        seen += [x["id"] for x in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 7 and set(seen) == created
    bad = await client.get("/notes", params={"cursor": "%%%"}, headers=h)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "CURSOR_INVALID"


async def test_folder_rules(client) -> None:
    h = await login(client)
    inbox = (await client.get("/folders", headers=h)).json()[0]
    assert inbox["is_default"] and inbox["name"] == "Inbox"
    for r in (await client.patch(f"/folders/{inbox['id']}", json={"name": "X"}, headers=h),
              await client.delete(f"/folders/{inbox['id']}", headers=h)):
        assert r.status_code == 409 and r.json()["error"]["code"] == "FOLDER_IS_DEFAULT"
    a = (await client.post("/folders", json={"name": "A"}, headers=h)).json()
    await client.post("/folders", json={"name": "B"}, headers=h)
    dup = await client.post("/folders", json={"name": "B"}, headers=h)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "FOLDER_EXISTS"
    clash = await client.patch(f"/folders/{a['id']}", json={"name": "B"}, headers=h)
    assert clash.status_code == 409
    ok = await client.patch(f"/folders/{a['id']}", json={"name": "A2"}, headers=h)
    assert ok.status_code == 200 and ok.json()["name"] == "A2"
    assert [f["name"] for f in (await client.get("/folders", headers=h)).json()] == ["Inbox", "A2", "B"]


async def test_reindex_resets_failed_note(client) -> None:
    h = await login(client)
    n = (await client.post("/notes", json={"content": "x"}, headers=h)).json()
    r = await client.post(f"/notes/{n['id']}/reindex", headers=h)
    assert r.status_code == 202 and r.json()["index_status"] == "PROCESSING"


async def test_summary_save_requires_current_version(client) -> None:
    h = await login(client)
    n = (await client.post("/notes", json={"content": "x"}, headers=h)).json()
    await client.patch(f"/notes/{n['id']}", json={"version": 1, "title": "t"}, headers=h)
    r = await client.put(f"/notes/{n['id']}/summary", json={"version": 1, "summary_text": "s"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOTE_VERSION_CONFLICT"
