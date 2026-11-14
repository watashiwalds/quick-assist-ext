# ADR-0016: Nhà cung cấp AI theo từng người dùng (BYOK) + chế độ tự host một người

- **Trạng thái:** Chấp nhận (14/11/2026) · Kế hoạch: `docs/self_sustained/byok-and-easeofsetting.md` · Liên quan: ADR-0004 (provider port/adapter), ADR-0007 (background gateway), ADR-0006 (hybrid search), ADR-0012 (chat client-side)

## Bối cảnh

Cấu hình AI hiện nằm trong `.env` của server: mọi user dùng chung key và model của chủ server,
muốn đổi phải sửa env và khởi động lại. Nhu cầu thực tế: người dùng tự trả tiền (key riêng),
tự host model (Ollama/llama.cpp/vLLM qua endpoint OpenAI-compatible), và self-host một người
không cần dựng Google OAuth. Ràng buộc kỹ thuật: cột `note_chunks.embedding` cố định 1536 chiều
(HNSW), nên model embedding khác số chiều phải được chuẩn hoá hoặc từ chối.

## Quyết định

1. **Bảng `user_ai_settings`** (một cấu hình active / user): `mode = inherit | byok`; BYOK gồm
   provider (`openai` | `gemini`), `base_url`, key **mã hoá AES-GCM** (nonce ‖ ciphertext ‖ tag,
   AAD = `user_id` — không thể hoán đổi ciphertext giữa các row), `api_key_hint` (4 ký tự cuối),
   chat model, embedding model, `embedding_fingerprint` = sha256(provider|base_url|model),
   `timeout_seconds` (NULL = dùng `AI_TIMEOUT_SECONDS` toàn cục).
2. **Server proxy mọi lời gọi AI** — extension không bao giờ gọi thẳng provider (giữ ADR-0007),
   key không bao giờ xuất hiện trong response API, log hay `chrome.storage`.
3. **Resolver per-user không sửa adapter**: `build_provider(cfg)` dùng
   `get_settings().model_copy(update={...})` ghi đè các trường `openai_*` / `gemini_*` rồi tạo lại
   `OpenAIClient`/`GeminiClient` sẵn có, bọc trong `CanonicalEmbeddingProvider`. Provider cache
   LRU (64) khoá theo `user_id ‖ provider ‖ base_url ‖ models ‖ timeout ‖ sha256(key)` — luôn có
   `user_id`, không thể chia sẻ provider giữa 2 user. `mode=inherit` trả singleton cũ.
4. **Vector cố định 1536**: model trả < 1536 chiều → **zero-pad** (cosine bất biến: tử số và
   mẫu số không đổi); > 1536 → **từ chối** với thông báo rõ (truncate làm mất chất lượng âm thầm).
5. **Rebuild chỉ mục khi fingerprint embedding đổi**: xoá `note_chunks` của user, đánh
   `index_status='PROCESSING'`, enqueue lại job kèm `embedding_fingerprint`; job cũ fingerprint lệch
   sẽ tự bỏ. Đổi key hoặc chat model → fingerprint không đổi → không rebuild.
6. **`AUTH_MODE=local`** cho self-host một người: `GET /auth/config` công bố `auth_mode`;
   dev-login bỏ qua email client gửi, dùng `LOCAL_AUTH_EMAIL`; JWT/refresh flow giữ nguyên.
   Local mode = **không có xác thực** → bắt buộc bind 127.0.0.1 hoặc đặt sau proxy có auth.
7. Mã hoá key dùng `AI_KEY_SECRET` nếu có, fallback HKDF-SHA256 từ `JWT_SECRET`
   (salt `quickassist`, info `ai-keys-v1`). Xoay `JWT_SECRET` khi chưa đặt `AI_KEY_SECRET`
   → các key đã lưu không giải mã được → user phải nhập lại (ghi runbook).

## Phương án đã loại

- **Extension gọi thẳng provider**: phá ADR-0007, cần `host_permissions` rộng, search/index
  server-side vẫn cần key ở server — không giải quyết được gốc rễ.
- **Vector biến thiên / bỏ HNSW**: phải sửa schema + `_HYBRID_SQL` + repository; chưa cần cho
  model ≤ 1536 chiều.
- **Truncate vector > 1536**: mất chất lượng âm thầm, người dùng không biết search xấu đi.
- **Multi-profile / tách chat-embedding**: nhân đôi UI, rebuild logic và ma trận test, chưa có nhu cầu.
- **KMS/Vault**: quá mức cho self-host; AES-GCM + env secret là đủ.

## Hệ quả

- (+) BYOK và self-host trở thành tính năng thật, cấu hình ngay trong Settings, không sửa `.env`.
- (+) Migration chỉ thêm bảng; không có row → `mode=inherit` → hành vi y hệt hiện tại.
- (−) Thêm bảng + mã hoá + cache provider; đổi model embedding buộc dựng lại toàn bộ chỉ mục
  (trong lúc đó search giảm cấp còn nhánh từ khoá).
- (−) Xoay `JWT_SECRET` (khi không có `AI_KEY_SECRET`) làm mất key đã lưu — phải nhập lại.
- (−) Local mode không có xác thực — rủi ro chuyển xuống tầng triển khai (runbook bắt buộc).
