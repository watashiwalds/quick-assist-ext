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
from quickassist.presentation.api.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from quickassist.presentation.api.v1.router import api_v1


def _check_config() -> None:
    s = get_settings()
    if s.embedding_dim != EMBEDDING_DIM:
        raise RuntimeError(f"EMBEDDING_DIM={s.embedding_dim} lệch cột vector({EMBEDDING_DIM})")
    if s.app_env == "prod" and (s.jwt_secret.get_secret_value() == "change-me-in-env" or s.enable_dev_login):
        raise RuntimeError("Cấu hình prod không an toàn (JWT_SECRET / ENABLE_DEV_LOGIN)")


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
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,  # chrome-extension://<EXTENSION_ID>
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    register_error_handlers(app)
    app.include_router(api_v1, prefix=s.api_prefix)
    return app


app = create_app()
