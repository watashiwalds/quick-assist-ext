# Báo cáo P4 — Extension: RPC ai/config, card Nhà cung cấp AI, auto local-login

> **Ngày:** 2026-11-15 · **Phase:** P4/5 · **Commits:** `72c5bc4` (S1), `e6cb096` (S2), `76348b7` (S3), `b869f52` (S4), `f0b5416` (S5)
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` §7 (P4), §4.7–4.8, §6

## Đã làm (5 slice, mỗi slice 1 commit + test)

### S1 — Regen contract (`72c5bc4`)
- `python scripts/export_openapi.py` (chạy offline, không cần DB) → `docs/api/openapi.json`;
  `npm run gen:api:file` → `schema.d.ts`.
- **Diff thuần additive** (đã verify bằng git diff): 5 endpoint `/me/ai-settings*` + `/auth/config`,
  `QuotaOut` + `billing_mode` (P2), không sửa schema cũ → nghiệm thu #9.
- `types.ts`: `AiSettings`, `AiSettingsInput`, `AiTestResult`, `AuthConfig`…
- Kèm commit báo cáo P0 (lỡ chưa commit ở P0).

### S2 — RPC + auto local-login (`e6cb096`)
- `endpoints.ts`: nhóm `aiSettings: { get, set, remove, test }` + `auth: { devLogin, config }` —
  URL chỉ nằm ở đây (quy ước kiến trúc). `devLogin(email?)`: E2E truyền email riêng từng test
  (isolation user), local mode KHÔNG truyền (server tự dùng `LOCAL_AUTH_EMAIL`, bỏ qua email client).
- `protocol.ts`: `SessionInfo` + `authMode: 'google' | 'local'` (additive); RPC
  `ai/config/get|set|test|reset` — TypeScript bắt thiếu handler lúc biên dịch.
- `handlers.ts`: `sessionInfo()` — chưa có refresh token + `auth_mode=local` → **tự dev-login một
  lần** rồi chạy luồng `signedIn()` (broadcast + refresh folders + flush outbox); lỗi → signed-out,
  lần mở panel sau thử lại. Mọi nhánh trả `authMode`. `e2e/devLogin` dùng chung endpoint (bỏ gọi
  thẳng URL — đúng yêu cầu §4.8).
- ⚠️ **`check-bundle.mjs`: gỡ cấm chuỗi `/auth/dev-login`** — giờ là đường hợp lệ của local mode
  (server vẫn chặn dev-login khi không bật). Giữ chặn `__qaE2E` và nhãn "Đăng nhập thử". Đã chạy
  `npm run check:bundle` trên bản build mới → ✅ đạt.

### S3 — Card "Nhà cung cấp AI" (`76348b7`)
- `ui/features/account/ProviderCard.tsx` (mới), đặt **trên** card "Hạn mức AI":
  1. Preset: OpenAI · Google Gemini · Ollama (local) · LM Studio · llama.cpp · Tuỳ chỉnh — chỉ điền
     giá trị mẫu, mọi ô sửa được (D10);
  2. base_url; api_key password + Hiện/Ẩn + `key_hint` "…a1b2" + nút "Xoá key" (gửi `api_key: ""`);
  3. chat/embedding model + `<datalist>` gợi ý theo preset (D11 — không gọi `/models`);
  4. timeout_seconds trong mục `<details>` "Nâng cao" (placeholder 90);
  5. **Kiểm tra kết nối** → banner xanh: model · dim native · "(sẽ pad về 1536)" · latency · chat
     latency + sample; lỗi → banner đỏ nguyên nhân (stage + message);
  6. **Lưu** → nếu đổi trường liên quan fingerprint (provider/base_url/embedding_model) hoặc lần
     đầu chuyển BYOK và `rebuild_note_count > 0` → `ConfirmDialog` đúng chữ kế hoạch với N ghi chú
     → set → response `rebuild` → **banner tiến độ** ("Đang dựng lại chỉ mục ngữ nghĩa của N ghi
     chú. Tìm kiếm từ khoá vẫn hoạt động…"), toast; đổi key/chat model → không dialog;
  7. **Dùng cấu hình server** (chỉ khi BYOK) → confirm → DELETE → banner.
- Key chỉ nằm trong ô input của form — không storage, không RPC nào khác (test chốt).
- `SettingsView`: nhãn quota theo `billing_mode` — BYOK: "Đã dùng (key của bạn)" + nút "Đặt lại
  số liệu" (D6, không chỉ demo); thanh giới hạn vẫn hiện; local mode **ẩn Đăng xuất**.

### S4 — AuthGate local mode (`b869f52`)
- `authMode === 'local'` + chưa đăng nhập: **ẩn nút Google**, hiện nút "Kết nối lại server"
  (gọi lại `auth/status` → background tự dev-login) + chú thích cảnh báo bảo vệ server.

### S5 — Test UI + sửa lỗi race form (`f0b5416`)
- `tests/ui/provider-card.test.tsx`: 7 test — preset điền mẫu + sửa tay được; test kết nối
  (768→pad 1536); ConfirmDialog đúng N khi đổi model embedding; đổi chat model không dialog;
  semantics key (gõ mới / null giữ / "" xoá); Dùng cấu hình server; lỗi test hiện nguyên nhân.
- **Bug bắt được khi viết test**: form khởi tạo rỗng rồi sync bằng `useEffect` → race (clobber
  khi đang gõ, người dùng phải gõ lại toàn bộ). Sửa bằng **derived state**: form = `fromSaved(data)
  + edits` (chỉ ghi đè ô người dùng đã chỉnh); sau lưu/reset → `cfg.setData(res)` + xoá edits.

## Verify

- ✅ Extension: **173 tests passed** (16 files, +7 mới); `tsc --noEmit` sạch; `npm run build` OK;
  `npm run check:bundle` ✅ (bản phát hành không có key/hook E2E)
- ✅ API: `pytest` 202 passed + ruff sạch (không đổi gì backend ở P4)
- ✅ Kiến trúc: UI không import `shared/api` (tests/architecture.test.ts xanh — UI chỉ gọi RPC;
  dùng type từ `shared/api/types` là được phép)
- ✅ `sessionInfo` có `authMode` ở mọi nhánh; E2E fixture `devLogin(email)` vẫn hoạt động (chung
  endpoint, không đổi fixture)

## Quyết định nhỏ trong phase

- **check-bundle nới lỏng `/auth/dev-login`**: hệ quả tất yếu của yêu cầu §4.8 (local mode cần
  dev-login ở bản phát hành; server-side vẫn chặn khi không bật). Giữ nguyên 2 marker E2E khác.
- **ConfirmDialog theo trường fingerprint phía client**: server mới chốt rebuild thật, dialog chỉ
  để xác nhận trước (so sánh provider/base_url/embedding_model — đúng 3 thành phần của fingerprint).
- **Banner tiến độ** hiện số note + chữ "tìm kiếm từ khoá vẫn hoạt động" (đúng với phương án P3
  giữ chunk cũ); nút Ẩn. Không poll tiến độ thật (không có endpoint đếm job — ngoài phạm vi).
- Form BYOK khi mode=inherit: các ô trống với placeholder từ `server_default`.

## Tiếp theo (P5)

Docs (README, runbook `AUTH_MODE=local` + `AI_KEY_SECRET`, user-guide), `.env.example` ×2,
E2E stub provider (Playwright, tuỳ chọn), test ma trận thủ công + test tổng hợp.

## Đính chính (2026-11-15)

- "202 passed, 137 skipped" là chạy **không có** `TEST_DATABASE_URL`; integration bị skip.
- Với PostgreSQL thật: 14 test đỏ do target monkeypatch/URL cũ (không phải regression sản phẩm).
- `test_full_rebuild_flow` gọi `/ai/search` (đúng là `/search`) nên chưa từng xanh trên DB.
- P5 sửa các mục trên; xem `docs/self_sustained/reports/byok-ease-PRE_P5.md` và báo cáo P5.
