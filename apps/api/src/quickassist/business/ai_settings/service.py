"""Business Layer — AI Settings Service: cấu hình AI theo từng user (BYOK, ADR-0016).

- `provider_for(user_id)`: resolver cho API dependency và indexing worker (P1).
- `get/save/delete`: CRUD cấu hình + validate (§5). Key chỉ vào DB dưới dạng ciphertext
  AES-GCM; response KHÔNG bao giờ chứa key.
- `test_connection`: kiểm tra kết nối embed+complete với timeout ngắn (§4.9).
- `is_byok`: quota dùng để cho phép reset usage (D6).
- Rebuild chỉ mục khi fingerprint đổi: orchestration ở P3.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.exceptions import InvalidTag
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError
from quickassist.data.models.user_ai_settings import UserAISettings
from quickassist.data_access.repositories.user_ai_settings_repository import UserAISettingsRepository
from quickassist.infrastructure import ai_keys
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.openai import (
    UserProviderConfig,
    build_raw_provider,
    get_ai_provider,
    provider_cache,
)
from quickassist.infrastructure.openai.base import AIProvider, AIProviderError, ChatMessage
from quickassist.infrastructure.openai.dimensions import CANONICAL_DIM

_TIMEOUT_RANGE = (5.0, 600.0)

# Test kết nối: timeout ngắn cố định, không retry → phản hồi nhanh cho UI (§4.9).
_TEST_TIMEOUT_SECONDS = 30.0
_TEST_EMBED_TEXT = "Hà Nội là thủ đô của Việt Nam."
_TEST_CHAT = [ChatMessage("system", "Bạn trả lời cực ngắn gọn."),
              ChatMessage("user", "Thủ đô của Việt Nam là gì? Trả lời đúng một từ.")]


@dataclass(frozen=True)
class AITestResult:
    ok: bool
    embedding_dim: int | None = None  # số chiều native đo được (kể cả khi >1536)
    embedding: dict[str, object] | None = None  # {model, dim, padded, latency_ms}
    chat: dict[str, object] | None = None       # {model, latency_ms, sample}
    stage: str | None = None
    code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class AISettingsInput:
    """Input của save() — controller truyền từ AISettingsIn.model_dump()."""

    mode: str
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # None = giữ key cũ; "" = xoá key; khác rỗng = thay key
    chat_model: str | None = None
    embedding_model: str | None = None
    embedding_dim: int | None = None  # advisory từ client; >1536 → từ chối sớm (§5.2)
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class AISettingsState:
    """Trạng thái cấu hình để controller dựng response (không bao giờ chứa key)."""

    mode: str
    provider: str | None
    base_url: str | None
    has_key: bool
    key_hint: str | None
    chat_model: str | None
    embedding_model: str | None
    timeout_seconds: float | None


@dataclass(frozen=True)
class SaveResult:
    """Kết quả save/delete: state + fingerprint hiện hành + có cần rebuild không (ADR-0016 §4.6).

    rebuild_required=True → controller gọi semantic_search.start_rebuild() (service này
    KHÔNG import semantic_search — tránh phụ thuộc vòng vì indexing_job dùng AISettingsService).

    rebuild_required dựa trên `applied_fingerprint` (fingerprint đã được bàn giao cho
    pipeline rebuild) thay vì so fingerprint cũ/mới: save B đã commit nhưng start_rebuild(A)
    chưa chạy (crash) → re-save cùng config vẫn phải rebuild (P5 §7)."""

    state: AISettingsState
    fingerprint: str
    rebuild_required: bool


def _rebuild_required(row: UserAISettings | None, new_mode: str, new_fp: str) -> bool:
    """Có cần rebuild chỉ mục sau khi lưu `new_mode` với fingerprint `new_fp` không (P5 §7.2).

    - Chưa có row: byok → True (chunk đang theo cấu hình server); inherit → False.
    - Row cũ chưa từng theo dõi fingerprint (row legacy trước P5): inherit → False (chunk
      vốn theo server); byok → True.
    - Còn lại: so với `applied_fingerprint` — NULL cũng tính là khác (lần save trước chưa
      kịp enqueue, crash giữa 2 commit)."""
    if row is None or row.embedding_fingerprint is None:
        return new_mode == "byok"
    return row.applied_fingerprint != new_fp


def embedding_fingerprint(provider: str, base_url: str, embedding_model: str) -> str:
    """sha256(provider|base_url|model) — ĐỔI KEY hoặc CHAT MODEL KHÔNG đổi fingerprint
    → không rebuild. Đổi embedding model / base_url / provider → rebuild (P3 dùng)."""
    raw = f"{provider}|{base_url.rstrip('/')}|{embedding_model}"
    return hashlib.sha256(raw.encode()).hexdigest()


def server_embedding_fingerprint() -> str:
    """Fingerprint của cấu hình TOÀN CỤC server — hiện hành khi mode=inherit."""
    s = get_settings()
    if s.ai_provider == "gemini":
        return embedding_fingerprint("gemini", s.gemini_base_url, s.gemini_embedding_model)
    if s.ai_provider == "openai":
        return embedding_fingerprint("openai", s.openai_base_url, s.embedding_model)
    return embedding_fingerprint("mock", "mock://server", "mock-embed")


def _invalid(message: str) -> AppError:
    return AppError(message, code="AI_CONFIG_INVALID")


def _parse_http_url(value: str, *, field: str = "base_url") -> tuple[str, str, int, str]:
    """Chuẩn hoá URL thành (scheme, host, port, path) — chặn userinfo/query/fragment/port lỗi.

    Host mới là ranh giới SSRF: so khớp theo (scheme, host, port), path chỉ là ràng buộc
    cấu hình theo biên segment (không chuẩn hoá percent-encoding/dot-segment — §4.5 ADR).
    """
    value = value.strip()
    if not value or "\\" in value or any(ch.isspace() for ch in value):
        raise _invalid(f"{field} không hợp lệ")
    u = urlparse(value)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise _invalid(f"{field} phải là URL http/https hợp lệ")
    if u.username is not None or u.password is not None:
        raise _invalid(f"{field} không được chứa thông tin đăng nhập")
    if u.query or u.fragment:
        raise _invalid(f"{field} không được chứa query/fragment")
    try:
        port = u.port
    except ValueError as e:
        raise _invalid(f"{field} có port không hợp lệ") from e
    default_port = 443 if u.scheme == "https" else 80
    return u.scheme, u.hostname.lower(), port or default_port, u.path.rstrip("/")


def _allowlist_match(base: tuple[str, str, int, str], entry: str) -> bool:
    try:
        a = _parse_http_url(entry, field="AI_BASE_URL_ALLOWLIST")
    except AppError:
        return False  # validator của Settings đã chặn entry hỏng khi khởi động
    if base[:3] != a[:3]:
        return False
    a_path = a[3]
    return not a_path or base[3] == a_path or base[3].startswith(a_path + "/")


def validate_base_url(base_url: str | None) -> str:
    """Bắt buộc http/https, host không rỗng; allowlist khác rỗng → khớp scheme+host+port+path."""
    if not base_url or not base_url.strip():
        raise _invalid("base_url không được để trống")
    base_url = base_url.strip()
    parsed = _parse_http_url(base_url)
    allowlist = get_settings().ai_base_url_allowlist
    if allowlist and not any(_allowlist_match(parsed, e) for e in allowlist):
        raise _invalid("base_url không nằm trong danh sách được phép (AI_BASE_URL_ALLOWLIST)")
    return base_url


def _validate(data: AISettingsInput) -> None:
    if data.provider not in ("openai", "gemini"):
        raise _invalid("provider phải là 'openai' hoặc 'gemini'")
    for name, value in (("chat_model", data.chat_model), ("embedding_model", data.embedding_model)):
        if not value or not value.strip():
            raise _invalid(f"{name} không được để trống")
        if len(value.strip()) > 100:
            raise _invalid(f"{name} dài tối đa 100 ký tự")
    lo, hi = _TIMEOUT_RANGE
    if data.timeout_seconds is not None and not (lo <= data.timeout_seconds <= hi):
        raise _invalid(f"timeout_seconds phải trong [{lo:.0f}, {hi:.0f}]")
    if data.embedding_dim is not None and data.embedding_dim > CANONICAL_DIM:
        raise _invalid(
            f"Model embedding trả {data.embedding_dim} chiều, vượt giới hạn "
            f"{CANONICAL_DIM} chiều được lưu trữ. Hãy chọn model ≤ {CANONICAL_DIM} chiều."
        )


def _state(row: UserAISettings | None) -> AISettingsState:
    if row is None:
        return AISettingsState(mode="inherit", provider=None, base_url=None, has_key=False,
                               key_hint=None, chat_model=None, embedding_model=None, timeout_seconds=None)
    return AISettingsState(
        mode=row.mode, provider=row.provider, base_url=row.base_url,
        has_key=row.api_key_enc is not None, key_hint=row.api_key_hint,
        chat_model=row.chat_model, embedding_model=row.embedding_model,
        timeout_seconds=float(row.timeout_seconds) if row.timeout_seconds is not None else None,
    )


class AISettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserAISettingsRepository(session)
        self._session = session

    # ---------------------------------------------------------- resolver (P1)
    async def provider_for(self, user_id: uuid.UUID) -> AIProvider:
        """Provider AI của user. Được cả API dependency và indexing worker dùng → cùng cache."""
        row = await self._repo.get(user_id)
        if row is None or row.mode == "inherit":
            return get_ai_provider()

        if row.provider not in ("openai", "gemini"):
            raise AppError("Cấu hình AI của user không hợp lệ", code="AI_CONFIG_INVALID")
        api_key = ""
        if row.api_key_enc is not None:
            try:
                api_key = ai_keys.decrypt(user_id, row.api_key_enc)
            except (InvalidTag, ValueError) as e:
                # Xoay JWT_SECRET khi chưa đặt AI_KEY_SECRET → key cũ không đọc được (runbook).
                raise AppError(
                    "Khoá API đã lưu không giải mã được (server đổi khoá mã hoá?), "
                    "vui lòng nhập lại khoá trong Cài đặt",
                    code="AI_KEY_UNREADABLE",
                ) from e

        cfg = UserProviderConfig(
            user_id=str(user_id),
            provider=row.provider,  # type: ignore[arg-type] — đã kiểm tra ở trên
            base_url=row.base_url or "",
            api_key=api_key,
            chat_model=row.chat_model or "",
            embedding_model=row.embedding_model or "",
            timeout_seconds=float(row.timeout_seconds) if row.timeout_seconds is not None else None,
        )
        return provider_cache.get_or_build(cfg)

    # ---------------------------------------------------------- CRUD (P2)
    async def get(self, user_id: uuid.UUID) -> AISettingsState:
        return _state(await self._repo.get(user_id))

    async def is_byok(self, user_id: uuid.UUID) -> bool:
        row = await self._repo.get(user_id)
        return row is not None and row.mode == "byok"

    # ------------------------------------------------- applied_fingerprint (P5.S5, §7.2)
    # Controller/worker repair gọi qua service (không import repo — ranh giới ownership L4).

    async def mark_applied(self, user_id: uuid.UUID, fingerprint: str) -> None:
        """Đánh dấu fingerprint đã được bàn giao cho rebuild. Điều kiện
        `embedding_fingerprint = :fp` để KHÔNG đè dấu lên cấu hình mới hơn (P5 §7.4)."""
        await self._repo.mark_applied(user_id, fingerprint)

    async def fingerprint_is_current(self, user_id: uuid.UUID, fingerprint: str) -> bool:
        """Fingerprint truyền vào có còn là cấu hình hiện hành không (guard chống save cũ
        ghi đè save mới — start_rebuild không được enqueue job của cấu hình đã bị thay)."""
        return await self._repo.fingerprint_is_current(user_id, fingerprint)

    async def set_inherit_fingerprint(self, user_id: uuid.UUID, fingerprint: str) -> None:
        """Đồng bộ fingerprint server hiện tại cho row inherit trước khi repair enqueue."""
        await self._repo.set_inherit_fingerprint(user_id, fingerprint)

    async def pending_rebuilds(self) -> list[tuple[uuid.UUID, str, str | None]]:
        """Các row có applied_fingerprint lệch embedding_fingerprint (crash giữa save và
        rebuild). Trả (user_id, mode, embedding_fingerprint) cho worker repair."""
        return await self._repo.find_applied_mismatches()

    async def current_fingerprint(self, user_id: uuid.UUID) -> str:
        """Fingerprint embedding HIỆN HÀNH của user — indexing_job so với payload của job
        để bỏ job của cấu hình cũ (ADR-0016 §4.6). inherit/chưa có row → fingerprint server."""
        row = await self._repo.get(user_id)
        if row is None or row.mode == "inherit":
            return server_embedding_fingerprint()
        if row.embedding_fingerprint:
            return row.embedding_fingerprint
        return embedding_fingerprint(row.provider or "", row.base_url or "", row.embedding_model or "")

    async def save(self, user_id: uuid.UUID, data: AISettingsInput) -> SaveResult:
        old_row = await self._repo.get(user_id)  # đọc TRƯỚC upsert — cần trạng thái cũ
        if data.mode == "inherit":
            # Quay về cấu hình server: chỉ đổi mode, GIỮ nguyên row. Chưa từng cấu hình →
            # không cần tạo row. Ghi fingerprint server hiện hành để repair biết cần rebuild
            # về đâu (P5 §7.2).
            new_fp = server_embedding_fingerprint()
            if old_row is not None:
                fields: dict[str, object] = {"mode": "inherit", "embedding_fingerprint": new_fp}
                if not _rebuild_required(old_row, "inherit", new_fp):
                    fields["applied_fingerprint"] = new_fp  # đồng bộ — repair không enqueue oan
                row = await self._repo.upsert(user_id, fields)
                await self._session.commit()
            else:
                row = None
        else:
            _validate(data)
            new_fp = embedding_fingerprint(
                data.provider or "", data.base_url or "", data.embedding_model or "")
            fields = {
                "mode": "byok",
                "provider": data.provider,
                "base_url": validate_base_url(data.base_url),
                "chat_model": data.chat_model.strip() if data.chat_model else None,
                "embedding_model": data.embedding_model.strip() if data.embedding_model else None,
                "embedding_fingerprint": new_fp,
                "timeout_seconds": data.timeout_seconds,
            }
            if not _rebuild_required(old_row, "byok", new_fp):
                fields["applied_fingerprint"] = new_fp
            if data.api_key is not None:  # None = giữ key cũ (một số model local không cần key)
                key = data.api_key.strip()
                fields["api_key_enc"] = ai_keys.encrypt(user_id, key) if key else None
                fields["api_key_hint"] = key[-4:] if key else None
            row = await self._repo.upsert(user_id, fields)
            await self._session.commit()

        provider_cache.invalidate_user(str(user_id))  # lần gọi kế tiếp dùng key mới ngay
        return SaveResult(
            _state(row), fingerprint=new_fp,
            rebuild_required=_rebuild_required(old_row, data.mode, new_fp))

    async def delete(self, user_id: uuid.UUID) -> SaveResult:
        """Về mode=inherit (nút "Dùng cấu hình server"): giữ provider/models làm bản nháp,
        XOÁ key khỏi DB (reset = không giữ vật liệu nhạy cảm)."""
        old_row = await self._repo.get(user_id)  # đọc TRƯỚC upsert — cần trạng thái cũ
        new_fp = server_embedding_fingerprint()
        fields: dict[str, object] = {"mode": "inherit", "api_key_enc": None,
                                     "api_key_hint": None, "embedding_fingerprint": new_fp}
        if not _rebuild_required(old_row, "inherit", new_fp):
            fields["applied_fingerprint"] = new_fp
        row = await self._repo.upsert(user_id, fields)
        await self._session.commit()
        provider_cache.invalidate_user(str(user_id))
        return SaveResult(_state(row), fingerprint=new_fp,
                          rebuild_required=_rebuild_required(old_row, "inherit", new_fp))

    # ---------------------------------------------------------- test kết nối (P2, §4.9)
    async def test_connection(self, user_id: uuid.UUID, data: AISettingsInput) -> AITestResult:
        """Chạy 1 embed + 1 complete với timeout 30s, không retry. KHÔNG lưu cấu hình,
        KHÔNG dùng provider cache (cấu hình test có thể khác đã lưu) — đóng client sau khi chạy.

        `api_key` None → dùng key đã lưu; rỗng → không key (model local)."""
        _validate(data)
        base_url = validate_base_url(data.base_url)
        api_key = data.api_key.strip() if data.api_key else ""
        if data.api_key is None:  # không gửi key → dùng key đã lưu (nếu có)
            row = await self._repo.get(user_id)
            if row is not None and row.api_key_enc is not None:
                try:
                    api_key = ai_keys.decrypt(user_id, row.api_key_enc)
                except (InvalidTag, ValueError) as e:
                    raise AppError(
                        "Khoá API đã lưu không giải mã được, vui lòng nhập lại khoá",
                        code="AI_KEY_UNREADABLE",
                    ) from e
        assert data.provider is not None  # _validate đảm bảo
        cfg = UserProviderConfig(
            user_id=str(user_id), provider=data.provider, base_url=base_url, api_key=api_key,
            chat_model=(data.chat_model or "").strip(), embedding_model=(data.embedding_model or "").strip(),
            timeout_seconds=data.timeout_seconds,
        )
        probe = build_raw_provider(cfg, timeout_seconds=_TEST_TIMEOUT_SECONDS, max_retries=0)
        try:
            try:
                t0 = time.perf_counter()
                emb = await probe.embed([_TEST_EMBED_TEXT])
                latency = int((time.perf_counter() - t0) * 1000)
                dim = len(emb.vectors[0]) if emb.vectors else 0
                if dim > CANONICAL_DIM:
                    return AITestResult(
                        ok=False, embedding_dim=dim, stage="embedding", code="AI_PROVIDER_ERROR",
                        message=f"Model embedding trả {dim} chiều, vượt giới hạn {CANONICAL_DIM} chiều "
                                "được lưu trữ. Hãy chọn model có số chiều ≤ 1536.")
                embedding = {"model": emb.model, "dim": dim,
                             "padded": dim < CANONICAL_DIM, "latency_ms": latency}
            except AIProviderError as e:
                return AITestResult(ok=False, stage="embedding", code="AI_PROVIDER_ERROR",
                                    message=str(e))
            try:
                t0 = time.perf_counter()
                comp = await probe.complete(_TEST_CHAT, max_tokens=32)
                latency = int((time.perf_counter() - t0) * 1000)
                chat = {"model": comp.model, "latency_ms": latency, "sample": comp.text.strip()[:200]}
            except AIProviderError as e:
                return AITestResult(ok=False, stage="chat", code="AI_PROVIDER_ERROR", message=str(e),
                                    embedding=embedding)
            return AITestResult(ok=True, embedding_dim=dim, embedding=embedding, chat=chat)
        finally:
            await probe.aclose()  # client test không vào cache — luôn đóng
