"""Business Layer — lỗi nghiệp vụ.

Service ném AppError (hoặc lớp con) với `code` ổn định (vd NOTE_NOT_FOUND).
Business Layer KHÔNG biết HTTP: việc đổi lỗi → HTTP response nằm ở
presentation/api/error_handlers.py. `status_code` dưới đây chỉ là gợi ý ánh xạ.
"""

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(
        self,
        message: str = "",
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        if code:
            self.code = code
        self.details = details or {}


class Unauthorized(AppError):
    status_code, code = 401, "UNAUTHORIZED"


class Forbidden(AppError):
    status_code, code = 403, "FORBIDDEN"


class NotFound(AppError):
    """Dùng cả khi tài nguyên thuộc user khác — không lộ sự tồn tại (chống IDOR)."""

    status_code, code = 404, "NOT_FOUND"


class Conflict(AppError):
    status_code, code = 409, "CONFLICT"


class QuotaExceeded(AppError):
    status_code, code = 402, "QUOTA_EXCEEDED"


class PayloadTooLarge(AppError):
    status_code, code = 413, "PAYLOAD_TOO_LARGE"


class UpstreamError(AppError):
    """Lỗi từ dịch vụ ngoài (OpenAI, Google)."""

    status_code, code = 502, "UPSTREAM_ERROR"


class NotImplementedYet(AppError):
    status_code, code = 501, "NOT_IMPLEMENTED"
