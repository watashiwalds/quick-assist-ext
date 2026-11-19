# Báo cáo triển khai P5 — Hardening: component/token dùng chung, a11y, ADR, kiểm chứng độc lập

> Nguồn: `docs/self_sustained/ux_improvement_plan.md` §5.5, §11 checklist Phase 5, §12 rủi ro  
> Ngày: 18/11/2026 · Nhánh: `son-test-dev`  
> Trạng thái: **Hoàn tất phần code + tài liệu** — 7 commit triển khai (chưa kể commit báo cáo này),
> typecheck/test/build extension và ruff/pytest API xanh; e2e/integration + eval ngưỡng vẫn
> **cần PostgreSQL + Docker/Playwright** (máy dev không chạy được, xem §3.2).

## 1. Phạm vi đã làm

| # | Hạng mục | Commit | File chính |
|---|---|---|---|
| 1 | Sửa đếm ghi chú tìm kiếm theo `note_count` của nguồn | `619c381` | `NotesView.tsx`, `SearchView.tsx`, `searchSummary.ts`, `search-summary.test.ts`, `ui.test.tsx` |
| 2 | `ConfidenceBadge` dùng chung cho Tìm trong trang + kết quả tìm kiếm | `6142c08` | `components/ConfidenceBadge.tsx`, `PageFinderView.tsx`, `SearchResults.tsx`, `styles.css` |
| 3 | Tách Nguồn chat khỏi `ChatView`, test `groupChatSources` độc lập | `fd9c71e` | `features/chat/Sources.tsx`, `ChatView.tsx`, `chat-sources.test.ts` |
| 4 | Gom CSS rail/pane-head, thêm token dùng chung, giữ class cũ alias | `3a74c48` | `styles.css`, `NotesView.tsx`, `PageFinderView.tsx`, `ChatView.tsx` |
| 5 | `PaneHeader` + `GroupSection` dùng chung (2 nơi dùng thật) | `6b54cb3` | `components/PaneHeader.tsx`, `components/GroupSection.tsx`, `components/index.ts`, `NotesView.tsx`, `PageFinderView.tsx`, `SearchResults.tsx` |
| 6 | Test bàn phím group header / sort toggle / Modal | `989cc6b` | `tests/ui/ui.test.tsx`, `tests/ui/page-finder.test.tsx` |
| 7 | ADR-0006 (source-first/ngưỡng OR), ADR-0017 (SSE page-match), sửa Caddy route `/stream` | `4c1a36f` | `docs/adr/0006-hybrid-search-rrf.md`, `docs/adr/0017-page-match-sse-progress.md`, `docs/adr/README.md`, `infra/Caddyfile` |

## 2. Thay đổi chi tiết

### 2.1. Component dùng chung

- **`ConfidenceBadge`** (`components/ConfidenceBadge.tsx`):
  - Nhận `value` 0..1 (kẹp ngoài khoảng), `kind: 'confidence' | 'similarity'`, `verified`.
  - Hiển thị `%` + tooltip phân biệt “AI tin cậy…” / “AI chưa thẩm định — theo độ tương đồng cosine”;
    nhãn đầy đủ nằm trong `.sr-only` nên badge gọn mà vẫn có ngữ nghĩa.
  - Dùng ở `PageFinderView` (thay `.pf-sim`) và `SearchResults` (thay `<small>` cosine).
- **`Sources`** (`features/chat/Sources.tsx`):
  - Tách chip + “Chi tiết nguồn” khỏi `ChatView`; `groupChatSources()` là hàm thuần, test trực tiếp
    (nhóm theo `source_index`, fallback legacy theo `source_domain`, “Không rõ nguồn” cuối).
- **`GroupSection`** (`components/GroupSection.tsx`):
  - Chuyển từ `features/notes/SourceGroup.tsx`; 2 consumer thật (`NotesView`, `SearchResults`).
  - Giữ `.source-group*` và `aria-label="Nguồn …"`; header là `<button>` với `aria-expanded` +
    `aria-controls` trỏ đúng body.
- **`PaneHeader`** (`components/PaneHeader.tsx`):
  - Dùng cho `NotesView` (`.pane-head`) và `PageFinderView` (`.pf-head`).
  - `title`/`subtitle`/`actions` + slot `children` (banner) / `footer` (hint); phụ đề có `aria-live`
    (tắt được bằng `subtitleLive={false}`).
  - Class cũ vẫn truyền qua props (`pane-head`, `pane-head-row`, `pane-title`, `pf-titlerow`,
    `pf-title`, `pf-meta`, `pf-headactions`), không đổi giao diện/selector e2e.
- **Không tách thêm khi chỉ có 1 nơi dùng** (đúng quy tắc §5.5 “tránh abstraction sớm”):
  `SegmentedControl` (`.pf-sort`), `BulkActionBar` (`.selection-bar`), `SourceChip`/`SourceCard`
  (chat), `MoveNotesDialog` (đã là component riêng của Thư viện). Khi có consumer thứ hai mới tách.

### 2.2. CSS + design token (`styles.css`)

- Thêm token: `--pane-head-h: 56px`, `--pane-pad: 14px`, `--card-pad: 9px 10px`,
  `--group-head-bg: var(--surface)`; dùng thật ở `.conv-head`, `.pane-head`/`.rail-head`,
  `.note-item`/`.source-card`, hover của `.source-group-toggle`.
- Gom layout rail: `.pane-rail` là class chuẩn (`flex column`, `--rail-bg`, border phải);
  `.folder-rail` / `.pf-rail` / `.session-pane` giữ làm alias, chỉ còn khai báo phần khác biệt.
- `.pane-head` còn padding; hàng tiêu đề chuyển sang `.pane-head-row` (`flex`, `space-between`).
- `.confidence-badge` dùng chung selector với `.pf-sim` (alias) — không phá CSS/ảnh chụp cũ.
- Không thêm màu cứng; mọi màu vẫn qua token, `tests/contrast.test.ts` kiểm tra WCAG AA.

### 2.3. Sửa lỗi đếm kết quả tìm kiếm

- **Trước**: `NotesView` và `SearchView` cộng `sources.reduce((n, s) => n + s.notes.length, 0)`.
  API chỉ trả tối đa 10 note/nguồn, nên nguồn có 12 note khớp bị báo “3 ghi chú”.
- **Sau**: `countSearchNotes()` cộng `source.note_count` (tổng đạt ngưỡng trước khi cắt); test UI
  dựng nguồn `note_count=12`, API trả 3 note → hiện “12 ghi chú cho ‘phở’” + “và 9 ghi chú khác”.

### 2.4. Test / a11y

- Tổng test extension: **22 file, 227 test** (tăng 15 so với baseline 18 file/212 test):
  - `search-summary.test.ts` (2), `chat-sources.test.ts` (4), `ui/group-section.test.tsx` (3),
    `ui/pane-header.test.tsx` (3).
  - `ui.test.tsx`: đếm theo `note_count`, `ConfidenceBadge` (kẹp 0..1, fallback), Modal
    (Esc đóng, trả focus, Tab tuần hoàn), group header là button focus được.
  - `ui/page-finder.test.tsx`: sort group có `role="group"`, từng nút là `<button type="button">`
    và focus được (Enter/Space do trình duyệt kích hoạt).
- A11y: `GroupSection` dùng `<button>` + `aria-expanded`/`aria-controls`; sort toggle là button
  thật + `aria-pressed`; `Modal` đã có bẫy focus/Esc/trả focus (test mới xác nhận).

### 2.5. Docs / hạ tầng

- **ADR-0006**: thêm mục “Cập nhật Phase 1 — source-first + ngưỡng OR (18/11/2026)”: gom chunk→note,
  ngưỡng OR `similarity ≥ 0.5` hoặc `score ≥ 0.03`, xếp hạng nguồn, `note_count`, giới hạn
  `max_sources`/`notes_per_source`; nêu rõ ngưỡng **chưa eval trên DB thật**.
- **ADR-0017**: quyết định SSE cho `/ai/page-match/stream` (event `progress`/`done`/`error`, batch 32,
  timeout 30 s/lô, huỷ → `aclose()` nhả quota), phương án đã loại (JSON+spinner, polling job,
  WebSocket, NDJSON) và hệ quả.
- **ADR README**: bổ sung 0016 (đã có file nhưng thiếu bảng) và 0017.
- **Caddy**: `@page_match` chỉ khớp `/api/v1/ai/page-match`, **không khớp `/stream`** → request stream
  bị route `@api` giới hạn 1 MB thay vì 3 MB. Đã thêm `/api/v1/ai/page-match/stream` và
  `reverse_proxy { flush_interval -1 }` để SSE không bị gom buffer.

### 2.6. Hiệu năng / quota

- Không thêm dependency runtime; `npm run check:bundle` vẫn 11 tệp, quyền không đổi. Bundle side panel
  sau P5: `index.html-*.js` 251,65 kB (73,48 kB gzip), `AuthGate-*.js` 235,25 kB (74,24 kB gzip) —
  xấp xỉ baseline (`252,56`/`233,80` kB; tổng lệch ~+0,5 kB không nén, do component mới được
  tree-shake theo import).
- Page-match SSE không thêm lease: vẫn 1 lease embed + 1 lease verify; đóng stream gọi `aclose()`
  để `async with` release phần giữ chỗ ngay (đã ghi trong ADR-0017, integration test stream/quota
  nằm trong nhóm 51 test bị skip vì thiếu DB).
- `countSearchNotes()` chỉ cộng số nguyên đã có trong response, không gọi thêm API.

## 3. Kiểm chứng độc lập

Không dùng báo cáo P0–P4 làm bằng chứng; mọi số dưới đây chạy lại trên cây làm việc hiện tại.

### 3.1. Tự động

| Lệnh | Kết quả |
|---|---|
| `npm run typecheck` (apps/extension) | ✅ không lỗi |
| `npm test` (vitest) | ✅ **22 file, 227/227 test** |
| `npm run build` | ✅ built (331 modules) |
| `npm run check:bundle` | ✅ 11 tệp; quyền giữ nguyên (`contextMenus`, `storage`, `identity`, `scripting`, `activeTab`, `alarms`, `sidePanel`, `http://localhost:8000/*`) |
| `ruff check src tests` (apps/api) | ✅ All checks passed |
| `pytest -q` (apps/api) | ✅ **225 passed, 154 skipped** (integration skip có chủ ý — không có DB) |
| `pytest -q tests/unit/business/test_semantic_grouping.py tests/unit/business/test_rag_prompts.py tests/unit/business/page_match` | ✅ **60 passed** |
| `pytest -q tests/integration/api/test_search.py tests/integration/api/test_notes_crud.py tests/integration/api/test_page_match.py` | ⚠️ **51 skipped** (cần `TEST_DATABASE_URL` + pgvector) |
| `python scripts/export_openapi.py --check` | ✅ `openapi.json khớp code` |
| `npm run gen:api:file` + `git diff` | ✅ `schema.d.ts` đồng bộ, không phát sinh diff |
| `grep SearchHit` trong `apps/extension/src`, `apps/api/src` | ✅ **0** — không còn type phẳng ở nơi dùng grouped |

### 3.2. E2E — chưa chạy được (blocked)

- Docker daemon có nhưng user không thuộc group `docker`: `permission denied ... /var/run/docker.sock`;
  `sudo` yêu cầu mật khẩu tương tác.
- Không có PostgreSQL server cục bộ (chỉ có `psql` client); `TEST_DATABASE_URL` không tồn tại.
- Playwright CLI có trong `node_modules` nhưng `~/.cache/ms-playwright` rỗng (chưa cài chromium).
- Vì vậy **chưa chạy**: `c05-library`, `r05-search`, `x02-chat`, `ux-screens`, `h05-a11y`.

Đã rà tính tương thích selector của các spec với thay đổi P5 (không chạy):

- `c05-library`: `region` “Nguồn same.example” (giữ `section[aria-label]`), `Chọn`, `Chuyển thư mục`,
  `dialog` + `Thư mục đích` + `Chuyển (2)` — không đổi.
- `r05-search`: `ol.list > li` vẫn nằm trong `GroupSection`; `Mở ghi chú`, `Mở trang nguồn` giữ nguyên.
- `x02-chat`: `Nguồn (N)`, `.source-card`, `[n]` → `Sources.tsx` giữ nguyên markup/aria-label.
- `ux-screens`: heading/`ol.list`/toolbar giữ nguyên; `h05-a11y`: axe + tab/Enter/Escape vẫn dùng
  component cũ (`Tabs`, `Modal`).

### 3.3. Kiểm tra giao diện bằng CSS thật (chrome-devtools)

Dựng preview ngoài repo (`/tmp/opencode/p5-verify/`) dùng **nguyên `styles.css`** với DOM mới của
`PaneHeader`/`GroupSection`/rail, xem ở 400×900 (panel hẹp) cả light & dark:

- `.pane-head`: `display:block`, padding `14px 14px 4px`; `.pane-head-row`: `flex`, `space-between`,
  `align-items:flex-start`, `gap:8px`; title 15px/650 — khớp trước refactor.
- `.pf-titlerow`: `flex`, `wrap`, `space-between`; `.pf-hint` vẫn nằm trong `.pf-head`; banner và
  sort toggle đúng thứ tự.
- `.folder-rail` + `.pane-rail`: `flex column`, `--rail-bg`, border phải 1px; ở ≤900px alias
  `.folder-rail { display:none }` vẫn hoạt động.
- `.confidence-badge`: light `#0b57d0` trên `#eef4ff`, viền `#c7d9ff`, radius 999px — đúng token.
- Ảnh: `/tmp/opencode/p5-verify/p5-preview-dark.png` (dark), `p5-preview-light.png` (light) — không commit.

### 3.4. Phát hiện độc lập trong quá trình kiểm chứng

1. **Đếm sai kết quả tìm kiếm**: UI đếm `notes.length` (tối đa 10/nguồn) thay vì `note_count` → sửa
   bằng `countSearchNotes()` + test 12/3.
2. **Caddy bỏ sót route SSE**: `/stream` rơi vào giới hạn 1 MB và không có `flush_interval` → sửa
   Caddy (chưa `caddy validate` vì máy không cài Caddy; xem §5).
3. `schema.d.ts` thực sự đồng bộ OpenAPI; không còn `SearchHit` phẳng — xác nhận bằng lệnh, không
   dựa vào báo cáo cũ.

## 4. Đối chiếu checklist Phase 5 (§11)

- [x] `npm run typecheck`, `npm test`, `npm run build` xanh — 22 file/227 test, bundle đạt rà soát.
- [x] `pytest` xanh; test grouping/threshold/bulk move/page-match đã có — unit API 60 passed;
  integration 51 skipped vì thiếu DB (bulk move + stream nằm trong nhóm này).
- [ ] E2E `c05-library`, `r05-search`, `x02-chat`, `ux-screens` xanh — **chưa chạy được** (Docker/
  Postgres/Playwright chromium, xem §3.2).
- [x] Contrast/a11y test xanh; keyboard group header/sort toggle/dialog — test đơn vị xác nhận
  button/focus/`aria-expanded`/`aria-pressed`/Esc/Tab; e2e thật chờ môi trường.
- [x] `schema.d.ts` regenerate; không còn type `SearchHit` phẳng ở nơi dùng grouped.
- [x] Docs/ADR: ADR-0006 cập nhật threshold/grouping; ADR-0017 mới cho page-match SSE/progress;
  README ADR cập nhật index.

## 5. Hạn chế & ghi chú

- **E2E chưa nghiệm thu**: các spec đã được rà selector nhưng chưa chạy; cần môi trường Docker +
  PostgreSQL/pgvector + `npx playwright install chromium` để chốt.
- **Eval ngưỡng chưa chạy**: 0.5/0.03 vẫn là đề xuất; cần `TEST_DATABASE_URL=... python -m tests.eval.run_eval`
  để đo `empty_rate`/recall trước khi chốt (hạ 0.5 → 0.45 chỉ cần đổi env).
- **Caddy chưa validate**: máy dev không có binary `caddy`; cần `caddy validate --config infra/Caddyfile`
  và smoke test SSE qua proxy trước khi deploy.
- **Không tách component một consumer**: `SegmentedControl`, `BulkActionBar`, `SourceChip`/`SourceCard`
  giữ nguyên tại chỗ theo quy tắc “chỉ tách khi có ≥2 nơi dùng thật”; `MoveNotesDialog` đã là component
  riêng của Thư viện. Nếu Phase sau có consumer thứ hai, tách mà không đổi class alias.
- **A11y form field id/name** trên sidepanel thật (ghi chú từ P0) vẫn chưa xử lý trong P5; cần chạy
  axe/e2e để xác nhận còn vi phạm hay không.
- `docs/self_sustained/ux_improvement_plan.md` và `ux_recommendation.md` vẫn là file chưa track của
  người dùng — không sửa/commit.

## 6. Đề xuất tiếp theo

1. Dựng môi trường e2e (Docker Compose + Postgres/pgvector + `npx playwright install chromium`) và
   chạy `c05-library`, `r05-search`, `x02-chat`, `ux-screens`, `h05-a11y`; bổ sung kiểm tra bàn phím
   thật cho group header/sort/dialog nếu muốn chuyển từ unit sang e2e.
2. Chạy eval baseline trên DB thật, ghi `empty_rate`/recall/MRR vào báo cáo bổ sung; chỉ chốt
   0.5/0.03 (hoặc hạ 0.45) sau khi có số.
3. `caddy validate` + smoke test SSE qua Caddy (đặc biệt body >1 MB và event đến từng bước, không bị
   gom).
4. Khi có consumer thứ hai, tách `SegmentedControl`/`BulkActionBar`/`SourceChip` và giữ alias class
   như P5 đã làm với `.pf-sim`/`.pane-head`.
