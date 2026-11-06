"""Presentation Layer — middleware HTTP:
- `RequestIdMiddleware`: gắn X-Request-ID cho mọi request/response + log truy cập (A07).
- `SecurityHeadersMiddleware`: header bảo mật cho mọi response (H02).
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.request_context import reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
log = get_logger("quickassist.access")


def _route_template(request: Request) -> str:
    """Đường dẫn dạng mẫu (/api/v1/notes/{note_id}) — không log id cụ thể / query string."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.isascii() and incoming.isprintable() \
            else uuid.uuid4().hex
        token = set_request_id(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            # Log truy cập: method, route, status, thời gian — KHÔNG body, header, query (SDS §8).
            if not request.url.path.endswith(("/health/live", "/health/ready")):
                log.info("http_request", extra={
                    "method": request.method, "route": _route_template(request), "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                })
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, hsts: bool) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if not request.url.path.endswith(("/docs", "/openapi.json")):
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        h.setdefault("Cache-Control", "no-store")  # dữ liệu cá nhân — không cache ở proxy
        if self.hsts:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
