# Báo cáo P2 — Service/controller `/me/ai-settings` + test endpoint + quota reset + local auth

> **Ngày:** 2026-11-14 · **Phase:** P2/5 · **Commits:** `952ef73` (S1), `08a17f9` (S2), `8f68003` (S3), `bc9f4d5` (S4), `e1751fe` (S5)
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` §7 (P2), §4.7–4.9, §5

## Đã làm (5 slice, mỗi slice 1 commit + test)

### S1 — Schema + repository CRUD + service (`952ef73`)
- `presentation/schemas/ai_settings.py`: `AISettingsIn/Out` (response **không bao giờ chứa key** —
  chỉ `has_key` + `key_hint` "…4 ký tự cuối"), `AISTestIn/Out`, `ServerDefaultOut`, `AIRebuildOut`
  (wire thật ở P3), `EmbeddingTestOut/ChatTestOut`.
- `UserAISettingsRepository.upsert` (partial fields, `updated_at` luôn làm mới).
- `AISettingsService`: `get`, `save` (byok: validate + mã hoá key + fingerprint; **api_key null =
  giữ key cũ, "" = xoá key**; inherit: chỉ đổi mode, giữ nguyên row để biết fingerprint đang dùng),
  `delete` (về inherit + xoá key khỏi DB), `is_byok`, `embedding_fingerprint()`
  = sha256(provider|base_url|model) — đổi key/chat model **không** đổi fingerprint.
- Validate theo §5: base_url http/https + allowlist prefix; model 1–100 ký tự; timeout [5,600];
  provider openai/gemini. Lỗi → `AppError(code="AI_CONFIG_INVALID")` → 400.
- Test unit: 8 case (fingerprint bỏ qua key/chat model; state/repr không có plaintext;
  null/"" semantics; inherit giữ row; delete xoá key; 8 cấu hình sai bị từ chối và không ghi DB).

### S2 — Controller + router (`08a17f9`)
- `GET/PUT/DELETE /me/ai-settings` (`AiSettingsController`, tag `ai-settings`), đăng ký router.
- `GET` trả kèm `server_default` (đúng model chat/embedding theo `AI_PROVIDER` hiện hành).
- Integration test (tự skip khi thiếu `TEST_DATABASE_URL`): key chỉ xuất hiện dưới dạng ciphertext
  trong DB (assert `b"sk-..." not in api_key_enc`), không lọt GET/PUT response; validate 400/422;
  cấu hình cách ly theo user.

### S3 — `POST /me/ai-settings/test` (`8f68003`)
- Infrastructure tách `build_user_settings()` + `build_raw_provider()` (adapter thẳng, không bọc
  canonical) — test đo **số chiều native** của model; `timeout=30s`, `max_retries=0` (phản hồi
  nhanh); client test **không vào cache** và luôn được đóng trong `finally`.
- `AISettingsService.test_connection`: `api_key` None → dùng key đã lưu; trả
  `{model, dim, padded, latency_ms}` cho embedding + `{model, latency_ms, sample}` cho chat;
  > 1536 chiều → `ok=false` với thông báo "vượt 1536 chiều"; lỗi chat vẫn kèm kết quả embedding.
- Rate limit riêng: `rate_limit_ai_settings_test_per_minute` (mặc định 6/phút) → 429.
- Test: 4 unit (stub provider: 768→padded, 3072→từ chối, chat 401 vẫn có embedding, client đóng)
  + 3 integration (endpoint unreachable → stage=embedding, 400, 429 sau 7 lần gọi).

### S4 — Quota `reset_usage` + `billing_mode` (`bc9f4d5`)
- `reset_demo` → **`reset_usage`**: điều kiện `is_dev_login_allowed or is_byok(user_id)` (D6);
  code lỗi `DEMO_ONLY` → `RESET_NOT_ALLOWED` (extension không tham chiếu code cũ — đã grep).
- `QuotaOut` + `billing_mode: "server"|"byok"` (additive), controller điền qua `is_byok`.
- Luồng RESERVE→COMMIT/RELEASE **không đổi**.
- Integration: cập nhật 2 test cũ (exact-match response, code mới); thêm case user BYOK được reset
  kể cả khi `ENABLE_DEV_LOGIN=false`.

### S5 — `GET /auth/config` + local auth (`e1751fe`)
- `GET /auth/config` public → `{"auth_mode": "google"|"local"}`, **không trả email**.
- `AuthService.dev_login`: `auth_mode=local` → **bỏ qua email client gửi**, luôn dùng
  `LOCAL_AUTH_EMAIL` (sub=`dev:<local_auth_email>`) — đăng nhập nhiều lần vẫn cùng 1 user;
  JWT/refresh flow giữ nguyên. Google flow không đổi.
- `main._check_config`: log **WARNING** lúc khởi động khi local mode ("API KHÔNG có xác thực,
  bắt buộc bind 127.0.0.1 hoặc proxy có auth").
- Integration: config mặc định google; local mode đăng nhập đúng 1 user bất kể email client;
  luồng google cũ không đổi.

## Quyết định nhỏ trong phase

- **DELETE xoá key khỏi DB** (giữ provider/models làm bản nháp): kế hoạch chỉ nói "quay về
  mode=inherit"; xoá key là lựa chọn an toàn về privacy (reset = không giữ vật liệu nhạy cảm),
  còn key có thể nhập lại khi cần. PUT mode=inherit thì **giữ** key (quay lại BYOK nhanh).
- **`billing_mode` điền ở cả GET lẫn reset** — UI cần biết mode ở mọi view quota.
- **Test endpoint trả `dim` native + `padded`** (vd 768 → `padded: true`): kế hoạch ví dụ `dim: 1536`
  nhưng §10 yêu cầu "test endpoint hiện dim/latency" — native dim là chẩn đoán có ích (người dùng
  biết model sẽ bị pad); ví dụ trong kế hoạch vẫn đúng với model 1536 native.
- `rebuild_note_count` hiện trả **0** (schema đã chốt); tính thật ở P3 (cần count qua
  `business/notes` — service này chưa có API count, và P3 sở hữu phần orchestration rebuild).
- `AuthConfigOut` đặt trong `schemas/auth.py` (đúng domain), không phải `ai_settings.py`.

## Verify

- ✅ `pytest tests` → **199 passed, 131 skipped** (unit + architecture xanh; integration tự skip
  do thiếu `TEST_DATABASE_URL` — gồm 15 test mới cho P2 sẽ chạy thật khi có Postgres)
- ✅ `ruff check src tests migrations` → sạch
- ✅ `create_app()` OK (router mới nạp được)
- ⚠️ Chưa chạy `npm run gen:api` — thuộc P4 (theo bảng phase)

## Rủi ro / việc mở

- **Mỗi request AI giờ query `user_ai_settings` 1 lần** (PK lookup, index tốt) — chấp nhận được;
  không thêm cache để tránh stale key.
- **PUT/DELETE invalidate ngay cache provider** (`invalidate_user`) — request đang stream (RAG)
  giữ provider cũ đến khi kết thúc (không bị cắt giữa dòng); lần gọi sau dùng key mới.
- `AI_KEY_UNREADABLE` surface ở mọi endpoint AI (qua `provider_for`) — message yêu cầu nhập lại
  key trong Cài đặt; UI cụ thể ở P4.

## Tiếp theo (P3)

Rebuild orchestration: `enqueue_many` (batch 500 + ON CONFLICT DO NOTHING), xoá chunk khi lưu
fingerprint mới, bulk `index_status='PROCESSING'`, fingerprint guard 2 lần trong `indexing_job`
(trước embed, trước khi ghi chunk), tính thật `rebuild_note_count`, integration test đổi cấu
hình giữa chừng.
