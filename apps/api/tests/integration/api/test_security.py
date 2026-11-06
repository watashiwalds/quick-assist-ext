"""H02 — hardening: mọi endpoint cần xác thực, chống IDOR trên MỌI route có id,
header bảo mật, rate limit (429 + Retry-After), CORS chỉ cho extension, không lộ lỗi nội bộ.

Danh sách route được LẤY TỰ ĐỘNG từ app → thêm endpoint mới mà quên kiểm tra quyền
là test đỏ.
"""

import pytest

from tests.conftest import login

pytestmark = pytest.mark.integration

PUBLIC = {"/health/live", "/health/ready", "/auth/google/exchange", "/auth/refresh",
          "/auth/logout", "/auth/dev-login"}
PREFIX = "/api/v1"
METHODS = {"get", "post", "put", "patch", "delete"}

BODIES = {  # body hợp lệ tối thiểu cho từng (method, path) để vượt qua validation
    ("PATCH", "/notes/{note_id}"): {"version": 1, "title": "hack"},
    ("PUT", "/notes/{note_id}/summary"): {"version": 1, "summary_text": "hack"},
    ("PATCH", "/folders/{folder_id}"): {"name": "hack"},
    ("POST", "/notes"): {"content": "x"},
    ("POST", "/folders"): {"name": "x"},
    ("POST", "/notes/bulk-delete"): {"ids": ["00000000-0000-0000-0000-000000000000"]},
    ("POST", "/search"): {"query": "x"},
    ("POST", "/ai/summaries"): {"text": "x"},
    ("POST", "/ai/chat"): {"question": "x"},
}


def _routes(app) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Mọi (method, path) công khai trong OpenAPI — nguồn sự thật của contract."""
    out = []
    for path, ops in app.openapi()["paths"].items():
        out += [(m.upper(), path[len(PREFIX):]) for m in ops if m in METHODS]
    return sorted(out)


async def test_every_private_endpoint_requires_token(app, client) -> None:
    checked = 0
    for method, path in _routes(app):
        if path in PUBLIC:
            continue
        url = path.replace("{note_id}", "00000000-0000-0000-0000-000000000000") \
                  .replace("{folder_id}", "00000000-0000-0000-0000-000000000000")
        r = await client.request(method, url, json=BODIES.get((method, path)))
        assert r.status_code == 401, f"{method} {path} → {r.status_code}"
        checked += 1
    assert checked >= 15


async def test_no_idor_on_any_route_with_id(app, client) -> None:
    a, b = await login(client, "owner@x.vn"), await login(client, "attacker@x.vn")
    note = (await client.post("/notes", json={"content": "bí mật của A"}, headers=a)).json()
    folder = (await client.post("/folders", json={"name": "A riêng"}, headers=a)).json()
    checked = 0
    for method, path in _routes(app):
        if "{note_id}" not in path and "{folder_id}" not in path:
            continue
        url = path.replace("{note_id}", note["id"]).replace("{folder_id}", folder["id"])
        r = await client.request(method, url, json=BODIES.get((method, path)), headers=b)
        assert r.status_code == 404, f"{method} {path} → {r.status_code}: {r.text}"
        assert "bí mật" not in r.text
        checked += 1
    assert checked >= 7
    # dữ liệu của A không đổi
    got = (await client.get(f"/notes/{note['id']}", headers=a)).json()
    assert got["version"] == 1 and got["summary_text"] is None and got["deleted_at"] is None
    assert (await client.get("/folders", headers=a)).json()[1]["name"] == "A riêng"


async def test_bulk_delete_and_search_cannot_reach_other_user(client) -> None:
    from quickassist.infrastructure.jobs import drain

    a, b = await login(client, "a@x.vn"), await login(client, "b@x.vn")
    n = (await client.post("/notes", json={"content": "kubernetes helm chart"}, headers=a)).json()
    await drain()
    r = await client.post("/notes/bulk-delete", json={"ids": [n["id"]]}, headers=b)
    assert r.json()["deleted"] == 0
    assert (await client.post("/search", json={"query": "kubernetes helm"}, headers=b)).json()["items"] == []
    s = await client.post("/ai/summaries", json={"note_id": n["id"]}, headers=b)
    assert s.status_code == 404


async def test_security_headers_and_request_id(client) -> None:
    r = await client.get("/health/live", headers={"X-Request-ID": "client-rid-123"})
    assert r.headers["X-Request-ID"] == "client-rid-123"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["X-Frame-Options"] == "DENY"
    bad = await client.get("/health/live", headers={"X-Request-ID": "x\ty"})
    assert bad.headers["X-Request-ID"] != "x\ty"


async def test_rate_limit_returns_429_with_retry_after(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_search_per_minute", 2)
    h = await login(client)
    codes = [(await client.post("/search", json={"query": "x"}, headers=h)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    r = await client.post("/search", json={"query": "x"}, headers=h)
    assert r.json()["error"]["code"] == "RATE_LIMITED" and int(r.headers["Retry-After"]) >= 1
    other = await login(client, "other@x.vn")  # đếm theo từng user
    assert (await client.post("/search", json={"query": "x"}, headers=other)).status_code == 200


async def test_cors_only_allows_configured_extension(monkeypatch) -> None:
    import httpx

    from quickassist.infrastructure.config import get_settings
    from quickassist.main import create_app

    monkeypatch.setattr(get_settings(), "cors_origins", ["chrome-extension://goodid"])
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"}
        ok = await c.options("/api/v1/notes", headers=pre | {"Origin": "chrome-extension://goodid"})
        assert ok.headers.get("access-control-allow-origin") == "chrome-extension://goodid"
        evil = await c.options("/api/v1/notes", headers=pre | {"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in evil.headers


def test_prod_config_guard(monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings
    from quickassist.main import _check_config

    s = get_settings()
    monkeypatch.setattr(s, "app_env", "prod")
    monkeypatch.setattr(s, "jwt_secret", type(s.jwt_secret)("change-me-in-env"))
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _check_config()
    monkeypatch.setattr(s, "jwt_secret", type(s.jwt_secret)("x" * 40))
    monkeypatch.setattr(s, "enable_dev_login", False)
    monkeypatch.setattr(s, "cors_origins", ["*"])
    with pytest.raises(RuntimeError, match="CORS"):
        _check_config()
    monkeypatch.setattr(s, "cors_origins", ["chrome-extension://abc"])
    _check_config()
