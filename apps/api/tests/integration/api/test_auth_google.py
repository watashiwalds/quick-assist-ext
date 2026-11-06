"""A02 — đăng nhập Google qua API với id_token giả lập (không gọi Google thật)."""

import pytest

from quickassist.presentation.api.v1.controllers import auth_controller
from tests.unit.infrastructure.test_google_oidc import REDIRECT, make_client, make_id_token

pytestmark = pytest.mark.integration

BODY = {"code": "auth-code", "code_verifier": "v" * 43, "redirect_uri": REDIRECT, "nonce": "n" * 16}


def _use_token(monkeypatch, token: str) -> None:  # type: ignore[no-untyped-def]
    import httpx

    client = make_client(lambda r: httpx.Response(200, json={"id_token": token}))
    monkeypatch.setattr(auth_controller, "_oidc", lambda: client)


async def test_exchange_creates_user_then_reuses_it(client, monkeypatch) -> None:
    _use_token(monkeypatch, make_id_token())
    first = await client.post("/auth/google/exchange", json=BODY)
    assert first.status_code == 200, first.text
    assert first.json()["is_new_user"] is True and first.json()["token_type"] == "Bearer"
    second = await client.post("/auth/google/exchange", json=BODY)
    assert second.json()["is_new_user"] is False
    me = await client.get("/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "a@gmail.com"


@pytest.mark.parametrize(("claims", "code"), [
    ({"nonce": "z" * 16}, "OAUTH_NONCE_MISMATCH"),
    ({"aud": "someone-else"}, "OAUTH_ID_TOKEN_INVALID"),
    ({"email_verified": False}, "OAUTH_EMAIL_UNVERIFIED"),
])
async def test_exchange_rejects_bad_id_token(client, monkeypatch, claims, code) -> None:  # type: ignore[no-untyped-def]
    _use_token(monkeypatch, make_id_token(**claims))
    r = await client.post("/auth/google/exchange", json=BODY)
    assert r.status_code == 401 and r.json()["error"]["code"] == code


async def test_exchange_validates_pkce_shape(client) -> None:
    r = await client.post("/auth/google/exchange", json=BODY | {"code_verifier": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "short" not in r.text  # không phản hồi lại giá trị đầu vào


async def test_google_down_is_502(client, monkeypatch) -> None:
    import httpx

    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(auth_controller, "_oidc", lambda: make_client(boom))
    r = await client.post("/auth/google/exchange", json=BODY)
    assert r.status_code == 502 and r.json()["error"]["code"] == "OAUTH_UPSTREAM"


async def test_logout_revokes_refresh(client) -> None:
    pair = (await client.post("/auth/dev-login", json={"email": "l@x.vn"})).json()
    out = await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
    assert out.status_code == 204
    r = await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401


async def test_expired_access_token_is_401_token_expired(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "access_token_ttl_seconds", -60)
    pair = (await client.post("/auth/dev-login", json={"email": "e@x.vn"})).json()
    r = await client.get("/me", headers={"Authorization": f"Bearer {pair['access_token']}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"
