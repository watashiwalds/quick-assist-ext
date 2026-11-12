# Kế hoạch UI Evolution — QuickAssist

> **Trạng thái:** Đã chốt phạm vi, chưa triển khai · **Ngôn ngữ:** Tiếng Việt · **Phạm vi:** chỉ tài liệu kế hoạch trong thư mục này — không động tới code hiện có.
> Nguồn: thảo luận kế hoạch (plan mode) trên repo `quick-assist-ext`. Ngày: 2026-11-06.
> **v2 (2026-11-07):** đổi hướng sau phỏng vấn intent — **một responsive extension UI (2 chế độ portrait/landscape) thay cho extension UI + web UI**. Web app bị loại; lý do chi tiết tại §1.1.

## 1. Tóm tắt

Sinh ra **một frontend mới duy nhất**, **không đổi một dòng code backend/database hiện tại**:

1. **Extension v2** — UI mới theo ngôn ngữ thiết kế compact, "modular-feeling", responsive **hai chế độ trên cùng một React app**:
   - **Portrait** — side panel hẹp (360–480px), mật độ `compact`, tabs: Thư viện / Tìm kiếm / Tóm tắt / Cài đặt (+ chat-stub).
   - **Landscape** — cùng app trải rộng, mật độ `cozy`, layout split-view cho các tác vụ nhiều nội dung (thư viện + đọc/sửa, thư mục & thao tác hàng loạt, tóm tắt, chat-stub, slot AutoChunk "Tìm trong trang"). Mở bằng **nút "Mở rộng"** (cửa sổ riêng ~900–1100px qua `chrome.windows.create` — không cần permission mới) hoặc do **người dùng kéo rộng side panel** (Chrome tự nhớ width).

**Web app riêng (theo v1) bị loại** vì: mọi tính năng nó định phục vụ đã tồn tại trong extension (kiểm kê `docs/ux/ui-map.md`); không có kịch bản truy cập không-cài-extension (đã xác nhận); tiết kiệm ~2–3 tuần và toàn bộ hệ sinh thái deploy web (subdomain, Caddy, OAuth web).

Hiện trạng tái sử dụng: toàn bộ `apps/api` + PostgreSQL/pgvector + `/api/v1` (hợp đồng OpenAPI `docs/api/openapi.json`) được giữ nguyên — **kể cả biến môi trường** (v1 cần thêm CORS/redirect cho web; v2 không cần gì). Extension v2 giữ **đúng pinned key** ⇒ cùng Extension ID với extension hiện tại.

```
                 ┌─────────────────────────────┐
                 │   apps/api + Postgres        │  ← BẤT BIẾN: không đổi code/env
                 │   /api/v1 (OpenAPI contract) │
                 └─────────────▲───────────────┘
                               │ Bearer JWT + Idempotency-Key (chỉ background)
        ┌──────────────────────┼───────────────────────────┐
        │                      │                           │
┌───────┴────────┐   ┌─────────┴─────────┐     ┌───────────┴─────────┐
│ Popup toolbar  │   │ Side Panel        │     │ Cửa sổ Mở rộng      │
│ capture + quota│   │ PORTRAIT          │     │ LANDSCAPE           │
│ nút "Mở rộng"  │   │ compact, 360–480  │     │ cozy, 900–1100      │
│                │   │ kéo rộng →        │     │ nút "Mở rộng" →     │
│                │   │ landscape         │     │ chrome.windows      │
└────────────────┘   └───────────────────┘     └─────────────────────┘
        ▲                     ▲                          ▲
        │ một React app · design tokens: compact | cozy   │
        └─────────────────────┴──────────────────────────┘
              packages MỚI: api-contract · frontend-core ·
              offline-core · design-system

 (apps/extension hiện tại — giữ cho tới khi cutover)
```

## 1.1 Statement of Intent (đã xác nhận 2026-11-07)

| Mục | Nội dung |
|---|---|
| **Outcome** | Một frontend duy nhất: Extension v2 responsive, 2 mode — portrait (side panel hẹp, tabs) và landscape (nút "Mở rộng" → cửa sổ riêng ~1000px, hoặc user kéo rộng panel — Chrome tự nhớ width) — mọi tính năng dùng thoải mái ở cả hai. |
| **User** | Nhóm + người dùng QuickAssist; demo/chấm điểm đều trên máy có cài extension. |
| **Why now** | Kế hoạch 7–9 tuần quá nặng so với tiến độ HK9; đang ở giai đoạn kế hoạch (chưa viết code) — thời điểm đổi hướng rẻ nhất. |
| **Success** | Thư viện/sửa/tìm kiếm/tóm tắt/thư mục–hàng loạt/chat-stub **và AutoChunk** đều thoải mái ở cả 2 mode; parity tests + E2E port + axe xanh; tổng effort ~5–6 tuần (thay vì 7–9). |
| **Constraint** | `apps/api` + DB bất biến; side panel không tự resize bằng API → "tự động" = cửa sổ popup; AutoChunk nhắm thẳng vào UI v2 (không xây trên sidepanel cũ rồi vứt); design system 2 mật độ: `compact` = portrait, `cozy` = landscape. |
| **Out of scope** | Web app (`apps/web`, Caddy, OAuth web, ADR web frontend), truy cập không-extension, offline web, backend chat/RAG thật (chat vẫn stub 501). |

Câu hỏi mở (không chặn kế hoạch): thứ tự AutoChunk ↔ Extension v2 (khuyến nghị: sau Phase 2); popup window hay tab làm landscape mặc định (khuyến nghị: popup, tab là tuỳ chọn); đã giải trừ trùng số ADR-0012 (nhường AutoChunk, xem Phase 4).

## 2. Ràng buộc đã chốt

| Ràng buộc | Hệ quả |
|---|---|
| Backend/DB bất biến, không đổi code **và env** | Mọi tích hợp đi qua JWT Bearer + `/api/v1`; ghi luôn kèm `Idempotency-Key`; CI sinh lại contract từ `openapi.json`, lệch = build đỏ |
| Chrome Side Panel API **không cho set/chỉnh width từ code** (Chromium issue 416840970) | "Mở rộng tự động" = `chrome.windows.create({type:'popup'})` mở cùng React app (không cần permission mới); "kéo rộng tay" = người dùng tự kéo, Chrome tự lưu; UI chuyển layout bằng container query theo chiều rộng container |
| Extension v2 tái sử dụng pinned key | Extension cũ và v2 **không cài song song được trên một profile Chrome** — phát triển song song dùng dev key, lúc cutover/store mới gắn pinned key; extension hiện tại giữ làm đường rollback |
| Chat = stub | Ship UI chat sẵn sàng nhưng hiển thị trạng thái "chưa hỗ trợ" khi `501 CHAT_NOT_IMPLEMENTED`; backend RAG (task X01) là hạng mục **ngoài phạm vi** kế hoạch này |
| Figma chưa có (wireframe một phần, extension) | Design system ship với placeholder dark tokens cho cả 2 mật độ; chỉ polish cuối Phase 2 mới bị Figma chặn; đổi tokens = đổi 1 file, không viết lại component |
| QA phải phủ đủ 2 chế độ | Không CI-green (architecture tests, bundle scan, E2E, axe ở cả portrait + landscape) ⇒ không cutover |
| AutoChunk dùng chung shell | `PageFinderView` (kế hoạch `docs/plan/autochunk/`) xây trên shell v2 — kế hoạch này chỉ chừa slot tab + pattern layout, không implement tính năng |
| Không chỉnh sửa file ngoài kế hoạch | Kế hoạch này chỉ tạo/sửa file trong `docs/plan/ui-evolution/`; code hiện hữu (`apps/*`, `infra/*`) không bị sửa trong bước lập kế hoạch |

## 3. Kiến trúc đề xuất

### 3.1 Package dùng chung (mới, trong repo)

| Package | Nội dung | Ghi chú |
|---|---|---|
| `packages/api-contract` | Kiểu TypeScript sinh từ `docs/api/openapi.json` (`schema.d.ts`) | Một lệnh `gen:api`; CI chạy `--check` |
| `packages/frontend-core` | HTTP client factory (timeout, `X-Request-ID`, map lỗi), `AppError` + map code→tiếng Việt, refresh token single-flight có adapter lưu trữ (`chrome.storage`), cắt 20.000 ký tự, sanitize HTML, tiện ích chung | Port từ `apps/extension/src/shared/` hiện tại — viết mới, hành vi tương đương, có unit test đối chiếu |
| `packages/offline-core` | Schema IndexedDB v2 (`notes/outbox/failed/meta`), outbox 5s undo, sync cache-first `updated_since` kèm tombstone | Chỉ extension v2 dùng |
| `packages/design-system` | Design tokens 2 mật độ: `compact` (portrait) và `cozy` (landscape) + component React (Button, Input, Modal, Toast, Tabs, NoteCard, QuotaMeter, EmptyState…) | React 19 + TS, cùng stack hiện tại; chuyển mật độ theo container query, **không fork component** |

Workspace npm mới ở root **chỉ gồm `packages/*`** — không đụng `apps/extension` (CI hiện tại giữ nguyên).

### 3.2 Extension v2 (`apps/extension-v2/`)

- Manifest MV3 sinh từ env (`manifest.config.ts` tương tự hiện tại); dev key lúc phát triển, pinned key khi cutover. **Không thêm permission mới** — `chrome.windows.create`/`chrome.tabs.create` không cần quyền.
- Background service worker viết lại trên `frontend-core` + `offline-core`: đăng nhập Google PKCE, token vault (`chrome.storage.session` cho access JWT, `chrome.storage.local` cho refresh), RPC có kiểu (`RpcMap` chỉ đầy đủ handler mới biên dịch), outbox ghi→ flush bằng `chrome.alarms`, **hoàn tác 5 giây**, **quarantine `failed` store** + banner "N ghi chú chưa gửi được", sync cache-first `updated_since` với tombstone, context menu "Ghi chú vào thư mục ▸", phím tắt `Alt+Shift+N` (ghi chú nhanh) / `Alt+Shift+Z` (hoàn tác), side panel behavior.
- **Toàn bộ hợp đồng hành vi tương đương extension hiện tại** (outbox + undo + failed store là bất biến) — chỉ ngôn ngữ thiết kế và tổ chức UI là mới.
- Popup: capture + quota glance; nút "Mở thư viện" (panel) + nút "Mở rộng" (cửa sổ landscape).
- Side panel (portrait): lưới modular tabs — Thư viện / Tìm kiếm / Tóm tắt* / Cài đặt / Chat-stub; chừa slot "Tìm trong trang" (AutoChunk). (*Tóm tắt chỉ hiện khi có vùng chọn chờ — như hiện tại.)
- **Cửa sổ Mở rộng (landscape):** nút ở header panel + popup → `chrome.windows.create({type:'popup', url:'index.html#/…'})` — deep-link mở đúng module/ghi chú; nhớ kích thước lần trước qua `storage.local`; tuỳ chọn "Mở trong tab". Trạng thái panel ↔ cửa sổ đồng bộ bằng broadcast `qa-event` sẵn có.

### 3.3 Chế độ landscape & responsive

- Ngưỡng container query (~560px, đặt trong token) quyết định portrait/landscape theo **chiều rộng container** — áp dụng cho cả side panel bị kéo rộng lẫn cửa sổ mở rộng; popup toolbar luôn compact.
- Landscape = split-view: Thư viện (danh sách ↔ reader/editor — thay modal editor), Tìm kiếm (kết quả ↔ xem trước), Thư mục & thao tác hàng loạt, Tóm tắt (nguồn ↔ preview), Chat-stub; Modal chỉ còn cho confirm/409/xoá tài khoản.
- Một codebase, một bộ route hash (`#/library`, `#/note/:id`, `#/search`, `#/summary`, `#/settings`, `#/chat`); side panel ánh xạ route ↔ tab.
- AutoChunk: slot tab "Tìm trong trang" + pattern layout danh sách đoạn (checkbox, badge, lưu N đoạn) sẵn sàng ở cả 2 chế độ — tính năng do kế hoạch `docs/plan/autochunk/` triển khai.

## 4. Các giai đoạn (vertical slices)

> Chi tiết nghiệm thu từng task: xem `todo.md` trong thư mục này.

**Phase 0 — Nền tảng (~1 tuần).** Scaffold workspace, `api-contract`, `frontend-core` + unit test đối chiếu hành vi hiện tại, `offline-core`, `design-system` (2 mật độ cho cùng một app), CI job cho packages mới.

**Phase 1 — Extension v2: background tương đương (~1–1,5 tuần).** Scaffold `apps/extension-v2/`, manifest, background PKCE/vault/outbox/undo/failed/sync/menus/shortcuts/RPC; port `architecture.test.ts` (ui ↛ background, content cô lập, shared thuần).

**Phase 2 — Extension v2: UI responsive 2 chế độ (~2–2,5 tuần, Figma-gated).** Popup + side panel portrait trên design system; chế độ landscape (cửa sổ mở rộng + panel kéo rộng) với split-view cho các module nhiều nội dung; toasts, hộp thoại 409, trạng thái rỗng/loading; placeholder tokens cho tới khi Figma về.

**Phase 3 — Extension v2: QA & cutover (~1 tuần + soak).** Port vitest suites (outbox/undo/sync/session/injected/UI/contrast), `check:bundle` bản v2 (không secret/hook kiểm thử, quyền tối thiểu), Playwright E2E tái sử dụng (`n07`, `r05`, `c05`, `sum-a08`, `h05-a11y`, `ux-screens`) **+ spec landscape**; axe WCAG AA **ở cả 2 chế độ**; dogfood soak, **store publish bằng pinned key**, giữ bản cũ làm rollback.

**Phase 4 — Tài liệu & đóng kế hoạch (~0,5 tuần).** ADR-0013 (một responsive extension UI: 2 chế độ container-query, cửa sổ mở rộng, design system 2 mật độ, packages workspace); **giải trừ trùng số ADR: ADR-0012 dành cho AutoChunk** ("Page segmentation in content script" — theo `docs/plan/autochunk/`); cập nhật `docs/architecture/README.md` (+ `docs/ux/ui-map.md`, deck sau cutover); đóng checklist.

Thứ tự: **Phase 0 → 4.** AutoChunk (T1–T6 của kế hoạch riêng) khuyến nghị bắt đầu sau Phase 2 khi shell v2 ổn định, để `PageFinderView` xây thẳng trên UI v2 thay vì sidepanel hiện tại.

## 5. Nỗ lực ước tính

| Hạng mục | Ước tính |
|---|---|
| Phase 0 — Nền tảng | ~1 tuần |
| Phase 1 — ext2 background | ~1–1,5 tuần |
| Phase 2 — ext2 UI responsive 2 chế độ | ~2–2,5 tuần |
| Phase 3 — ext2 QA & cutover | ~1 tuần + soak |
| Phase 4 — Tài liệu & đóng kế hoạch | ~0,5 tuần |
| **Tổng** | **~5–6 tuần** (bán thời gian, 4 người) — giảm ~2–3 tuần so với v1 (7–9 tuần) |

Figma về trễ ⇒ chỉ Phase 2 kéo dài; mọi phase khác không phụ thuộc Figma.

## 6. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Pinned key ⇒ không cài song song bản cũ/mới | Trung bình | Dev key cho bản v2; dogfood bằng hoán đổi thủ công; cutover = publish store; bản cũ gắn tag rollback |
| Figma về trễ / chỉ có wireframe | Trung bình | Token-driven density; màn thiếu do tự thiết kế trong repo + xin duyệt; không chặn Phase 0–1, 3, 4 |
| Lệch hợp đồng API | Trung bình | `api-contract` sinh từ `openapi.json` + CI `--check`; lệch ⇒ build đỏ ⇒ revert app, không sửa backend |
| Mất bất biến "không mất ghi chú" khi port | Cao | Outbox + undo + failed quarantine là spec viết cứng trong Phase 1 với test port từ extension hiện tại; E2E `n07` chặn merge |
| Hai chế độ portrait/landscape lệch nhau | Thấp | Một design system token-driven; review mọi component ở cả 2 mật độ; axe + E2E chạy ở 2 chiều rộng mẫu |
| Cửa sổ mở rộng ít được phát hiện / ít dùng | Trung bình | Nút "Mở rộng" nổi bật ở header panel + popup; đo lường trong dogfood; demo script có cảnh landscape |
| Panel và cửa sổ mở cùng lúc lệch trạng thái | Thấp | Broadcast `qa-event` sẵn có; test 2 surface đồng thời trong Phase 2 |
| Chat bị kỳ vọng nhưng 501 | Trung bình | Truyền thông rõ trong kế hoạch; UI stub có trạng thái đẹp; X01 là task riêng, ước tính riêng (~3–4 tuần nếu được duyệt) |

## 7. Ngoài phạm vi (không làm trong kế hoạch này)

- Thay đổi code backend/database dưới mọi hình thức, **kể cả biến môi trường** (RAG/X01, cookie session, httpOnly auth — v1 cần thêm env cho web; v2 không cần gì).
- **Web app & mọi biến thể:** `apps/web`, subdomain `app.<domain>`, Caddy static block, OAuth web flow, offline web.
- **Truy cập không-cài-extension** (đã xác nhận không có nhu cầu thật).
- **Triển khai tính năng AutoChunk** — kế hoạch này chỉ chừa slot UI; xem `docs/plan/autochunk/`.
- Tự động deploy CD (vẫn theo `docs/deploy/runbook.md` thủ công).
- Thiết kế Figma (chỉ tiêu thụ; do người phụ trách thiết kế).
- Tách microservices, đổi database, đổi nhà cung cấp AI.

## 8. Điều kiện hoàn thành (Definition of Done)

- Extension v2: parity hành vi (outbox/undo/failed/sync) được chứng minh bằng test port + E2E xanh; **axe không vi phạm WCAG AA ở cả portrait và landscape**; bundle scan sạch; store publish thành công; bản cũ tagged làm rollback.
- **Landscape đầy đủ:** mọi module dùng được ở cả 2 chế độ; Thư viện/Tìm kiếm/Thư mục/Tóm tắt/Chat có layout split-view; nút "Mở rộng" + deep-link hoạt động; panel ↔ cửa sổ không lệch trạng thái.
- Backend/DB/infra: `git diff` trên `apps/api/` và `infra/` **rỗng hoàn toàn**.
- Kế hoạch & trạng thái cập nhật trong thư mục này (`plan.md`, `todo.md`).
