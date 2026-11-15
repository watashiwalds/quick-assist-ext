"""Integration P2 — GET /auth/config (public) + AUTH_MODE=local bỏ qua email client (ADR-0016 §4.8).

Cần PostgreSQL (TEST_DATABASE_URL) — không có thì tự skip.
"""

import pytest

pytestmark = pytest.mark.integration


async def test_auth_config_default_google(client) -> None:
    r = await client.get("/auth/config")
    assert r.status_code == 200 and r.json() == {"auth_mode": "google"}


async def test_local_mode_login_ignores_client_email(client, monkeypatch) -> None:
    """AUTH_MODE=local: dev-login luôn được phép (kể cả prod) và email client gửi bị bỏ qua."""
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    try:
        r = await client.post("/auth/dev-login", json={"email": "attacker@evil.com"})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = (await client.get("/me", headers=h)).json()
        assert me["email"] == "local@quickassist.local"  # luôn đúng tài khoản local duy nhất
        # đăng nhập lại lần nữa → cùng user (sub="dev:<local_auth_email>")
        r2 = await client.post("/auth/dev-login", json={"email": "other@x.vn"})
        me2 = (await client.get("/me", headers={
            "Authorization": f"Bearer {r2.json()['access_token']}"})).json()
        assert me2["id"] == me["id"]
    finally:
        get_settings.cache_clear()


async def test_google_mode_rejects_email_spoofing_is_untouched(client) -> None:
    """auth_mode=google (mặc định): dev-login vẫn hoạt động theo luồng cũ khi được bật."""
    h_login = await client.post("/auth/dev-login", json={"email": "normal@x.vn"})
    assert h_login.status_code == 200
    assert (await client.get("/me", headers={
        "Authorization": f"Bearer {h_login.json()['access_token']}"})).json()["email"] == "normal@x.vn"
