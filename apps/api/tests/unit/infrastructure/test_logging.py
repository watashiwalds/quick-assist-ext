"""A07 — log JSON có request_id, che dữ liệu nhạy cảm (SDS §8)."""

import json
import logging

from quickassist.infrastructure.logging import JsonFormatter
from quickassist.infrastructure.request_context import reset_request_id, set_request_id


def _fmt(msg: str, **extra) -> dict:  # type: ignore[no-untyped-def]
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return json.loads(JsonFormatter().format(rec))


def test_request_id_is_attached() -> None:
    tok = set_request_id("rid-12345678")
    try:
        assert _fmt("evt")["request_id"] == "rid-12345678"
    finally:
        reset_request_id(tok)


def test_sensitive_keys_are_redacted_recursively() -> None:
    out = _fmt("evt", content="ghi chú bí mật", refresh_token="r", note_id="n1",
               payload={"text": "x", "nested": {"access_token": "y", "ok": 1}}, items=[{"query": "q"}])
    assert out["content"] == out["refresh_token"] == "***"
    assert out["note_id"] == "n1"
    assert out["payload"]["text"] == "***" and out["payload"]["nested"]["access_token"] == "***"
    assert out["payload"]["nested"]["ok"] == 1 and out["items"][0]["query"] == "***"


def test_secret_patterns_scrubbed_from_message_and_values() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
    out = _fmt(f"failed with Bearer abcdefghijkl and {jwt}", err="key sk-abcdefghijklmnopqrstuv")
    assert "abcdefghijkl" not in out["event"] and "eyJ" not in out["event"]
    assert "sk-abc" not in out["err"]


def test_exception_is_logged_without_secrets() -> None:
    try:
        raise ValueError("Bearer supersecrettoken123")
    except ValueError:
        import sys

        rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", (), sys.exc_info())
    out = json.loads(JsonFormatter().format(rec))
    assert out["exc_type"] == "ValueError" and "supersecret" not in out["exc"]
