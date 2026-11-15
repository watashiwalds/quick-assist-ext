"""Presentation Layer — DTO request/response (AI settings per-user, ADR-0016 §5).

Response KHÔNG BAO GIỜ chứa key (chỉ `has_key` + `key_hint` 4 ký tự cuối).
"""

from typing import Literal

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel

AiProvider = Literal["openai", "gemini"]


class ServerDefaultOut(ApiModel):
    """Cấu hình AI toàn cục của server (mode=inherit sẽ dùng cái này)."""

    provider: Literal["openai", "gemini", "mock"]
    chat_model: str
    embedding_model: str


class AIRebuildOut(ApiModel):
    """Thông tin rebuild chỉ mục khi fingerprint embedding đổi (wire đầy đủ ở P3)."""

    required: bool
    notes: int


class AISettingsOut(ApiModel):
    mode: Literal["inherit", "byok"]
    provider: AiProvider | None = None
    base_url: str | None = None
    has_key: bool = False
    key_hint: str | None = None  # 4 ký tự cuối, hiển thị dạng "…a1b2"
    chat_model: str | None = None
    embedding_model: str | None = None
    timeout_seconds: float | None = None
    rebuild_note_count: int = 0  # số note sẽ dựng lại nếu đổi embedding config (tính thật ở P3)
    server_default: ServerDefaultOut
    rebuild: AIRebuildOut | None = None  # chỉ PUT/DELETE trả khi fingerprint đổi (P3)


class AISettingsIn(ApiModel):
    """PUT /me/ai-settings. `api_key`: null = giữ key đã lưu, "" = xoá key (model local)."""

    mode: Literal["inherit", "byok"]
    provider: AiProvider | None = None
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    chat_model: str | None = Field(default=None, max_length=100)
    embedding_model: str | None = Field(default=None, max_length=100)
    timeout_seconds: float | None = Field(default=None, ge=5, le=600)


class AISTestIn(ApiModel):
    """POST /me/ai-settings/test — giống PUT nhưng không có `mode`; thiếu api_key → dùng key đã lưu."""

    provider: AiProvider | None = None
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    chat_model: str | None = Field(default=None, max_length=100)
    embedding_model: str | None = Field(default=None, max_length=100)
    timeout_seconds: float | None = Field(default=None, ge=5, le=600)


class EmbeddingTestOut(ApiModel):
    model: str
    dim: int  # số chiều NATIVE của model (trước khi pad về 1536)
    padded: bool = False  # dim < 1536 → sẽ được zero-pad khi lưu
    latency_ms: int


class ChatTestOut(ApiModel):
    model: str
    latency_ms: int
    sample: str


class AISTestOut(ApiModel):
    ok: bool
    embedding: EmbeddingTestOut | None = None
    chat: ChatTestOut | None = None
    stage: Literal["embedding", "chat"] | None = None  # stage lỗi khi ok=false
    code: str | None = None
    message: str | None = None
