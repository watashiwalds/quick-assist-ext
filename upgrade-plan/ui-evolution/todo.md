# UI Evolution — Danh sách công việc (checklist)

> Kế hoạch tổng thể: xem [`plan.md`](plan.md) cùng thư mục. Mỗi task: **mô tả · nghiệm thu · kiểm chứng · phụ thuộc · phạm vi ước tính**.
> Quy ước cỡ: XS = 1 file · S = 1–2 file · M = 3–5 file · L = 5–8 file (L trở lên phải tách nhỏ).
> Trạng thái cập nhật trực tiếp trên file này khi làm.
> **v2 (2026-11-07):** đổi hướng một responsive extension UI (bỏ web app) — Phase 2 thêm chế độ landscape; Phase 4–5 cũ (web) gộp thành Phase 4 tài liệu.

## Phase 0 — Nền tảng

### Task 0.1: Scaffold npm workspace cho packages mới
**Mô tả:** Thêm `package.json` root ở chế độ workspaces chỉ gồm `packages/*`; không đụng `apps/extension` hay CI hiện hữu.
**Nghiệm thu:**
- [ ] `npm install` ở root tạo workspace link cho `packages/*`
- [ ] `apps/extension` và CI hiện tại không đổi (git diff chỉ thêm file mới)
**Kiểm chứng:** `npm run build` (nếu có) + CI `extension` job vẫn xanh
**Phụ thuộc:** Không · **Phạm vi:** S

### Task 0.2: `packages/api-contract` — kiểu sinh từ OpenAPI
**Mô tả:** Script `gen:api` + output `schema.d.ts` từ `docs/api/openapi.json`; export types dùng chung (Note, NoteCreate, Folder, Quota, SearchHit, TokenPair, User, SummaryPreview, IndexStatus…).
**Nghiệm thu:**
- [ ] Types compile với `tsc --noEmit`
- [ ] Lệnh `gen:api --check` fail khi `openapi.json` đổi mà chưa regenerate (dùng trong CI)
**Kiểm chứng:** CI job mới `api-contract-check` xanh/đỏ đúng như kỳ vọng
**Phụ thuộc:** 0.1 · **Phạm vi:** S

### Task 0.3: `packages/frontend-core` — HTTP client + lỗi + refresh single-flight
**Mô tả:** Port `shared/api/http.ts` (timeout, request-id, map lỗi về `AppError`), `shared/errors.ts` (code→VI), refresh token single-flight với adapter lưu trữ (`chrome.storage`), cắt 20k ký tự, `sanitizeNoteHtml`. Viết mới, giữ hành vi tương đương.
**Nghiệm thu:**
- [ ] Unit test đối chiếu hành vi: 401 TOKEN_EXPIRED → refresh 1 lần → retry; refresh song song bị gộp (single-flight); lỗi map đúng `{code, message, status, requestId}`
- [ ] Không import `chrome.*` (trừ qua adapter) → dùng được ở mọi surface của cùng app (popup/panel/cửa sổ mở rộng)
**Kiểm chứng:** `npm test` trong package
**Phụ thuộc:** 0.2 · **Phạm vi:** M

### Task 0.4: `packages/offline-core` — IndexedDB schema + outbox + sync
**Mô tả:** Port `shared/storage/db.ts` (v2: `notes/outbox/failed/meta`), `background/notes/quick-note.ts` (undo 5s, `notBefore`, retry backoff qua adapter alarm, chuyển `failed` quarantine trong **một transaction**), `background/notes/sync.ts` (cache-first + `updated_since` + tombstone, single-flight).
**Nghiệm thu:**
- [ ] Unit test với `fake-indexeddb`: tạo note → chờ 5s → flush gọi `api.notes.create` đúng payload + `Idempotency-Key`
- [ ] 413/422/hết phiên → mục chuyển sang `failed`, không mất dữ liệu; "Gửi lại" về `outbox` giữ nguyên key
- [ ] Test đối chiếu với extension hiện tại (cùng fixture) — kết luận parity
**Kiểm chứng:** `npm test` trong package
**Phụ thuộc:** 0.2, 0.3 · **Phạm vi:** M→L (tách 0.4a db/outbox, 0.4b sync nếu cần)

### Task 0.5: `packages/design-system` — tokens + density + component primitives
**Mô tả:** Tokens (color/type/spacing/radius/elevation) ở 2 mật độ `compact` (portrait — panel hẹp) và `cozy` (landscape — cửa sổ mở rộng/panel kéo rộng) cho **cùng một app**; ngưỡng container query đặt trong token. Component: Button, Input/Textarea, Card, Modal, Toast, Tabs, State (empty/loading/error), NoteCard, QuotaMeter. Placeholder dark tokens theo hiện trạng; cấu trúc sẵn sàng nhận token từ Figma.
**Nghiệm thu:**
- [ ] `tsc --noEmit` sạch; mỗi component có tối thiểu 1 vitest + Testing Library render test
- [ ] Density chuyển bằng token + container query (không fork component)
- [ ] Kitchen&#8209;sink page (route dev) liệt kê mọi component × density × 2 chiều rộng mẫu (400px / 1000px)
**Kiểm chứng:** `npm test` + mở kitchen-sink page
**Phụ thuộc:** 0.1 · **Phạm vi:** L (tách theo nhóm component nếu >8 file)

### Checkpoint: Phase 0
- [ ] Tất cả packages build + test xanh; CI có job cho packages mới
- [ ] `git diff -- apps/` **rỗng**
- [ ] Duyệt với tech lead trước khi sang Phase 1

## Phase 1 — Extension v2: background tương đương

### Task 1.1: Scaffold `apps/extension-v2/` + manifest từ env
**Mô tả:** Vite + CRXJS + React 19 + TS; `manifest.config.ts` (MV3): `contextMenus, storage, identity, scripting, activeTab, alarms, sidePanel`; host_permissions chỉ API origin; CSP strict; lệnh QuickAssist; pinned key **chỉ** bật khi `VITE_EXTENSION_KEY` có (cutover). Không thêm permission mới — cửa sổ mở rộng dùng `chrome.windows.create` (không cần quyền).
**Nghiệm thu:**
- [ ] Build ra `dist/`; extension nạp được (unpacked) với dev key
- [ ] `check:bundle` (port ở Task 3.2) chưa cần ở bước này, nhưng cấu trúc phải cho phép
**Kiểm chứng:** `npm run build` + load unpacked thành công
**Phụ thuộc:** Phase 0 · **Phạm vi:** M

### Task 1.2: Auth PKCE + token vault
**Mô tả:** Port `background/auth/google.ts` (launchWebAuthFlow, state/nonce/verifier), `auth/session.ts` (access JWT → `chrome.storage.session`, refresh → `chrome.storage.local`, clear khi logout/delete-account, R-10 wipe), refresh single-flight dùng `frontend-core`.
**Nghiệm thu:**
- [ ] Đăng nhập E2E dev-login hoạt động; refresh tự xoay khi access hết hạn
- [ ] Unit test: logout xoá sạch storage; REFRESH_REUSED → clearAll
**Kiểm chứng:** `npm test` (fixture chrome giả lập)
**Phụ thuộc:** 1.1 · **Phạm vi:** M

### Task 1.3: RPC có kiểu + handlers + broadcast
**Mô tả:** `shared/messaging/protocol.ts` tương đương (`RpcMap`, `RpcResponse`, `BroadcastEvent`), `background/handlers.ts` đầy đủ mọi RPC (thiếu = lỗi biên dịch), broadcast `notes/changed|folders/changed|outbox/changed|selection/pending|session/changed`.
**Nghiệm thu:**
- [ ] `tsc` fail khi thiếu bất kỳ handler nào (kiểm bằng thử xoá 1 handler — build phải đỏ)
- [ ] RPC trả đúng shape `{ok:true,data}|{ok:false,error}`
**Kiểm chứng:** build + 1 test cố tình fail/pass
**Phụ thuộc:** 1.2 · **Phạm vi:** M

### Task 1.4: Outbox + undo 5s + failed quarantine trong background
**Mô tả:** Dùng `offline-core`; flush qua `chrome.alarms` (FLUSH_ALARM 1 phút + trigger khi login); `quickNote/undo`; banner dữ liệu "N ghi chú chưa gửi được"; retry/discard; xoá thư mục đích → gửi vào Inbox.
**Nghiệm thu:**
- [ ] Ghi chú tạo → 5s undo được; hết 5s → gửi lên server với `Idempotency-Key` = outbox id
- [ ] 413/hết phiên → vào `failed`; UI liệt kê được; Gửi lại không tạo trùng
**Kiểm chứng:** U/test port từ extension hiện tại (`tests/outbox`, `tests/quick-note`)
**Phụ thuộc:** 1.3, 0.4 · **Phạm vi:** M

### Task 1.5: Sync cache-first + context menus + phím tắt
**Mô tả:** `syncNotes()` single-flight với `updated_since`; menu "QuickAssist ▸ Ghi chú văn bản này / Ghi chú vào thư mục ▸ / Tóm tắt ▸"; `Alt+Shift+N` / `Alt+Shift+Z`; `page-actions.ts` + `content/injected.ts` (tự chứa, không import).
**Nghiệm thu:**
- [ ] Sync tăng dần, áp tombstone (`deleted_at` → xoá cache), không lặp vô hạn
- [ ] Phím tắt hiển thị đúng trong `chrome://extensions/shortcuts`; injected đọc đúng vùng chọn
**Kiểm chứng:** E2E `n07` (port) pass
**Phụ thuộc:** 1.4 · **Phạm vi:** M

### Task 1.6: Port architecture tests
**Mô tả:** `tests/architecture.test.ts`: ui↛background/shared-storage, content cô lập, shared thuần, background↛ui.
**Nghiệm thu:**
- [ ] Vi phạm cố ý (import chéo) làm test đỏ
**Kiểm chứng:** chạy suite, quan sát fail/pass
**Phụ thuộc:** 1.1 · **Phạm vi:** XS

### Checkpoint: Phase 1
- [ ] Extension v2 chạy được: đăng nhập, tạo ghi chú (undo 5s), search, xoá; test Phase 1 xanh
- [ ] `apps/api` & `infra` không bị sửa

## Phase 2 — Extension v2: UI responsive 2 chế độ (Figma-gated)

### Task 2.1: Popup mới — capture + quota glance
**Mô tả:** Popup nhỏ gọn: trạng thái đăng nhập, nút "Ghi chú đoạn đã chọn", quota meter, link mở side panel, nút "Mở rộng" (cửa sổ landscape — cùng Task 2.7).
**Nghiệm thu:**
- [ ] Mọi trạng thái: signed-out / signed-in / offline (hiển thị từ cache) / đang flush
- [ ] Nút "Mở rộng" mở đúng cửa sổ landscape (deep-link route mặc định)
- [ ] Snapshot/RTL test cho từng trạng thái
**Kiểm chứng:** vitest
**Phụ thuộc:** Phase 1 · **Phạm vi:** S

### Task 2.2: Side panel (portrait) — khung lưới modular
**Mô tả:** Layout lưới module: Library (mặc định) / Search / Summary / Settings / Chat-stub; chuyển tab bằng Tabs component; responsive trong panel width 360–480px. **Chừa sẵn slot tab "Tìm trong trang"** cho AutoChunk (`docs/plan/autochunk/`) — không implement tính năng ở đây.
**Nghiệm thu:**
- [ ] Không cuộn ngang ở width tối thiểu; focus order đúng (a11y)
- [ ] Route hash ↔ tab ánh xạ đúng (dùng chung cho cửa sổ landscape)
- [ ] Axe (qua test) không vi phạm cơ bản
**Kiểm chứng:** vitest + axe test
**Phụ thuộc:** 2.1 · **Phạm vi:** M

### Task 2.3: Module Library + Quarantine banner
**Mô tả:** Danh sách ghi chú cache-first, filter thư mục, trạng thái `index_status`, banner "N ghi chú chưa gửi được" với Gửi lại / Bỏ, xoá hàng loạt, reindex. Portrait: editor là modal. Landscape: **split-view danh sách ↔ reader/editor** (modal chỉ còn cho confirm/409).
**Nghiệm thu:**
- [ ] Khớp hành vi extension hiện tại + UI mới ở cả 2 chế độ; 409 → hộp thoại tải bản mới
**Kiểm chứng:** vitest + E2E `c05` (port)
**Phụ thuộc:** 2.2 · **Phạm vi:** M

### Task 2.4: Module Search (hybrid, có nguồn)
**Mô tả:** Ô tìm kiếm debounce, filter folder, kết quả kèm nguồn (title/url), mở side panel note tương ứng. Landscape: kết quả ↔ xem trước hiển thị cạnh nhau (split-view).
**Nghiệm thu:**
- [ ] Enter/click kết quả mở đúng note; hiển thị điểm/rank; empty state đẹp
- [ ] Split-view landscape hiển thị đúng nguồn + xem trước
**Kiểm chứng:** vitest + E2E `r05` (port)
**Phụ thuộc:** 2.2 · **Phạm vi:** S

### Task 2.5: Module Summary (preview → xác nhận → lưu)
**Mô tả:** Chọn note/vùng chọn → preview tóm tắt (AI, gọi `/ai/summaries`) → người dùng xác nhận → lưu vào note (`PUT /notes/{id}/summary`). Landscape: preview và nội dung nguồn hiển thị cạnh nhau.
**Nghiệm thu:**
- [ ] Không tự ghi khi chưa xác nhận; lỗi 402 → hiện quota UI + link Settings
- [ ] Layout portrait (stacked) và landscape (split) đều đúng
**Kiểm chứng:** vitest + E2E `sum-a08` (port)
**Phụ thuộc:** 2.2 · **Phạm vi:** M

### Task 2.6: Module Settings + Chat-stub
**Mô tả:** Settings: profile, quota, xoá tài khoản (full confirm), prefs (thư mục mặc định). Chat-stub: màn hình chat đẹp, gọi `/ai/chat`, nhận `501 CHAT_NOT_IMPLEMENTED` → trạng thái "Tính năng chưa hỗ trợ" + giải thích. Landscape: layout hội thoại rộng.
**Nghiệm thu:**
- [ ] Xoá tài khoản wipe storage + gọi `DELETE /me`; chat-stub hiển thị đúng 501 path
**Kiểm chứng:** vitest
**Phụ thuộc:** 2.2 · **Phạm vi:** M

### Task 2.7: Chế độ landscape — cửa sổ mở rộng + panel kéo rộng
**Mô tả:** Nút "Mở rộng" ở header panel + popup → `chrome.windows.create({type:'popup', url:'index.html#/…', width:1000, height:760})` mở **cùng React app** (deep-link mở đúng module/ghi chú); nhớ kích thước cửa sổ lần trước (`storage.local`); tuỳ chọn "Mở trong tab". Ngưỡng container query (token, ~560px) đổi layout + mật độ compact↔cozy — áp dụng cho cả cửa sổ mở rộng lẫn side panel bị kéo rộng (Chrome tự lưu width người dùng). Trạng thái panel ↔ cửa sổ đồng bộ qua broadcast `qa-event` sẵn có.
**Nghiệm thu:**
- [ ] Nút "Mở rộng" mở cửa sổ đúng route; deep-link `#/note/:id` mở đúng ghi chú
- [ ] Kéo panel qua ngưỡng → layout + mật độ đổi, không cuộn ngang, không mất trạng thái form
- [ ] Panel + cửa sổ mở đồng thời: thao tác ở một surface cập nhật ở surface kia (broadcast)
- [ ] Axe sạch ở cả 2 mật độ
**Kiểm chứng:** vitest + axe
**Phụ thuộc:** 2.2 · **Phạm vi:** M

### Checkpoint: Phase 2
- [ ] UI 2 chế độ (portrait/landscape) hoàn chỉnh theo Figma (hoặc placeholder) — duyệt với người thiết kế
- [ ] Axe sạch ở cả portrait và landscape; E2E port xanh: `n07 r05 c05 sum-a08 h05-a11y ux-screens`

## Phase 3 — Extension v2: QA & cutover

### Task 3.1: Port toàn bộ vitest suites
**Mô tả:** Port `tests/ui/*`, `tests/outbox|sync|session|injected`, tương phản màu, `tests/helpers/chrome.ts`, `tests/architecture.test.ts`; cấu trúc thư mục tương đương `apps/extension`.
**Nghiệm thu:**
- [ ] Số test tương đương hoặc cao hơn extension hiện tại; tất cả xanh trong CI job mới
**Kiểm chứng:** CI job `extension-v2` xanh
**Phụ thuộc:** Phase 2 · **Phạm vi:** M

### Task 3.2: `scripts/check-bundle.mjs` v2 + `package.mjs`
**Mô tả:** Port bundle security scan (không secret, không quyền thừa, không hook `VITE_E2E`); script đóng gói zip.
**Nghiệm thu:**
- [ ] Bản release (không `VITE_E2E`) không chứa chuỗi dev/hook; CI chạy scan sau build
**Kiểm chứng:** CI + chạy tay scan trên `dist/`
**Phụ thuộc:** 3.1 · **Phạm vi:** S

### Task 3.3: Playwright E2E v2 + axe
**Mô tả:** Reuse fixtures (`fixtures.ts`, `serve.mjs`), spec port: `n07-quick-note`, `r05-search`, `c05-library`, `sum-a08`, `h05-a11y`, `ux-screens`; cấu hình `build:e2e` với `VITE_E2E=true`. Thêm spec landscape: mở trang v2 như tab (Playwright điều khiển được), kiểm split-view + deep-link; axe chạy ở 2 chiều rộng mẫu (400px / 1000px).
**Nghiệm thu:**
- [ ] 28+ test E2E xanh trên Chromium + API/worker thật (AI mock), gồm kịch bản landscape
**Kiểm chứng:** `npm run test:e2e` local/CI
**Phụ thuộc:** 3.2 · **Phạm vi:** M

### Task 3.4: Cutover store + rollback
**Mô tả:** Gắn pinned key, bump `version`, build release, submit Chrome Web Store; tag `extension-v1.0.0` (bản cũ) để rollback; cập nhật redirect URI/CORS (nếu key đổi — với pinned key thì không); thông báo team.
**Nghiệm thu:**
- [ ] Store duyệt version mới; extension cũ vẫn cài được từ tag cũ; demo script chạy với v2
**Kiểm chứng:** smoke test sau publish
**Phụ thuộc:** 3.3 + soak ≥ 3 ngày · **Phạm vi:** S

### Checkpoint: Phase 3
- [ ] Extension v2 live trên store; rollback khả dụng; docs/ADR cập nhật (Phase 4)

## Phase 4 — Tài liệu & đóng kế hoạch

### Task 4.1: ADR + cập nhật docs
**Mô tả:** ADR-0014 (một responsive extension UI: 2 chế độ container-query, cửa sổ mở rộng, design system 2 mật độ, packages workspace). **Giải trừ trùng số ADR: ADR-0012 dành cho AutoChunk** ("Page segmentation in content script" — `docs/plan/autochunk/`). Cập nhật `docs/architecture/README.md`; `docs/ux/ui-map.md` + deck `docs/presentation/` cập nhật sau cutover.
**Nghiệm thu:**
- [ ] ADR đúng khuôn (Bối cảnh→Quyết định→Phương án loại→Hệ quả); docs review bởi owner tương ứng
- [ ] Không còn hai kế hoạch nào dùng chung một số ADR
**Kiểm chứng:** review PR
**Phụ thuộc:** 3.4 · **Phạm vi:** S

### Task 4.2: Đóng kế hoạch
**Mô tả:** Cập nhật `plan.md` (trạng thái → hoàn thành), thông báo đội.
**Nghiệm thu:**
- [ ] Mọi checkbox phase 0–4 được tick hoặc ghi chú hoãn + lý do
**Kiểm chứng:** xem `todo.md` cuối cùng
**Phụ thuộc:** 4.1 · **Phạm vi:** XS

### Checkpoint: Hoàn thành
- [ ] Tất cả nghiệm thu đạt; backend/DB/infra diff rỗng; báo cáo cuối cho team

## Chuẩn hoá kiểm chứng chung

| Loại | Lệnh |
|---|---|
| Backend | `pytest -q` · `ruff check` · `alembic check` (không đổi code nhưng chạy để xác nhận) |
| Extension v2 | `npm test` · `npm run build` · `npm run check:bundle` · `npm run test:e2e` |
| Contract | `node packages/api-contract/bin/gen.mjs --check` (hoặc tương đương) |

## Ghi chú triển khai

- **Figma:** chưa có file hoàn chỉnh — mọi task UI dùng placeholder tokens; khi Figma về, chỉ cập nhật token cho cả 2 mật độ (portrait/landscape), không đổi API nhiệm vụ.
- **Dev key vs pinned key:** phát triển/CI dùng dev key; chỉ build release cutover mới gắn `VITE_EXTENSION_KEY` (pinned).
- **Chat:** mọi nơi hiển thị "chưa hỗ trợ" cho 501; X01 là task riêng nếu được duyệt (~3–4 tuần, phá ràng buộc backend bất biến — cần quyết định riêng).
- **Side panel width:** Chrome không có API set/chỉnh width side panel (Chromium issue 416840970) — "mở rộng tự động" thực hiện bằng cửa sổ popup (`chrome.windows.create`, không cần permission); "kéo rộng tay" do Chrome tự lưu cho người dùng; mọi chuyển layout theo container query.
- **AutoChunk:** `PageFinderView` thuộc kế hoạch `docs/plan/autochunk/` — khuyến nghị bắt đầu sau Phase 2 (shell v2 ổn định) để xây thẳng trên UI mới, không xây trên sidepanel hiện tại rồi phải port. Kế hoạch đó giữ ADR-0013 (đã implement 10/11/2026 trên sidepanel hiện tại — khi làm v2 cần port `PageFinderView`).
