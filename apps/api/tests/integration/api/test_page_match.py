"""AutoChunk — POST /ai/page-match: contract, 413/422, verify JSON / fallback VERIFY_UNAVAILABLE,
2 lease quota (embed + verify), full_page, rate limit, lưu kết quả bằng POST /notes."""

import uuid
from pathlib import Path

import pytest

from quickassist.infrastructure.openai.base import AIProviderError, CompletionResult, Usage
from quickassist.infrastructure.openai.mock_client import MockAIClient
from tests.conftest import login

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html"
RESOLUTIONS = (FIXTURES / "resolutions.html").read_text(encoding="utf-8")
QUERY = "nghị quyết đất đai"


def _body(query: str = QUERY, html: str = RESOLUTIONS) -> dict[str, str]:
    return {"query": query, "html": html, "url": "https://example.vn/nghi-quyet", "title": "Nghị quyết"}


class _Spy(MockAIClient):
    def __init__(self) -> None:
        super().__init__(1536)
        self.embed_calls: list[int] = []
        self.complete_calls = 0

    async def embed(self, texts):  # type: ignore[no-untyped-def,override]
        self.embed_calls.append(len(texts))
        return await super().embed(texts)

    async def complete(self, messages, *, max_tokens):  # type: ignore[no-untyped-def,override]
        self.complete_calls += 1
        return await super().complete(messages, max_tokens=max_tokens)


async def _ledger_ops() -> list[tuple[str, str]]:
    from sqlalchemy import text

    from quickassist.data.database import get_engine

    async with get_engine().connect() as c:
        rows = await c.execute(text("SELECT operation, status FROM quota_ledger ORDER BY created_at"))
        return [(r[0], r[1]) for r in rows]


async def test_segments_verified_in_page_order_and_two_quota_leases(app, client) -> None:
    from quickassist.infrastructure.openai import get_ai_provider

    spy = _Spy()
    app.dependency_overrides[get_ai_provider] = lambda: spy
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "segments" and data["warning"] is None and data["full_text"] is None
    texts = [i["text"] for i in data["items"]]
    assert texts and all("đất" in t for t in texts) and all(i["verified"] for i in data["items"])
    assert any("12/2023" in t for t in texts) and not any("13/2023" in t for t in texts)  # giáo dục
    ids = [i["id"] for i in data["items"]]
    assert ids == sorted(ids)  # thứ tự trang
    assert 0 < data["match_ratio"] < 0.6 and data["total_chars"] > 0 and data["truncated"] is False
    assert len(spy.embed_calls) == 1 and spy.embed_calls[0] == 1 + 8  # 1 batch: query + 8 khối
    assert spy.complete_calls == 1
    ops = await _ledger_ops()
    assert ("page_match_embed", "COMMITTED") in ops and ("page_match_verify", "COMMITTED") in ops
    q = (await client.get("/me/quota", headers=h)).json()
    assert q["used_tokens"] > 0 and q["reserved_tokens"] == 0


async def test_full_page_mode_returns_whole_page_text(client) -> None:
    html = "<html><body><article>" + "".join(
        f"<p>Đoạn {i}: quy định về đất đai, thu hồi đất đai và bồi thường đất đai cho người dân.</p>"
        for i in range(6)) + "</article></body></html>"
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body("đất đai", html), headers=h)
    data = r.json()
    assert r.status_code == 200 and data["mode"] == "full_page" and data["match_ratio"] >= 0.6
    assert data["full_text"] and data["full_text"].count("\n\n") == 5


async def test_no_candidate_returns_empty_without_calling_llm(app, client) -> None:
    from quickassist.infrastructure.openai import get_ai_provider

    spy = _Spy()
    app.dependency_overrides[get_ai_provider] = lambda: spy
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body("kubernetes pod helm chart"), headers=h)
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["mode"] == "segments"
    assert spy.complete_calls == 0


@pytest.mark.parametrize("failure", ["error", "garbage"])
async def test_verify_failure_falls_back_to_score_ranked_unverified(app, client, failure) -> None:  # type: ignore[no-untyped-def]
    from quickassist.infrastructure.openai import get_ai_provider

    class Flaky(MockAIClient):
        async def complete(self, messages, *, max_tokens):  # type: ignore[no-untyped-def,override]
            if failure == "error":
                raise AIProviderError("down", retryable=True)
            return CompletionResult("xin lỗi, tôi không thể {trả JSON", Usage(10, 5), "x")

    app.dependency_overrides[get_ai_provider] = lambda: Flaky(1536)
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    data = r.json()
    assert r.status_code == 200 and data["warning"] == "VERIFY_UNAVAILABLE"
    assert data["items"] and not any(i["verified"] for i in data["items"])
    ops = dict(await _ledger_ops())
    assert ops["page_match_verify"] == ("RELEASED" if failure == "error" else "COMMITTED")
    assert (await client.get("/me/quota", headers=h)).json()["reserved_tokens"] == 0


async def test_embed_failure_is_502_and_releases_quota(app, client) -> None:
    from quickassist.infrastructure.openai import get_ai_provider

    class Broken(MockAIClient):
        async def embed(self, texts):  # type: ignore[no-untyped-def,override]
            raise AIProviderError("down", retryable=True)

    app.dependency_overrides[get_ai_provider] = lambda: Broken(1536)
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    assert r.status_code == 502 and r.json()["error"]["code"] == "AI_UNAVAILABLE"
    q = (await client.get("/me/quota", headers=h)).json()
    assert q["used_tokens"] == 0 and q["reserved_tokens"] == 0


async def test_quota_exhausted_is_402(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "quota_default_tokens", 5)
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    assert r.status_code == 402 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"


async def test_html_over_cap_is_413_page_too_long(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "page_match_max_html_bytes", 1000)
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAGE_TOO_LONG"


async def test_page_without_main_content_is_422_page_no_content(client) -> None:
    h = await login(client)
    html = (FIXTURES / "blank.html").read_text(encoding="utf-8")
    r = await client.post("/ai/page-match", json=_body(html=html), headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PAGE_NO_CONTENT"


@pytest.mark.parametrize("body", [
    {"query": "", "html": "<p>x</p>"},
    {"query": "a" * 501, "html": "<p>x</p>"},
    {"query": "abc"},
    {"query": "abc", "html": "<p>x</p>", "la": 1},
])
async def test_validation_422(client, body) -> None:  # type: ignore[no-untyped-def]
    h = await login(client)
    r = await client.post("/ai/page-match", json=body, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_whitespace_query_is_422(client) -> None:
    h = await login(client)
    r = await client.post("/ai/page-match", json=_body("   "), headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PAGE_MATCH_QUERY_INVALID"


async def test_requires_auth(client) -> None:
    r = await client.post("/ai/page-match", json=_body())
    assert r.status_code == 401


async def test_rate_limited_after_6_per_minute(client) -> None:
    h = await login(client)
    for _ in range(6):
        assert (await client.post("/ai/page-match", json=_body(), headers=h)).status_code == 200
    r = await client.post("/ai/page-match", json=_body(), headers=h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


async def test_selected_segments_saved_as_one_note(client) -> None:
    h = await login(client)
    items = (await client.post("/ai/page-match", json=_body(), headers=h)).json()["items"]
    content = "\n\n".join(i["text"] for i in items)
    r = await client.post("/notes", json={"title": QUERY, "content": content,
                                          "url": "https://example.vn/nghi-quyet"},
                          headers=h | {"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201, r.text
    assert r.json()["content"] == content and r.json()["title"] == QUERY
