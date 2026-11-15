# BYOK & dễ cài đặt — Kế hoạch triển khai

> **Trạng thái:** Draft, chờ duyệt để bắt đầu P0
> **Ngày:** 2026-11-14
> **Phạm vi:** `apps/api` + `apps/extension` + 1 migration + tài liệu vận hành
> **ADR đề xuất:** `docs/adr/0016-per-user-ai-provider-byok.md`
> **Ước lượng:** 8–9 người-ngày

## 0. TL;DR

Cho phép mỗi user cấu hình nhà cung cấp AI ngay trong extension: khoá API, base URL
(OpenAI-compatible hoặc Gemini), model chat, model embedding, timeout. Khoá lưu **mã hoá trong
Postgres**, backend giải mã và proxy lời gọi AI. Thêm `AUTH_MODE=local` để self-host một người
không cần Google OAuth.

Nguyên tắc xuyên suốt: **`mode=inherit` là mặc định** → deployment hiện tại không đổi hành vi.
Mọi thay đổi hợp đồng đều additive; business layer, prompt, SSE và `note_chunks` không bị sửa.

## 1. Mục tiêu

1. Người dùng nhập được key/model/endpoint trong Settings, không cần sửa `.env` hay khởi động lại.
2. Hỗ trợ BYOK cho **cả chat và embedding** (summary, RAG, search, page-match, indexing worker).
3. Hỗ trợ model tự host qua endpoint OpenAI-compatible (Ollama `/v1`, llama.cpp, vLLM, LM Studio).
4. Tác động tối thiểu: không phá hợp đồng frontend/backend, không viết lại service nào.
5. Self-host một người dùng được mà không cần Google OAuth (`AUTH_MODE=local`).

### Không phải mục tiêu

- Không gọi thẳng provider từ extension (giữ ADR-0007).
- Không hỗ trợ đa cấu hình song song (một cấu hình active / user).
- Không hỗ trợ Anthropic native, Ollama native, model discovery qua `/models` trong đợt này.
- Không đổi schema `note_chunks`, không bỏ HNSW, không hỗ trợ vector >1536 chiều.

## 2. Quyết định đã chốt

| # | Vấn đề | Quyết định |
|---|---|---|
| D1 | Nơi lưu key | Server DB, mã hoá AES-GCM; server proxy mọi lời gọi AI |
| D2 | Phạm vi | Chat **và** embedding; chấp nhận rebuild toàn bộ chỉ mục khi đổi model embedding |
| D3 | Chiều vector | Cố định 1536. `<1536` → zero-pad (cosine bất biến); `>1536` → xin native 1536, không được thì **từ chối** |
| D4 | Rebuild | Hộp thoại xác nhận → tự động rebuild; search giảm cấp còn nhánh từ khoá + banner tiến độ |
| D5 | Số cấu hình | Một cấu hình active / user |
| D6 | Quota | Giữ RESERVE→COMMIT và chặn như hiện tại; user BYOK được reset usage; UI đổi nhãn |
| D7 | Timeout | Cột `timeout_seconds` / user, null = dùng `AI_TIMEOUT_SECONDS` toàn cục |
| D8 | Tài khoản | Giữ multi-user + JWT; thêm `AUTH_MODE=local` cho self-host một người |
| D9 | Provider MVP | OpenAI-compatible + Gemini (dùng lại 2 adapter sẵn có) |
| D10 | UX | Card trong Settings hiện có + preset + nút "Kiểm tra kết nối" |
| D11 | Chọn model | Preset gợi ý model cố định (`<datalist>`), vẫn cho nhập tay; **không** gọi `/models` |
| D12 | Khoá mã hoá | `AI_KEY_SECRET` nếu có, fallback HKDF từ `JWT_SECRET` |

## 3. Kiến trúc

```
Extension (Settings card)
   │  RPC: ai/config/get | set | test | reset
   ▼
background/  ──►  API /me/ai-settings      (JWT như mọi endpoint khác)
                     │
                     ├─ UserAISettingsRepository  (user_ai_settings)
                     ├─ ai_keys: AES-GCM decrypt
                     └─ ProviderFactory ──► cache theo (user_id, config hash)
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
                 OpenAIClient (Settings override)            GeminiClient (Settings override)
                   - OpenAI, vLLM, llama.cpp, Ollama /v1       - AI Studio, Vertex
                        │
                        ▼
              CanonicalEmbeddingProvider (pad 1536 / reject >1536)

Worker indexing_job ──► AISettingsService.provider_for(note.user_id) ──► cùng factory/cache
```

Điểm cốt lõi: **không sửa adapter**. `OpenAIClient`/`GeminiClient` đã nhận `Settings`, nên chỉ cần
`settings.model_copy(update={...})` với các trường `openai_*` / `gemini_*`.

## 4. Backend

### 4.1. Bảng `user_ai_settings` (migration `20261114_0003_user_ai_settings.py`)

```sql
CREATE TABLE user_ai_settings (
    user_id                UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    mode                   VARCHAR(10) NOT NULL DEFAULT 'inherit',  -- inherit | byok
    provider               VARCHAR(20),                             -- openai | gemini
    base_url               TEXT,
    api_key_enc            BYTEA,                                   -- nonce || ciphertext || tag
    api_key_hint           VARCHAR(8),                              -- 4 ký tự cuối để hiển thị
    chat_model             VARCHAR(100),
    embedding_model        VARCHAR(100),
    embedding_fingerprint  CHAR(64),                                -- sha256(provider|base_url|model)
    timeout_seconds        NUMERIC(6,2),                            -- NULL = dùng global
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_user_ai_settings_mode CHECK (mode IN ('inherit','byok')),
    CONSTRAINT ck_user_ai_settings_byok CHECK (
        mode = 'inherit' OR (
            provider IS NOT NULL AND base_url IS NOT NULL AND
            chat_model IS NOT NULL AND embedding_model IS NOT NULL AND
            embedding_fingerprint IS NOT NULL
        )
    )
);
```

- `api_key_enc` cho phép NULL: model local không cần khoá.
- `mode='inherit'` vẫn giữ nguyên row (nếu đã từng cấu hình) để biết fingerprint đang dùng.
- Downgrade: `DROP TABLE user_ai_settings`.

`EmbeddingFingerprint`:

```python
sha256(f"{provider}|{base_url.rstrip('/')}|{embedding_model}".encode()).hexdigest()
```

Không gồm key và chat model → đổi key hoặc đổi model chat **không** rebuild.

### 4.2. Mã hoá key — `infrastructure/ai_keys.py`

```python
def _key() -> bytes:
    base = s.ai_key_secret.get_secret_value() or s.jwt_secret.get_secret_value()
    return HKDF(SHA256(), 32, salt=b"quickassist", info=b"ai-keys-v1").derive(base.encode())

def encrypt(user_id: UUID, plaintext: str) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext.encode(), user_id.bytes)

def decrypt(user_id: UUID, blob: bytes) -> str:
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], user_id.bytes).decode()
```

- AAD = `user_id.bytes` → không thể hoán đổi ciphertext giữa 2 row.
- Thêm `cryptography>=42` vào `pyproject.toml` (hiện chỉ có gián tiếp qua `pyjwt[crypto]`).
- Không log plaintext/ciphertext. `AIProviderError` hiện chỉ chứa `http <status>` nên an toàn.
- Xoay `JWT_SECRET` khi không đặt `AI_KEY_SECRET` → phải nhập lại key; ghi rõ trong runbook.

### 4.3. Config mới (`infrastructure/config.py`)

```python
ai_key_secret: SecretStr = SecretStr("")          # tuỳ chọn; rỗng → derive từ jwt_secret
ai_base_url_allowlist: list[str] = []             # rỗng = cho phép mọi http(s) URL
auth_mode: Literal["google", "local"] = "google"
local_auth_email: str = "local@quickassist.local"
rate_limit_ai_settings_test_per_minute: int = 6
ai_embedding_strict_dim: bool = True              # BYOK override = False để cho phép pad
ai_request_embedding_dimensions: bool = True      # BYOK OpenAI-compatible override = False
```

- `.env.example` / `infra/.env.example` thêm 3 biến người dùng cần biết: `AI_KEY_SECRET`,
  `AUTH_MODE`, `LOCAL_AUTH_EMAIL`. Tất cả có default → không bắt buộc khi nâng cấp.
- `is_dev_login_allowed` sửa thành:
  `auth_mode == "local" or (enable_dev_login and app_env in ("dev","test"))`.

### 4.4. Provider resolver + cache — `infrastructure/openai/__init__.py`

```python
@dataclass(frozen=True)
class UserProviderConfig:
    user_id: str
    provider: Literal["openai", "gemini"]
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    timeout_seconds: float | None

def build_provider(cfg: UserProviderConfig) -> AIProvider:
    s = get_settings().model_copy(update={
        "ai_timeout_seconds": cfg.timeout_seconds or get_settings().ai_timeout_seconds,
        "embedding_dim": 1536,                 # hợp đồng lưu trữ
        "ai_embedding_strict_dim": False,      # cho phép adapter trả chiều native
        "ai_request_embedding_dimensions": False,
        **({"openai_base_url": cfg.base_url, "openai_api_key": SecretStr(cfg.api_key),
            "chat_model": cfg.chat_model, "embedding_model": cfg.embedding_model}
           if cfg.provider == "openai" else
           {"gemini_base_url": cfg.base_url, "gemini_api_key": SecretStr(cfg.api_key),
            "gemini_chat_model": cfg.chat_model, "gemini_embedding_model": cfg.embedding_model}),
    })
    raw = OpenAIClient(s) if cfg.provider == "openai" else GeminiClient(s)
    return CanonicalEmbeddingProvider(raw)
```

- Cache LRU bounded (64) keyed bằng `sha256(user_id | provider | base_url | chat | embed | timeout | sha256(key))`.
  **Luôn có `user_id` trong khoá** → không thể chia sẻ provider giữa 2 user.
- Evict: đóng client bất đồng bộ (`asyncio.create_task(p.aclose())`); đăng ký `close_all()` trong
  lifespan của FastAPI và `finally` của worker.
- Khi lưu/ xoá cấu hình: gọi `provider_cache.invalidate_user(user_id)` để lần gọi kế tiếp dùng key
  mới ngay, không chờ eviction.
- **Không** đóng client theo request: RAG trả `StreamingResponse`, vòng đời dài hơn handler.
- Dependency:
  ```python
  async def get_user_ai_provider(user_id: CurrentUserId, session: DbSession) -> AIProvider: ...
  AIProviderDep = Annotated[AIProvider, Depends(get_user_ai_provider)]
  ```
  Tên/type giữ nguyên → **4 controller AI không sửa**. `mode='inherit'` → trả `get_ai_provider()` cũ.

### 4.5. Canonical embedding 1536 — `infrastructure/openai/dimensions.py`

```python
class CanonicalEmbeddingProvider:
    """Bọc AIProvider, chuẩn hoá vector về 1536 chiều mà không đổi cosine."""
    async def embed(self, texts):
        r = await self._inner.embed(texts)
        return EmbeddingResult([_canonical(v, self._max_dim) for v in r.vectors], r.usage, r.model)

def _canonical(v: list[float]) -> list[float]:
    n = len(v)
    if n == 1536: return v
    if n < 1536:  return v + [0.0] * (1536 - n)   # zero-pad: dot và norm không đổi
    raise AIProviderError("Model embedding trả >1536 chiều...", retryable=False)
```

Giải thích để review: với cosine, `cos([q,0],[v,0]) = cos(q,v)` vì tử số và mẫu số đều không đổi.
Zero-pad **không mất chất lượng**, chỉ tốn dung lượng. Truncate mới mất chất lượng → không làm.

Thay đổi nhỏ trong 2 adapter để hỗ trợ chế độ BYOK:

- `OpenAIClient._embed_batch`: chỉ gửi `"dimensions"` khi `ai_request_embedding_dimensions=True`.
- `OpenAIClient.embed` / `GeminiClient.embed`: khi `ai_embedding_strict_dim=False`, chỉ kiểm tra
  "mọi vector cùng chiều", không bắt buộc bằng `embedding_dim`.
- `GeminiClient` vẫn gửi `outputDimensionality=1536`; nếu model không nhận → lỗi 400 được test
  endpoint trả về nguyên nhân.

### 4.6. Rebuild chỉ mục — `business/ai_settings/service.py`

Khi lưu cấu hình có fingerprint mới:

1. `DELETE FROM note_chunks WHERE user_id = :uid` — search lập tức rơi về nhánh từ khoá.
2. `UPDATE notes SET index_status='PROCESSING', index_rev=index_rev+1, index_error=NULL
   WHERE user_id=:uid AND is_deleted=false`.
3. Enqueue job `semantic_search.index_note` cho từng note, payload kèm
   `embedding_fingerprint`; thêm helper `enqueue_many()` vào `infrastructure/jobs/queue.py`
   (một `INSERT ... VALUES (...)` + `ON CONFLICT (dedupe_key) DO NOTHING`, chia lô 500).
4. Trả `rebuild: {required: true, notes: N}` để UI hiện banner.

Guard trong `indexing_job.py` (bắt buộc, vì `replace_for_note()` hiện không được bảo vệ bởi `index_rev`):

```python
expected = payload.get("embedding_fingerprint")
if expected and expected != await current_fingerprint(session, note.user_id):
    return                      # job của cấu hình cũ → bỏ, job mới đã được xếp
```

Kiểm tra lại fingerprint **sau khi embed, trước khi ghi chunk** để chống đổi cấu hình giữa chừng.

Chuyển `byok → inherit` cũng tính fingerprint mới (từ Settings server) và rebuild nếu khác.
Đổi key / chat model → fingerprint không đổi → không rebuild.

### 4.7. Quota

- Giữ nguyên `QuotaService.reserve/commit/release`, không đổi luồng nghiệp vụ.
- `reset_demo()` đổi tên thành `reset_usage()`; điều kiện:
  `is_dev_login_allowed or AISettingsService(session).is_byok(user_id)`.
- `QuotaOut` thêm `billing_mode: Literal["server","byok"]` (additive) do controller điền.
- UI: BYOK hiện "Đã dùng (key của bạn)" + nút "Đặt lại số liệu"; vẫn hiện thanh giới hạn như hiện tại.

### 4.8. `AUTH_MODE=local`

Mục tiêu: self-host một người, **không phá hợp đồng JWT/quyền sở hữu**.

- `GET /auth/config` (public, không secret) → `{"auth_mode":"google"|"local"}`. Không trả email
  (server tự quyết định, client không cần biết).
- `AuthService.dev_login`: nếu `auth_mode=="local"` thì **bỏ qua email client gửi**, dùng
  `local_auth_email`; cấp JWT/refresh như bình thường qua `upsert_google_user(sub="dev:...")`.
- Extension `sessionInfo()`: nếu chưa có refresh token và `auth_mode=="local"` → tự gọi
  `auth.devLogin` một lần rồi trả `signedIn=true`; `AuthGate` không hiện nút Google.
- Thêm `auth.devLogin` vào `endpoints.ts` (hiện handler `e2e/devLogin` đang tự gọi URL, lệch quy
  ước "chỉ endpoints.ts biết URL") và cho cả hai đường dùng chung hàm này.
- `SessionInfo` thêm `authMode: "google" | "local"` (additive). Ở local mode ẩn nút Đăng xuất
  (nếu không sẽ tự đăng nhập lại ngay).
- Cảnh báo bảo mật: local mode = **không có xác thực**. Bắt buộc bind `127.0.0.1` hoặc đặt sau
  proxy có auth. Ghi log WARNING lúc khởi động và thêm mục vào `docs/deploy/runbook.md`.
- Không đổi `CORS_ORIGINS`, không đổi Google OAuth flow khi `auth_mode=google`.

### 4.9. Test kết nối

`POST /me/ai-settings/test` — tái dùng logic `scripts/check_ai.py`:

- Body giống `PUT` (thiếu `api_key` thì dùng key đã lưu).
- Chạy `embed(["Hà Nội là thủ đô..."])` + `complete(...)` với timeout ngắn (30s), trả:
  ```json
  {"ok": true,
   "embedding": {"model": "...", "dim": 1536, "latency_ms": 412},
   "chat": {"model": "...", "latency_ms": 903, "sample": "..."}}
  ```
- Lỗi → `{ok:false, stage:"embedding"|"chat", code:"AI_PROVIDER_ERROR", message:"http 401"}`.
- Rate limit riêng `rate_limit_ai_settings_test_per_minute`.
- Không bắt buộc test trước khi lưu; UI cảnh báo nếu lưu khi chưa test thành công.

## 5. Hợp đồng API mới

Tất cả dưới `/api/v1`, cần Bearer token như hiện tại. **Không sửa endpoint cũ.**

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/me/ai-settings` | cấu hình hiện tại + `has_key`, `key_hint`, `rebuild_note_count` |
| `PUT` | `/me/ai-settings` | lưu; trả cấu hình + `rebuild` nếu fingerprint đổi |
| `DELETE` | `/me/ai-settings` | quay về `mode=inherit`, rebuild nếu cần |
| `POST` | `/me/ai-settings/test` | kiểm tra kết nối |
| `GET` | `/auth/config` | `auth_mode` cho extension (public) |

`PUT` request:

```json
{
  "mode": "byok",
  "provider": "openai",
  "base_url": "http://localhost:11434/v1",
  "api_key": "sk-...",              // null = giữ key cũ
  "chat_model": "llama3.1",
  "embedding_model": "nomic-embed-text",
  "timeout_seconds": 180
}
```

`GET`/`PUT` response **không bao giờ chứa key**:

```json
{
  "mode": "byok",
  "provider": "openai",
  "base_url": "http://localhost:11434/v1",
  "has_key": true,
  "key_hint": "…a1b2",
  "chat_model": "llama3.1",
  "embedding_model": "nomic-embed-text",
  "timeout_seconds": 180,
  "rebuild_note_count": 128,
  "server_default": {"provider": "gemini", "chat_model": "gemma-4-31b-it",
                     "embedding_model": "gemini-embedding-001"}
}
```

Validate: `base_url` chỉ `http/https`; nếu `ai_base_url_allowlist` khác rỗng thì phải khớp prefix;
`timeout_seconds` trong `[5, 600]`; model không rỗng, ≤100 ký tự.

Sau khi thêm endpoint: chạy `npm run gen:api` để sinh lại `apps/extension/src/shared/api/schema.d.ts`.

## 6. Extension

### 6.1. RPC mới (`shared/messaging/protocol.ts` + `background/handlers.ts`)

```ts
'ai/config/get':   { req: void; res: AiConfig }
'ai/config/set':   { req: AiConfigInput; res: AiConfig & { rebuild?: { required: boolean; notes: number } } }
'ai/config/test':  { req: AiConfigInput; res: AiConfigTestResult }
'ai/config/reset': { req: void; res: AiConfig & { rebuild?: ... } }
```

- `endpoints.ts` thêm nhóm `aiSettings: { get, set, remove, test, authConfig }` (URL chỉ nằm ở đây).
- `background/api.ts` không đổi; UI không import `shared/api` (test kiến trúc vẫn xanh).

### 6.2. Card "Nhà cung cấp AI" trong `SettingsView`

Đặt trên card "Hạn mức AI". Thành phần:

1. **Preset** (select): OpenAI · Google Gemini · Ollama (local) · LM Studio · llama.cpp · Custom.
   Preset chỉ điền default, mọi ô vẫn sửa được.
2. `base_url` (text), `api_key` (password + nút hiện/ẩn; nếu đã lưu hiện `key_hint` + nút "Xoá key").
3. `chat_model`, `embedding_model`: text + `<datalist>` gợi ý theo preset.
4. `timeout_seconds`: mục "Nâng cao", placeholder 90.
5. Nút **Kiểm tra kết nối** → hiện embedding dim/latency và chat latency/sample.
6. Nút **Lưu** → nếu fingerprint đổi, `ConfirmDialog`: "Sẽ dựng lại chỉ mục ngữ nghĩa của N ghi chú.
   Tìm kiếm từ khoá vẫn hoạt động trong lúc dựng."; sau khi lưu hiện banner tiến độ.
7. Nút **Dùng cấu hình server** (DELETE) khi đang BYOK.

Preset mặc định:

| Preset | base_url | chat | embedding | key |
|---|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` | bắt buộc |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/models` | `gemma-4-31b-it` | `gemini-embedding-001` | bắt buộc |
| Ollama | `http://localhost:11434/v1` | `llama3.1` | `nomic-embed-text` (768 → pad) | không |
| LM Studio | `http://localhost:1234/v1` | (trống) | (trống) | không |
| llama.cpp | `http://localhost:8080/v1` | (trống) | (trống) | không |

Không cần thêm `host_permissions`: extension chỉ nói chuyện với API backend.

## 7. Kế hoạch theo giai đoạn

| Phase | Việc chính | File chính | Ước lượng |
|---|---|---|---|
| **P0** | ADR 0016; config; `ai_keys`; model + migration | `docs/adr/0016-*.md`, `infrastructure/config.py`, `infrastructure/ai_keys.py`, `data/models/user_ai_settings.py`, `migrations/versions/20261114_0003_*.py` | 0.75d |
| **P1** | Resolver + cache + canonical dim + sửa 2 adapter + `AIProviderDep` + worker | `infrastructure/openai/__init__.py`, `openai/dimensions.py`, `openai/openai_client.py`, `openai/gemini_client.py`, `presentation/api/deps.py`, `business/semantic_search/indexing_job.py` | 2d |
| **P2** | Service/controller/schema cấu hình + test endpoint + quota reset + `auth/config` + local auth | `business/ai_settings/*`, `presentation/api/v1/controllers/ai_settings_controller.py`, `schemas/ai_settings.py`, `router.py`, `business/quota/quota_service.py`, `business/auth/auth_service.py`, `presentation/api/v1/controllers/auth_controller.py` | 1.75d |
| **P3** | Rebuild orchestration: `enqueue_many`, xoá chunk, bulk status, fingerprint guard, integration test | `infrastructure/jobs/queue.py`, `business/ai_settings/service.py`, `data_access/repositories/note_repository.py`, `note_chunk_repository.py` | 1.5d |
| **P4** | Extension: types regen, endpoints, RPC, card UI, preset, confirm dialog, auto local-login | `shared/api/endpoints.ts`, `schema.d.ts`, `shared/messaging/protocol.ts`, `background/handlers.ts`, `background/auth/session.ts`, `ui/features/account/SettingsView.tsx`, `ui/features/account/ProviderCard.tsx` | 2d |
| **P5** | Docs + test ma trận + E2E stub provider + hardening | `README.md`, `docs/deploy/runbook.md`, `docs/user-guide.md`, `apps/api/.env.example`, `infra/.env.example`, tests | 1d |

Thứ tự merge: P0 → P1 → P2 → P3 (backend chạy được với cấu hình mặc định) → P4 → P5.
P2 và P4 có thể song song sau khi chốt schema response.

## 8. Migration & tương thích ngược

- Migration chỉ **thêm bảng**, không sửa bảng cũ → deploy an toàn, rollback = drop table.
- Không có row `user_ai_settings` → `mode=inherit` → hành vi y hệt hiện tại.
- `AI_PROVIDER=mock` vẫn là mặc định dev/CI; test hiện có không cần key.
- `note_chunks` và `_HYBRID_SQL` không đổi → HNSW, RRF, evaluation giữ nguyên.
- Chunk cũ không có fingerprint: chỉ bị xoá khi user chủ động đổi cấu hình embedding.
- OpenAPI chỉ thêm schema/endpoint; `schema.d.ts` sinh lại nhưng không phá type cũ.
- `infra/.env.example` thêm biến có default; runbook cũ vẫn chạy đúng.

## 9. Test

### Unit

- `test_ai_keys.py`: roundtrip; AAD sai (user khác) → lỗi; key derive ổn định.
- `test_embedding_dimensions.py`: 768 → pad đúng 1536; cosine trước/sau bằng nhau (property test
  với vector ngẫu nhiên); >1536 → `AIProviderError` không retry.
- `test_provider_resolver.py`: cache tách biệt 2 user cùng config; `inherit` trả singleton;
  `model_copy` không làm bẩn `get_settings()`.
- `test_ai_settings_fingerprint.py`: đổi key/chat model → không đổi; đổi embed/base/provider → đổi.
- `test_auth_local_mode.py`: `auth_mode=local` cho phép dev-login ở prod; email client bị bỏ qua.

### Integration (Postgres)

- CRUD `/me/ai-settings`; response không chứa key; DB lưu ciphertext.
- Rebuild: đổi embedding model → chunk bị xoá, notes `PROCESSING`, job được enqueue đúng số.
- Job cũ với fingerprint lệch → không ghi chunk; job mới ghi đúng.
- BYOK + stub HTTP server (httpx.MockTransport hoặc FastAPI stub):
  summary/search/page-match/RAG dùng base_url của user; user không cấu hình dùng server default.
- Quota reset: user BYOK được phép; user inherit ở prod bị 403.
- Search trong lúc rebuild: nhánh từ khoá vẫn trả kết quả, không lỗi 500.

### Contract / kiến trúc

- `npm run gen:api` không tạo diff ngoài phần thêm.
- `apps/extension/tests/architecture.test.ts` vẫn xanh (UI không import `shared/api`).
- OpenAPI snapshot test cho 5 endpoint mới.

### E2E (Playwright, tuỳ chọn P5)

- Dựng stub OpenAI-compatible trong fixture; cấu hình qua UI; tóm tắt một note; assert stub nhận
  đúng 1 request chat và 1 request embedding; assert không có key trong response API.

### Ma trận thủ công trước khi merge

| Case | Kỳ vọng |
|---|---|
| OpenAI key thật | test OK, summary/RAG/search chạy, không rebuild khi chỉ đổi key |
| Gemini key thật | test OK, embedding 1536 |
| Ollama `nomic-embed-text` (768) | pad, search đúng thứ tự so với trước |
| llama.cpp không key | test OK |
| Key sai | test trả 401 rõ ràng, lưu vẫn được nhưng cảnh báo |
| Model 4096 chiều | test/lưu bị từ chối với thông báo "vượt 1536 chiều" |
| Đổi embedding model | confirm dialog đúng số note, search từ khoá chạy, banner về 0 |
| Đổi key khi đang rebuild | job cũ bỏ, không trộn vector |
| `AUTH_MODE=local` | mở side panel không cần Google; Đăng xuất bị ẩn |
| `AUTH_MODE=google` | luồng cũ không đổi |

## 10. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Rò provider/key chéo user qua cache | **Cao** | Cache key chứa `user_id`; test isolation 2 user cùng base URL; không log key |
| Search tụt chất lượng do model local yếu | Cao | Test endpoint hiện dim/latency; ghi chú model khuyến nghị; so sánh top-5 trên `tests/eval` trước khi phát hành |
| Rebuild lâu, người dùng tưởng treo | Trung bình | Confirm trước với số note; banner tiến độ; keyword search vẫn chạy; giới hạn lô 500 |
| Quên guard fingerprint → trộn vector 2 model | **Cao** | Guard 2 lần (trước embed, trước ghi); integration test đổi cấu hình giữa chừng |
| `base_url` tuỳ ý → SSRF | Trung bình | Chỉ http/https; `AI_BASE_URL_ALLOWLIST` tuỳ chọn; cảnh báo khi `APP_ENV=prod`; local mode khuyến nghị bind localhost |
| Xoay `JWT_SECRET` làm mất key | Trung bình | Khuyến nghị đặt `AI_KEY_SECRET`; ghi runbook; lỗi giải mã → trả `AI_KEY_UNREADABLE`, yêu cầu nhập lại |
| Local mode lộ dữ liệu nếu mở Internet | **Cao** | Log WARNING, tài liệu bắt buộc reverse proxy auth/bind localhost; không bật mặc định |
| `dimensions` bị server local từ chối | Thấp | BYOK tắt gửi `dimensions`; pad ở biên; test endpoint phát hiện sớm |
| FastAPI đóng dependency cắt SSE | Thấp | Dùng cache provider, không close theo request; có test RAG stream >10s |

## 11. Tiêu chí nghiệm thu

1. User chưa cấu hình: toàn bộ test hiện có xanh, không đổi hành vi, không cần biến môi trường mới.
2. Cấu hình OpenAI-compatible qua UI: summary, chat RAG, search, page-match và indexing dùng đúng
   key/base URL; xác nhận bằng stub server (không chỉ bằng mắt).
3. Key không xuất hiện trong bất kỳ response API, log, hay `chrome.storage` nào.
4. Đổi embedding model: confirm đúng số note; chunk bị xoá; keyword search hoạt động; job rebuild
   hoàn tất; search ngữ nghĩa dùng vector mới.
5. Model 768 chiều: lưu + search thành công (zero-pad). Model >1536: bị từ chối với thông báo rõ.
6. Đổi riêng key hoặc chat model: **không** rebuild.
7. `AUTH_MODE=local`: profile Chrome mới mở side panel không cần Google; `AUTH_MODE=google`
   không đổi.
8. Quota: user BYOK reset được usage; user inherit vẫn bị chặn như cũ.
9. `npm run gen:api` sạch; test kiến trúc extension xanh.

## 12. Not Doing (và lý do)

- **Extension gọi thẳng provider** — phá ADR-0007, cần `host_permissions` rộng, vẫn không giải quyết
  search/index server-side.
- **Vector biến thiên / bỏ HNSW** — mất tốc độ, sửa schema + `_HYBRID_SQL` + repository; chưa cần
  cho model ≤1536 chiều.
- **Truncate vector >1536** — mất chất lượng âm thầm; từ chối kèm thông báo trung thực hơn.
- **Nhiều profile / tách chat-embedding** — nhân đôi UI, logic rebuild và ma trận test; chưa có nhu cầu.
- **Anthropic native, Ollama native** — thêm adapter mới; OpenAI-compatible đã phủ các trường hợp
  phổ biến.
- **Model discovery `/models`** — preset + nhập tay đủ dùng, tránh thêm endpoint proxy và xử lý
  provider không hỗ trợ.
- **KMS/Vault** — quá mức với self-host; AES-GCM + env secret là đủ.
- **Lưu lịch sử chat server-side** — giữ ADR-0012.

## 13. ADR 0016 (nội dung đề xuất)

**Bối cảnh.** Cấu hình AI nằm trong `.env`, mọi user dùng chung key của chủ server. Người dùng muốn
tự trả tiền / tự host model; đổi model embedding kéo theo ràng buộc vector 1536 chiều.

**Quyết định.** Thêm `user_ai_settings` (key mã hoá, một cấu hình active); resolver per-user dùng lại
`OpenAIClient`/`GeminiClient` qua `Settings.model_copy`; lưu vector cố định 1536 với zero-pad cho
model nhỏ hơn và từ chối model lớn hơn; rebuild toàn bộ chỉ mục khi fingerprint embedding đổi;
`AUTH_MODE=local` cho self-host một người.

**Phương án loại.** Gọi thẳng provider từ extension (phá ADR-0007); vector biến thiên (mất HNSW);
multi-profile (phức tạp không cần thiết).

**Hệ quả.** (+) BYOK và self-host trở thành tính năng thật, không phải ghi chú trong `.env`.
(−) Thêm bảng + mã hoá + rebuild; người dùng phải chờ dựng lại chỉ mục khi đổi model embedding;
local mode không có xác thực nên phải tự bảo vệ ở tầng triển khai.
