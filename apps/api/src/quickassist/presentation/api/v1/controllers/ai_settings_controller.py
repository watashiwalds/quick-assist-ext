"""API Controller — cấu hình AI per-user (BYOK, ADR-0016 §5). Response không bao giờ chứa key.

Rebuild orchestration: controller nối AISettingsService (đổi fingerprint) với
semantic_search.start_rebuild (xoá/thay chunk + enqueue) — service KHÔNG import chéo nhau
 vì indexing_job đã phụ thuộc AISettingsService (test L3 cấm phụ thuộc vòng).
"""

from fastapi import APIRouter, Depends

from quickassist.business.ai_settings import AISettingsInput, AISettingsService, AISettingsState
from quickassist.business.notes import count_active_notes
from quickassist.business.semantic_search import start_rebuild
from quickassist.infrastructure.config import get_settings
from quickassist.presentation.api.deps import CurrentUserId, DbSession, rate_limit
from quickassist.presentation.schemas.ai_settings import (
    AIRebuildOut,
    AISettingsIn,
    AISettingsOut,
    AISTestIn,
    AISTestOut,
    ChatTestOut,
    EmbeddingTestOut,
    ServerDefaultOut,
)

router = APIRouter(prefix="/me/ai-settings", tags=["ai-settings"])


def _server_default() -> ServerDefaultOut:
    s = get_settings()
    if s.ai_provider == "gemini":
        return ServerDefaultOut(provider=s.ai_provider, chat_model=s.gemini_chat_model,
                                embedding_model=s.gemini_embedding_model)
    return ServerDefaultOut(provider=s.ai_provider, chat_model=s.chat_model,
                            embedding_model=s.embedding_model)


def _out(st: AISettingsState, *, rebuild_note_count: int = 0,
         rebuild: AIRebuildOut | None = None) -> AISettingsOut:
    return AISettingsOut(
        mode=st.mode, provider=st.provider, base_url=st.base_url, has_key=st.has_key,
        key_hint=f"…{st.key_hint}" if st.key_hint else None,
        chat_model=st.chat_model, embedding_model=st.embedding_model,
        timeout_seconds=st.timeout_seconds, rebuild_note_count=rebuild_note_count,
        server_default=_server_default(), rebuild=rebuild,
    )


@router.get("", response_model=AISettingsOut)
async def get_ai_settings(user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    st = await AISettingsService(session).get(user_id)
    return _out(st, rebuild_note_count=await count_active_notes(session, user_id))


@router.put("", response_model=AISettingsOut,
            responses={400: {"description": "Cấu hình không hợp lệ (AI_CONFIG_INVALID)"}})
async def put_ai_settings(body: AISettingsIn, user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    """Lưu cấu hình. api_key: null = giữ key cũ, "" = xoá key. Fingerprint embedding đổi →
    tự động rebuild chỉ mục (notes PROCESSING, job index lại từng note) và trả `rebuild`."""
    saved = await AISettingsService(session).save(user_id, AISettingsInput(**body.model_dump()))
    rebuild: AIRebuildOut | None = None
    if saved.rebuild_required:
        plan = await start_rebuild(session, user_id, fingerprint=saved.fingerprint)
        rebuild = AIRebuildOut(required=True, notes=plan.notes)
    count = await count_active_notes(session, user_id)
    return _out(saved.state, rebuild_note_count=count, rebuild=rebuild)


@router.delete("", response_model=AISettingsOut)
async def delete_ai_settings(user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    """Quay về dùng cấu hình server (mode=inherit); key bị xoá khỏi DB. Fingerprint đổi → rebuild."""
    saved = await AISettingsService(session).delete(user_id)
    rebuild: AIRebuildOut | None = None
    if saved.rebuild_required:
        plan = await start_rebuild(session, user_id, fingerprint=saved.fingerprint)
        rebuild = AIRebuildOut(required=True, notes=plan.notes)
    count = await count_active_notes(session, user_id)
    return _out(saved.state, rebuild_note_count=count, rebuild=rebuild)


@router.post("/test", response_model=AISTestOut,
             dependencies=[Depends(rate_limit("ai_settings_test",
                                              "rate_limit_ai_settings_test_per_minute"))],
             responses={429: {"description": "Quá tần suất (Retry-After)"}})
async def test_ai_settings(body: AISTestIn, user_id: CurrentUserId, session: DbSession) -> AISTestOut:
    """Kiểm tra kết nối embed + chat (timeout 30s, không retry). Không bắt buộc trước khi lưu."""
    r = await AISettingsService(session).test_connection(
        user_id, AISettingsInput(mode="byok", **body.model_dump()))
    return AISTestOut(
        ok=r.ok,
        embedding_dim=r.embedding_dim,
        embedding=EmbeddingTestOut(**r.embedding) if r.embedding else None,
        chat=ChatTestOut(**r.chat) if r.chat else None,
        stage=r.stage, code=r.code, message=r.message,
    )
