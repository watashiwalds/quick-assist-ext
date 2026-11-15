"""API Controller — cấu hình AI per-user (BYOK, ADR-0016 §5). Response không bao giờ chứa key."""

from fastapi import APIRouter, Depends

from quickassist.business.ai_settings import (
    AISettingsInput,
    AISettingsService,
    AISettingsState,
    AITestResult,
)
from quickassist.infrastructure.config import get_settings
from quickassist.presentation.api.deps import CurrentUserId, DbSession, rate_limit
from quickassist.presentation.schemas.ai_settings import (
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


def _out(st: AISettingsState) -> AISettingsOut:
    return AISettingsOut(
        mode=st.mode, provider=st.provider, base_url=st.base_url, has_key=st.has_key,
        key_hint=f"…{st.key_hint}" if st.key_hint else None,
        chat_model=st.chat_model, embedding_model=st.embedding_model,
        timeout_seconds=st.timeout_seconds, rebuild_note_count=st.rebuild_note_count,
        server_default=_server_default(),
    )


@router.get("", response_model=AISettingsOut)
async def get_ai_settings(user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    return _out(await AISettingsService(session).get(user_id))


@router.put("", response_model=AISettingsOut,
            responses={400: {"description": "Cấu hình không hợp lệ (AI_CONFIG_INVALID)"}})
async def put_ai_settings(body: AISettingsIn, user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    """Lưu cấu hình. api_key: null = giữ key cũ, "" = xoá key. Rebuild response wire ở P3."""
    return _out(await AISettingsService(session).save(user_id, AISettingsInput(**body.model_dump())))


@router.delete("", response_model=AISettingsOut)
async def delete_ai_settings(user_id: CurrentUserId, session: DbSession) -> AISettingsOut:
    """Quay về dùng cấu hình server (mode=inherit); key bị xoá khỏi DB."""
    return _out(await AISettingsService(session).delete(user_id))


@router.post("/test", response_model=AISTestOut,
             dependencies=[Depends(rate_limit("ai_settings_test",
                                              "rate_limit_ai_settings_test_per_minute"))],
             responses={429: {"description": "Quá tần suất (Retry-After)"}})
async def test_ai_settings(body: AISTestIn, user_id: CurrentUserId, session: DbSession) -> AISTestOut:
    """Kiểm tra kết nối embed + chat (timeout 30s, không retry). Không bắt buộc trước khi lưu."""
    r: AITestResult = await AISettingsService(session).test_connection(
        user_id, AISettingsInput(mode="byok", **body.model_dump()))
    return AISTestOut(
        ok=r.ok,
        embedding=EmbeddingTestOut(**r.embedding) if r.embedding else None,
        chat=ChatTestOut(**r.chat) if r.chat else None,
        stage=r.stage, code=r.code, message=r.message,
    )
