"""Error contract thống nhất cho toàn API.

Mọi lỗi trả về dạng:
    {"error": {"code": "NOTE_NOT_FOUND", "message": "...", "details": {...}, "request_id": "..."}}

Service ném AppError (hoặc lớp con); KHÔNG ném HTTPException từ service.
`code` là hằng số ổn định để extension map sang thông báo UI.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from quickassist.core.logging import get_logger
from quickassist.core.request_context import get_request_id

log = get_logger(__name__)


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


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": get_request_id(),
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.warning("app_error", extra={"error_code": exc.code, "status": exc.status_code})
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Dữ liệu không hợp lệ", {"errors": errors}),
                            status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Không trả stacktrace/chi tiết nội bộ cho client.
        log.exception("unhandled_error")
        return JSONResponse(_body("INTERNAL_ERROR", "Lỗi hệ thống"), status_code=500)
