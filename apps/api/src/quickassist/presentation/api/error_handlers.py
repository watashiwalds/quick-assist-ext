"""Presentation Layer — đổi lỗi nghiệp vụ → HTTP response theo error contract:

    {"error": {"code": "NOTE_NOT_FOUND", "message": "...", "details": {...}, "request_id": "..."}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from quickassist.business.common.exceptions import AppError
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.request_context import get_request_id

log = get_logger(__name__)


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {},
                      "request_id": get_request_id()}}


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
        log.exception("unhandled_error")  # không trả stacktrace cho client
        return JSONResponse(_body("INTERNAL_ERROR", "Lỗi hệ thống"), status_code=500)
