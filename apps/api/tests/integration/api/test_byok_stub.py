"""Integration P5.S6 — BYOK end-to-end với stub server OpenAI-compat thật (ThreadingHTTPServer).

Chứng minh (tiêu chí P5 #2, không monkeypatch internals — đi qua đúng httpx + adapter):
summary / search / RAG chat / page-match / indexing đều dùng đúng base_url + Authorization
của user; vector 768 được pad 1536; xoay key KHÔNG rebuild; response không lộ key.

Cần PostgreSQL + pgvector (TEST_DATABASE_URL) — không có thì tự skip.
"""

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import text

from quickassist.data.database import get_sessionmaker
from quickassist.infrastructure.jobs import drain
from tests.conftest import login

pytestmark = pytest.mark.integration

DIM = 768


def _vec(text_: str) -> list[float]:
    v = [0.0] * DIM
    for token in text_.lower().split():
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIM
        v[idx] += 1.0
    norm = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norm for x in v]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # đóng connection sau mỗi response → SSE không bị treo

    def log_message(self, *args):  # type: ignore[no-untyped-def]  # im lặng
        pass

    def do_POST(self):  # noqa: N802 — API của http.server
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        self.server.seen.append({  # type: ignore[attr-defined]
            "path": self.path,
            "auth": self.headers.get("authorization"),
            "body": body,
        })
        if self.path.endswith("/embeddings"):
            inputs = body["input"]
            self._json({
                "data": [{"index": i, "embedding": _vec(t if isinstance(t, str) else " ".join(t))}
                         for i, t in enumerate(inputs)],
                "model": body["model"],
                "usage": {"prompt_tokens": sum(len(str(t)) for t in inputs) // 4},
            })
        elif self.path.endswith("/chat/completions"):
            if body.get("stream"):
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                for part in ("Đây ", "là ", "câu trả lời."):
                    self.wfile.write(
                        f"data: {json.dumps({'choices': [{'delta': {'content': part}}]})}\n\n".encode()
                    )
                self.wfile.write((
                    "data: " + json.dumps({
                        "choices": [],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }) + "\n\n"
                ).encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self._json({
                    "choices": [{"message": {"content": "Tóm tắt từ stub."}}],
                    "model": body["model"],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                })
        else:
            self.send_error(404)

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def stub():  # type: ignore[no-untyped-def]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.seen = []  # type: ignore[attr-defined]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv, f"http://127.0.0.1:{srv.server_port}/v1"
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


async def _vector_dims(chunk_user: str) -> list[int]:
    async with get_sessionmaker()() as s:
        rows = await s.execute(text(
            "SELECT vector_dims(embedding) FROM note_chunks WHERE user_id = :u"), {"u": chunk_user})
        return [r[0] for r in rows]


async def _note_status(note_id: str) -> str:
    async with get_sessionmaker()() as s:
        return (await s.execute(text(
            "SELECT index_status FROM notes WHERE id = :i"), {"i": note_id})).scalar_one()


def parse_sse(body: str) -> list[tuple[str, object]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def test_byok_summary_search_rag_page_match_indexing_with_stub(client, stub) -> None:  # type: ignore[no-untyped-def]
    srv, base_url = stub
    h = await login(client, "byok-stub@test.local")
    uid = (await client.get("/me", headers=h)).json()["id"]

    # 1-2) Note index bằng provider server (mock) — baseline.
    r = await client.post("/notes", headers=h,
                          json={"content": "Phở bò Hà Nội hầm xương 8 tiếng với quế hồi.",
                                "title": "Phở bò", "url": "https://amthuc.example/pho"})
    note_id = r.json()["id"]
    await drain()
    assert await _note_status(note_id) == "READY"

    # 3) Lưu BYOK trỏ vào stub → fingerprint đổi → rebuild.
    cfg = {"mode": "byok", "provider": "openai", "base_url": base_url, "api_key": "sk-test-1",
           "chat_model": "stub-chat", "embedding_model": "stub-embed", "timeout_seconds": 30}
    r = await client.put("/me/ai-settings", json=cfg, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["rebuild"] == {"required": True, "notes": 1}
    assert await _note_status(note_id) == "PROCESSING"

    # 4) Drain: index lại bằng stub — đúng key, đúng base_url, không gửi `dimensions`,
    #    vector 768 được zero-pad về 1536.
    await drain()
    assert await _note_status(note_id) == "READY"
    emb_calls = [c for c in srv.seen if c["path"].endswith("/embeddings")]
    assert emb_calls and emb_calls[0]["auth"] == "Bearer sk-test-1"
    assert "dimensions" not in emb_calls[0]["body"]
    dims = await _vector_dims(uid)
    assert dims and all(d == 1536 for d in dims)  # 768 → pad 1536

    # 5) Search ngữ nghĩa dùng stub embed cho query.
    r = await client.post("/search", json={"query": "nấu phở"}, headers=h)
    assert r.status_code == 200 and len(r.json()["items"]) > 0, r.text
    assert any(c["path"].endswith("/embeddings") for c in srv.seen)

    # 6) Summary dùng stub chat.
    r = await client.post("/ai/summaries", json={"text": "Phở là món ăn nổi tiếng của Hà Nội. " * 5},
                          headers=h)
    assert r.status_code == 200 and r.json()["summary"] == "Tóm tắt từ stub.", r.text
    assert any(c["path"].endswith("/chat/completions") for c in srv.seen)

    # 7) RAG chat SSE qua stub stream.
    r = await client.post("/ai/chat", json={"question": "nấu phở thế nào?"}, headers=h)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "sources" and names[-1] == "done" and "delta" in names
    assert "Đây là câu trả lời." == "".join(d["text"] for e, d in events if e == "delta")  # type: ignore[index]

    # 8) Page-match (text) → embed + chat verify qua stub.
    pm_text = "Công thức phở bò: hầm xương, quế hồi. " * 8
    r = await client.post("/ai/page-match", json={"query": "công thức phở", "text": pm_text},
                          headers=h)
    assert r.status_code == 200, r.text

    # 9) Xoay key: cùng config, key mới → KHÔNG rebuild, request mới dùng key mới.
    srv.seen.clear()
    r = await client.put("/me/ai-settings", json={**cfg, "api_key": "sk-test-2"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["rebuild"] is None  # đổi key không đổi fingerprint
    assert await _note_status(note_id) == "READY"
    r = await client.post("/search", json={"query": "phở"}, headers=h)
    assert r.status_code == 200
    emb_calls = [c for c in srv.seen if c["path"].endswith("/embeddings")]
    assert emb_calls and emb_calls[-1]["auth"] == "Bearer sk-test-2"

    # 10) Response KHÔNG bao giờ chứa key.
    r = await client.get("/me/ai-settings", headers=h)
    body = r.text
    assert "sk-test-" not in body
    assert r.json()["has_key"] is True and r.json()["key_hint"] == "…st-2"
