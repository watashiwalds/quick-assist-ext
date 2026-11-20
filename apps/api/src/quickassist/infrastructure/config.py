"""Infrastructure Layer — cấu hình tập trung (biến môi trường / .env).

Quy tắc: KHÔNG module nào được đọc os.environ trực tiếp. Thêm biến mới vào đây
và vào `infra/.env.example`.
"""

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlparse

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

    # --- Chế độ xác thực (ADR-0016) ---
    # google = Google OAuth như cũ; local = self-host một người, dev-login tự động,
    # KHÔNG có xác thực → bắt buộc bind 127.0.0.1 hoặc đặt sau proxy có auth.
    auth_mode: Literal["google", "local"] = "google"
    local_auth_email: str = "local@quickassist.local"

    # --- Google OAuth (server giữ client secret, extension chỉ giữ client id) ---
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    oauth_allowed_redirect_uris: Annotated[list[str], NoDecode] = Field(default_factory=list)
    enable_dev_login: bool = False  # CHỈ bật ở dev/test để test API không cần Google

    # --- AI provider ---
    ai_provider: Literal["mock", "openai", "gemini"] = "mock"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536  # PHẢI khớp cột vector trong migration
    chat_model: str = "gpt-4o-mini"
    # Gemini API (AI_PROVIDER=gemini): chat bằng Gemma 4, embedding bằng gemini-embedding-001
    gemini_api_key: SecretStr = SecretStr("")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    gemini_chat_model: str = "gemma-4-31b-it"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_thinking_level: str = "minimal"  # "" = không gửi thinkingConfig
    # Gemini/Gemma có thể mất hơn 30 giây cho một lượt tóm tắt; timeout ngắn sẽ
    # biến một yêu cầu hợp lệ thành AI_UNAVAILABLE/502 trên máy người dùng.
    ai_timeout_seconds: float = 90.0
    ai_max_retries: int = 2
    # --- BYOK per-user (ADR-0016) ---
    # Khoá mã hoá key của user; rỗng → derive HKDF từ jwt_secret (xoay jwt_secret khi
    # rỗng → key đã lưu không giải mã được, user phải nhập lại).
    ai_key_secret: SecretStr = SecretStr("")
    # Rỗng = cho phép mọi http(s) base_url; khác rỗng = chỉ chấp nhận URL khớp
    # scheme+host+port+path prefix (so theo biên segment, chặn userinfo — P5.S2).
    ai_base_url_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Kiểm tra chiều vector bắt buộc bằng embedding_dim (hành vi hiện tại);
    # BYOK override = False để cho phép zero-pad / từ chối ở CanonicalEmbeddingProvider.
    ai_embedding_strict_dim: bool = True
    # Gửi "dimensions" cho OpenAI-compatible (hành vi hiện tại); BYOK override = False
    # vì nhiều server local (Ollama/llama.cpp) không nhận tham số này.
    ai_request_embedding_dimensions: bool = True
    # Ngân sách token ước tính cho MỖI request embedding — batch theo cả số mục lẫn tổng token;
    # một request vượt giới hạn input của provider sẽ 400 (không retryable) và làm chết cả lần quét.
    ai_embed_batch_tokens: int = 16_000

    # --- Indexing / Search ---
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150
    chunking_strategy: Literal["v1", "v2"] = "v2"  # N04 — v2 chia theo câu tiếng Việt
    search_top_k: int = 5
    search_candidate_k: int = 30
    search_rerank_enabled: bool = False
    # Phase 1 — truy xuất source-first (UX plan §5.1): note đạt nếu
    # similarity >= ngưỡng cosine HOẶC RRF >= ngưỡng RRF (OR, không AND — giữ cả
    # khớp ngữ nghĩa lẫn khớp từ khoá; không dùng RRF một mình vì mất khớp diễn đạt lại).
    search_min_similarity: float = 0.5
    search_min_rrf: float = 0.03
    search_max_sources: int = 5  # top nguồn trả về cho cả Thư viện lẫn RAG
    search_notes_per_source: int = 10  # Thư viện hiển thị 3 + "Xem thêm" trên nền này
    # RAG: cố định 5 nguồn × rag_notes_per_source note/nguồn × 1 chunk tốt nhất/note.
    rag_notes_per_source: int = 3
    chat_context_max_chars: int = 18_000  # trần ký tự ngữ cảnh ghi chú đưa vào prompt chat

    # --- Quota & giới hạn ---
    quota_default_tokens: int = 1_000_000
    # CHỈ dev/test: quota vẫn được ghi nhận (ledger + used_tokens) nhưng không chặn AI;
    # rate limit theo user cũng tắt. APP_ENV=prod từ chối khởi động nếu bật.
    dev_unlimited: bool = False
    max_note_chars: int = 20_000
    max_summary_input_chars: int = 30_000

    # --- AutoChunk / Page Match (POST /ai/page-match, ADR-0013) ---
    page_match_max_html_bytes: int = 2_000_000  # HTML extension gửi lên — vượt → 413 PAGE_TOO_LONG
    page_match_extract_timeout_seconds: float = 10.0  # Trafilatura trong process pool
    page_match_max_chars: int = 50_000  # tổng ký tự khối sau khi trích (bound chi phí embed)
    page_match_max_block_chars: int = 1200  # khối dài hơn → tách theo câu
    # khối ngắn hơn → gộp với khối liền kề (chỉ nguồn text dán; 0 = tắt)
    page_match_min_block_chars: int = 400
    page_match_top_candidates: int = 15  # số ứng viên tối đa đưa LLM thẩm định
    page_match_min_score: float = 0.35  # ngưỡng cosine vào vòng thẩm định (candidate)
    page_match_full_page_ratio: float = 0.6  # match_ratio ≥ ngưỡng → mode "full_page"
    page_match_verify_max_output_tokens: int = 500
    page_match_verify_timeout_seconds: float = 20.0  # quá → trả theo điểm (VERIFY_UNAVAILABLE)
    # Phase 3 — quét toàn bộ: chia block thành lô để embed, timeout TỪNG LÔ (không phải cả trang),
    # một quota lease cho toàn bộ lần quét (commit tổng usage, release khi lỗi/huỷ).
    page_match_embed_batch_blocks: int = 32
    page_match_embed_timeout_seconds: float = 30.0
    # Ngưỡng cuối: LLM confidence ≥ mức này mới giữ đoạn. Fallback khi LLM lỗi dùng cosine ≥ mức này.
    page_match_min_confidence: float = 0.5
    page_match_fallback_min_similarity: float = 0.5

    # --- Giới hạn tần suất theo user (request/phút; 0 = tắt) — H02, R03 ---
    rate_limit_search_per_minute: int = 30
    rate_limit_ai_per_minute: int = 10
    rate_limit_write_per_minute: int = 120
    rate_limit_page_match_per_minute: int = 6
    rate_limit_ai_settings_test_per_minute: int = 6

    # --- Lưu trữ dữ liệu (SDS §3.2, RET-01) ---
    retention_inactive_days: int = 365

    # --- Worker ---
    worker_poll_interval_seconds: float = 1.0
    job_max_attempts: int = 5

    @field_validator("cors_origins", "oauth_allowed_redirect_uris", "ai_base_url_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("ai_base_url_allowlist")
    @classmethod
    def _valid_allowlist(cls, v: list[str]) -> list[str]:
        # Fail-fast khi khởi động: entry hỏng trong allowlist không được âm thầm bỏ qua
        # (nếu bỏ qua, URL đáng lẽ bị chặn lại được chấp nhận — SSRF).
        for entry in v:
            if not entry or "\\" in entry or any(ch.isspace() for ch in entry):
                raise ValueError(f"AI_BASE_URL_ALLOWLIST entry không hợp lệ: {entry}")
            u = urlparse(entry)
            if (u.scheme not in ("http", "https") or not u.hostname
                    or u.username is not None or u.password is not None
                    or u.query or u.fragment):
                raise ValueError(f"AI_BASE_URL_ALLOWLIST entry không hợp lệ: {entry}")
            try:
                u.port  # noqa: B018 — ép urlparse kiểm tra port
            except ValueError as e:
                raise ValueError(f"AI_BASE_URL_ALLOWLIST entry có port không hợp lệ: {entry}") from e
        return v

    @property
    def is_dev_login_allowed(self) -> bool:
        # AUTH_MODE=local: self-host một người, dev-login luôn được phép (ADR-0016).
        return self.auth_mode == "local" or (self.enable_dev_login and self.app_env in ("dev", "test"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
