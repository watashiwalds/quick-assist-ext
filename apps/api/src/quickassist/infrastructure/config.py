"""Infrastructure Layer — cấu hình tập trung (biến môi trường / .env).

Quy tắc: KHÔNG module nào được đọc os.environ trực tiếp. Thêm biến mới vào đây
và vào `infra/.env.example`.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist"
    db_pool_size: int = 5

    # --- App session (JWT access token + refresh token xoay vòng) ---
    jwt_secret: SecretStr = SecretStr("change-me-in-env")
    jwt_issuer: str = "quickassist"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30

    # --- Google OAuth (server giữ client secret, extension chỉ giữ client id) ---
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    oauth_allowed_redirect_uris: Annotated[list[str], NoDecode] = Field(default_factory=list)
    enable_dev_login: bool = False  # CHỈ bật ở dev/test để test API không cần Google

    # --- AI provider ---
    ai_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536  # PHẢI khớp cột vector trong migration
    chat_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 2

    # --- Indexing / Search ---
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150
    search_top_k: int = 5
    search_candidate_k: int = 30
    search_rerank_enabled: bool = False

    # --- Quota & giới hạn ---
    quota_default_tokens: int = 200_000
    max_note_chars: int = 20_000
    max_summary_input_chars: int = 30_000

    # --- Worker ---
    worker_poll_interval_seconds: float = 1.0
    job_max_attempts: int = 5

    @field_validator("cors_origins", "oauth_allowed_redirect_uris", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def is_dev_login_allowed(self) -> bool:
        return self.enable_dev_login and self.app_env in ("dev", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
