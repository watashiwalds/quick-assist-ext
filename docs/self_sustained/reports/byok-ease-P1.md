# Báo cáo P1 — Resolver per-user + cache + canonical 1536 + adapter + wiring

> **Ngày:** 2026-11-14 · **Phase:** P1/5 · **Commits:** `205b834` (S1), `4b52bea` (S2), `b31a5b0` (S3), `c52ed9b` (S4)
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` §7 (P1), §4.4–4.5

## Đã làm (4 slice, mỗi slice 1 commit + test)

### S1 — Canonical embedding 1536 (`205b834`)
- `infrastructure/openai/dimensions.py`: `CANONICAL_DIM=1536`, `_canonical()` (zero-pad <
  1536 — cosine bất biến; từ chối non-retryable khi > 1536), `CanonicalEmbeddingProvider`
  bọc `AIProvider` (embed chuẩn hoá; complete/stream/aclose đi thẳng).
- Test: bất biến `CANONICAL_DIM == note_chunk.EMBEDDING_DIM` (test chốt vì infrastructure
  không được import data.models theo luật phân tầng); property test cosine 50 vector ngẫu nhiên
  (n ∈ [1,64] → target 128/768/1536); metadata passthrough.

### S2 — 2 adapter nhận cờ BYOK (`4b52bea`)
- `OpenAIClient`: gửi `"dimensions"` **chỉ khi** `ai_request_embedding_dimensions=True`
  (Ollama/llama.cpp không nhận tham số này); `ai_embedding_strict_dim=False` → chỉ yêu cầu
  mọi vector cùng chiều, không bắt buộc bằng `embedding_dim` (ragged vẫn từ chối).
- `GeminiClient`: cùng chính sách strict_dim; **vẫn gửi** `outputDimensionality` (model không
  nhận → 400 nguyên nhân, test endpoint P2 sẽ hiển thị).
- Test: 4 case MockTransport mới theo style sẵn có.

### S3 — Resolver + cache (`b31a5b0`)
- `UserProviderConfig` (frozen dataclass) + `build_provider()`: `get_settings().model_copy()`
  ghi đè `openai_*`/`gemini_*`, `embedding_dim=1536`, tắt strict_dim/`dimensions`, timeout
  override → `OpenAIClient`/`GeminiClient` **không sửa thêm gì** → bọc `CanonicalEmbeddingProvider`.
- `ProviderCache`: LRU 64, khoá `sha256(user_id|provider|base_url|chat|embed|timeout|sha256(key))`
  — **luôn có user_id** → không thể chia sẻ provider giữa 2 user; `invalidate_user()` đóng ngay
  (P2 gọi khi lưu/xoá cấu hình); evict đóng bất đồng bộ (`asyncio.create_task`), ngoài event loop
  → pending cho `close_all()`; **không đóng theo request** (RAG stream sống lâu hơn handler).
- Test: tái dùng cùng config, tách 2 user cùng config, đổi key → provider mới, LRU evict,
  `close_all` đóng httpx client, purity của `model_copy`.

### S4 — Wiring API + worker (`c52ed9b`)
- `data_access/repositories/user_ai_settings_repository.py`: `get(user_id)` (P2 thêm CRUD).
- `business/ai_settings/` mới: `AISettingsService.provider_for(user_id)` — inherit/chưa có row →
  `get_ai_provider()` singleton cũ; BYOK → giải mã key (AAD user_id) → `provider_cache`;
  key không giải mã được → `AppError(code="AI_KEY_UNREADABLE")` (không lộ plaintext).
- `presentation/api/deps.py`: `get_user_ai_provider(user_id, session)` + `AIProviderDep` rebind —
  **4 controller AI (summary/search/page-match/RAG) không sửa một dòng**.
- `business/semantic_search/indexing_job.py`: embed bằng provider của **chủ note**.
- `main.py` lifespan + `worker.py` finally: `provider_cache.close_all()`.

## Lệch so với kế hoạch (có lý do rõ)

- **`business/ai_settings/service.py` được tạo sớm ở P1 (bản tối thiểu)** thay vì P2: luật phân tầng
  (test_L1) cấm `infrastructure` import `data.models.user_ai_settings`, nên việc đọc DB + decrypt
  phải nằm ở business — và cả `deps.py` lẫn `indexing_job` đều cần nó. P2 sẽ mở rộng service này
  (CRUD/validate/test-connection), P3 thêm rebuild orchestration.
- **Fingerprint guard trong indexing_job dời về P3**: kế hoạch liệt kê guard vào P3 ("Rebuild
  orchestration: … fingerprint guard, integration test"); P1 không có payload nào mang fingerprint
  nên thêm giờ là dead code. `provider_for` đã sẵn sàng cho guard.

## Verify

- ✅ `pytest tests` → **187 passed, 118 skipped** (integration skip do không có
  `TEST_DATABASE_URL` — như trước P1; không test nào đỏ)
- ✅ `ruff check src tests` → sạch
- ✅ `create_app()` khởi tạo OK; `provider_cache.close_all()` chạy không lỗi
- ⚠️ Integration thật (BYOK qua stub HTTP, RAG stream >10s không bị cắt provider) đang skip —
  thuộc P3/P5 theo kế hoạch; cần Postgres (`TEST_DATABASE_URL`)

## Rủi ro / việc mở

- **Decrypt mỗi lần resolve** (kể cả cache hit): chi phí AES-GCM trên chuỗi ngắn ~µs, chấp nhận.
  Cache key dùng hash của plaintext key nên phải decrypt trước khi tra cache (dùng ciphertext
  hash thì nonce ngẫu nhiên làm cache luôn miss).
- Mock provider (AI_PROVIDER=mock) **không** được bọc Canonical — đúng kế hoạch (inherit giữ
  nguyên hành vi; mock trả đúng 1536).
- AutoChunk/page-match verify đi qua `AIProviderDep` → giờ đều tôn trọng BYOK (đúng mục tiêu §1).

## Tiếp theo (P2)

Service CRUD `/me/ai-settings` + validate (base_url http(s), allowlist, timeout [5,600], model
≤100 ký tự) + endpoint `test` (rate limit riêng) + quota `reset_usage` + `GET /auth/config` +
local auth + `invalidate_user` khi lưu/xoá.
