"""A02 — xác minh id_token Google với khoá ký GIẢ LẬP (không gọi mạng).

Kiểm tra đủ: chữ ký, iss, aud, exp, nonce, email_verified, redirect_uri cho phép,
và lỗi kết nối Google → upstream.
"""

import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from quickassist.infrastructure.config import Settings
from quickassist.infrastructure.errors import OAuthError
from quickassist.infrastructure.google_oauth.oidc_client import GoogleOIDCClient

CLIENT_ID = "cid.apps.googleusercontent.com"
REDIRECT = "https://abcdefgh.chromiumapp.org/"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWKS:
    """Thay PyJWKClient: luôn trả public key của _KEY."""

    def get_signing_key_from_jwt(self, _token: str):  # type: ignore[no-untyped-def]
        return type("K", (), {"key": _KEY.public_key()})()


def make_id_token(key=_KEY, **over) -> str:  # type: ignore[no-untyped-def]
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "google-sub-1",
        "email": "a@gmail.com", "email_verified": True, "name": "A", "picture": None,
        "iat": now, "exp": now + 600, "nonce": "n" * 16,
    } | over
    claims = {k: v for k, v in claims.items() if v is not ...}
    return jwt.encode(claims, key, algorithm="RS256")


def make_client(token_handler=None) -> GoogleOIDCClient:  # type: ignore[no-untyped-def]
    s = Settings(google_client_id=CLIENT_ID, google_client_secret="sec",
                 oauth_allowed_redirect_uris=[REDIRECT])
    handler = token_handler or (lambda req: httpx.Response(200, json={"id_token": make_id_token()}))
    return GoogleOIDCClient(s, transport=httpx.MockTransport(handler), jwks=_FakeJWKS())  # type: ignore[arg-type]


def test_valid_token_returns_identity() -> None:
    ident = make_client().verify_id_token(make_id_token(), nonce="n" * 16)
    assert ident.sub == "google-sub-1" and ident.email == "a@gmail.com" and ident.email_verified


@pytest.mark.parametrize(("over", "code"), [
    ({"aud": "other-client"}, "OAUTH_ID_TOKEN_INVALID"),
    ({"iss": "https://evil.example.com"}, "OAUTH_ID_TOKEN_INVALID"),
    ({"exp": int(time.time()) - 10}, "OAUTH_ID_TOKEN_INVALID"),
    ({"nonce": "x" * 16}, "OAUTH_NONCE_MISMATCH"),
    ({"nonce": ...}, "OAUTH_ID_TOKEN_INVALID"),
    ({"email_verified": False}, "OAUTH_EMAIL_UNVERIFIED"),
])
def test_invalid_claims_rejected(over: dict, code: str) -> None:
    with pytest.raises(OAuthError) as e:
        make_client().verify_id_token(make_id_token(**over), nonce="n" * 16)
    assert e.value.code == code


def test_wrong_signature_rejected() -> None:
    with pytest.raises(OAuthError) as e:
        make_client().verify_id_token(make_id_token(key=_OTHER_KEY), nonce="n" * 16)
    assert e.value.code == "OAUTH_ID_TOKEN_INVALID"


async def test_exchange_sends_pkce_and_secret_server_side() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(dict(x.split("=", 1) for x in req.content.decode().split("&")))
        return httpx.Response(200, json={"id_token": "tok"})

    assert await make_client(handler).exchange_code(code="c", code_verifier="v" * 43,
                                                    redirect_uri=REDIRECT) == "tok"
    assert seen["code_verifier"] == "v" * 43 and seen["client_secret"] == "sec"
    assert seen["grant_type"] == "authorization_code"


async def test_exchange_rejects_unknown_redirect_uri() -> None:
    with pytest.raises(OAuthError) as e:
        await make_client().exchange_code(code="c", code_verifier="v" * 43,
                                          redirect_uri="https://evil.chromiumapp.org/")
    assert e.value.code == "OAUTH_REDIRECT_INVALID"


async def test_exchange_bad_code_and_upstream_down() -> None:
    bad = make_client(lambda r: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(OAuthError) as e:
        await bad.exchange_code(code="c", code_verifier="v" * 43, redirect_uri=REDIRECT)
    assert e.value.code == "OAUTH_CODE_INVALID" and not e.value.upstream

    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(OAuthError) as e:
        await make_client(boom).exchange_code(code="c", code_verifier="v" * 43, redirect_uri=REDIRECT)
    assert e.value.upstream
