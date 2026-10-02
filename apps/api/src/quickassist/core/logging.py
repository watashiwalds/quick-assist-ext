"""Logging JSON một dòng, tự gắn request_id, tự che dữ liệu nhạy cảm.

Quy tắc (SDS §8): KHÔNG log token, API key, nội dung ghi chú/trang web.
Chỉ log id, độ dài, mã lỗi, thời gian xử lý.
"""

import json
import logging
import sys
from typing import Any

SENSITIVE_KEYS = {
    "authorization", "access_token", "refresh_token", "id_token", "code", "code_verifier",
    "password", "api_key", "openai_api_key", "content", "text", "query", "secret",
}
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def _redact(key: str, value: Any) -> Any:
    return "***" if key.lower() in SENSITIVE_KEYS else value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from quickassist.core.request_context import get_request_id

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": get_request_id(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = _redact(k, v)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc"] = self.formatException(record.exc_info)
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
