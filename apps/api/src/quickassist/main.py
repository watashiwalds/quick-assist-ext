"""Composition root của tiến trình API — nơi DUY NHẤT lắp các tầng lại với nhau.
Chạy: uvicorn quickassist.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import quickassist.data.models  # noqa: F401 — đăng ký entity
from quickassist.data.database import dispose_engine
from quickassist.data.models import EMBEDDING_DIM
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import configure_logging
from quickassist.presentation.api.error_handlers import register_error_handlers
from quickassist.presentation.api.middleware import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from quickassist.presentation.api.v1.router import api_v1


def _check_config() -> None:
    s = get_settings()
    if s.embedding_dim != EMBEDDING_DIM:
        raise RuntimeError(f"EMBEDDING_DIM={s.embedding_dim} lệch cột vector({EMBEDDING_DIM})")
    if s.ai_provider == "openai" and not s.openai_api_key.get_secret_value():
        raise RuntimeError("AI_PROVIDER=openai nhưng thiếu OPENAI_API_KEY")
    if s.ai_provider == "gemini" and not s.gemini_api_key.get_secret_value():
        raise RuntimeError("AI_PROVIDER=gemini nhưng thiếu GEMINI_API_KEY")
    if s.app_env == "prod":
        problems = []
        if s.jwt_secret.get_secret_value() == "change-me-in-env" or len(s.jwt_secret.get_secret_value()) < 32:
            problems.append("JWT_SECRET yếu/mặc định")
        if s.enable_dev_login:
            problems.append("ENABLE_DEV_LOGIN phải tắt")
        if any(o == "*" or not o.startswith("chrome-extension://") for o in s.cors_origins):
            problems.append("CORS_ORIGINS chỉ được chứa chrome-extension://<ID>")
        if problems:
            raise RuntimeError("Cấu hình prod không an toàn: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _check_config()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level)
    app = FastAPI(
        title="QuickAssist API", version="0.1.0", lifespan=lifespan,
        docs_url=None if s.app_env == "prod" else "/docs",
        openapi_url=f"{s.api_prefix}/openapi.json",
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=s.app_env == "prod")
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,  # chrome-extension://<EXTENSION_ID> — không bao giờ "*"
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
        max_age=600,
    )
    register_error_handlers(app)
    app.include_router(api_v1, prefix=s.api_prefix)
    return app


app = create_app()
