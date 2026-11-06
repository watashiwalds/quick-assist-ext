"""A06 — GET/DELETE /me: xoá tài khoản trong 1 transaction, lỗi giữa chừng → rollback."""

import pytest

from tests.conftest import login

pytestmark = pytest.mark.integration


async def test_get_me(client) -> None:
    h = await login(client, "me@x.vn")
    r = await client.get("/me", headers=h)
    assert r.status_code == 200 and r.json()["email"] == "me@x.vn"
    assert set(r.json()) == {"id", "email", "display_name", "avatar_url", "created_at"}


async def test_delete_twice_and_old_token_no_longer_works(client) -> None:
    h = await login(client)
    assert (await client.delete("/me", headers=h)).status_code == 204
    r = await client.delete("/me", headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "USER_NOT_FOUND"
    assert (await client.get("/me", headers=h)).status_code == 404


async def test_delete_does_not_touch_other_users(client) -> None:
    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    await client.post("/notes", json={"content": "B giữ lại"}, headers=b)
    await client.delete("/me", headers=a)
    assert len((await client.get("/notes", headers=b)).json()["items"]) == 1


async def test_failure_mid_transaction_rolls_back(app, client, monkeypatch) -> None:
    import httpx

    from quickassist.business.auth import account_service

    h = await login(client)
    await client.post("/notes", json={"content": "x"}, headers=h)

    async def broken_commit(self) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("db died")

    monkeypatch.setattr(account_service.AsyncSession, "commit", broken_commit)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)  # nhận đúng response 500
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as raw:
        r = await raw.delete("/me", headers=h)
    assert r.status_code == 500 and "db died" not in r.text  # không lộ lỗi nội bộ
    monkeypatch.undo()
    assert (await client.get("/me", headers=h)).status_code == 200
    assert len((await client.get("/notes", headers=h)).json()["items"]) == 1
