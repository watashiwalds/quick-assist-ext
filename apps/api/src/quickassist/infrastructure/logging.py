"""Infrastructure Layer — LoggingService (SDS Hình 1).

Log JSON một dòng, gắn request_id, che dữ liệu nhạy cảm.

Quy tắc (SDS §8): KHÔNG log token, API key, nội dung ghi chú/trang web.
Chỉ log id, độ dài, mã lỗi, thời gian xử lý.
"""

import json
import logging
import re
import sys
from typing import Any

SENSITIVE_KEYS = {
    "authorization", "access_token", "refresh_token", "id_token", "code", "code_verifier",
    "password", "api_key", "openai_api_key", "gemini_api_key", "x-goog-api-key",
    "content", "text", "query", "secret",
    "client_secret", "jwt_secret", "cookie", "summary", "summary_text", "prompt", "messages",
}
# Mẫu chuỗi trông như bí mật (Bearer token, JWT, khoá OpenAI) — che kể cả khi lọt vào message.
_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}"),  # JWT
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),  # OpenAI API key
)
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def _scrub(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("***", text)
    return text


def _redact(key: str, value: Any, depth: int = 0) -> Any:
    """Che theo TÊN khoá (đệ quy vào dict/list) và theo MẪU chuỗi bí mật."""
    if key.lower() in SENSITIVE_KEYS:
        return "***"
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {k: _redact(str(k), v, depth + 1) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact("", v, depth + 1) for v in value]
    if isinstance(value, str):
        return _scrub(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from quickassist.infrastructure.request_context import get_request_id

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": _scrub(record.getMessage()),
            "request_id": get_request_id(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = _redact(k, v)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc"] = _scrub(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
