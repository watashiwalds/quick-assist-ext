# AutoChunk v2 (Trafilatura) — Task List

> Plan chi tiết: `tasks/plan.md`. Statement of Intent: `docs/plan/autochunk/autochunk.md` §1 (giữ nguyên).
> Quy ước verify: backend `pytest` + `ruff check .` (chạy trong `apps/api`); extension `npm run typecheck` + `npm run test` + `npm run build` (chạy trong `apps/extension`).

---

## Phase 1 — Backend

### Task 1: Extraction core — Trafilatura trong ProcessPool

**Mô tả:** Tạo `business/page_match/extractor.py`: nhận HTML → chạy Trafilatura trong `ProcessPoolExecutor` (lazy singleton, timeout `page_match_extract_timeout_seconds`) → lấy XML tree (`output_format="xml"`, `include_tables=True`) → chuyển thành block units từ element `p/head/item/quote/cell` theo thứ tự tài liệu → gán `id` (`b00`, `b01`…) và `occ` (số lần text trùng lặp trước đó) → `splitLongBlock` tách block > `page_match_max_block_chars` theo câu → cap tổng `page_match_max_chars` (cắt theo biên block) → trả `(blocks, total_chars)`. HTML rỗng / trích rỗng / timeout → `ExtractError`. Thêm config + `.env.example` + dependency `trafilatura` vào `pyproject.toml`.

**Acceptance criteria:**
- [ ] Fixture HTML (bài viết, danh sách nghị quyết `<li>`, trang nhiều boilerplate, trang trắng) → blocks đúng thứ tự tài liệu, `id`/`occ` đúng
- [ ] Block > 1200 chars được tách theo câu, không mất text, `occ` đánh lại đúng
- [ ] HTML rác/timeout → `ExtractError`, process pool không chết, API không treo
- [ ] Chỉ `business/page_match` import trafilatura (test kiến trúc)

**Verification:**
- [ ] `pytest` pass (test mới: `tests/.../page_match/test_extractor.py` + fixtures `tests/fixtures/html/`)
- [ ] `ruff check .` pass
- [ ] `docker compose -f infra/docker-compose.yml build api` thành công (image +30–50MB, không đổi compose)

**Phụ thuộc:** None · **Files:** `business/page_match/{__init__,extractor}.py`, `infrastructure/config.py`, `infra/.env.example`, `apps/api/pyproject.toml`, tests · **Scope:** M

### Task 2: API endpoint + PageMatchService + prompts

**Mô tả:** `presentation/schemas/page_match.py` (request/response theo plan.md §Hợp đồng API); `business/page_match/prompts.py` (`PAGE_MATCH_SYSTEM` + `page_match_messages`: `neutralize()`, bọc `<document>` chứa query + `[id] đoạn`, yêu cầu JSON `{"results":[{"id":"…","relevant":true}]}`, system cấm làm theo chỉ dẫn — pattern `business/summary/prompts.py`); `page_match_service.py` theo pattern `SemanticSearchService`: validate query → cap HTML (413) → extract (422 khi `ExtractError`) → **quota lease 1** `page_match_embed`: `QuotaService.open()` → `reserve(estimate_tokens(query+blocks))` → `ai.embed([query, *block_texts])` 1 batch → `commit` (lỗi → `release` + `AI_UNAVAILABLE`) → cosine Python → lọc `min_score`/`top_candidates` → **quota lease 2** `page_match_verify`: `ai.complete(..., max_tokens=...)` → parse JSON an toàn (fail/`AIProviderError` → `warning=VERIFY_UNAVAILABLE`, `verified=false`) → `match_ratio` → `mode` → items sort theo trang. `page_match_controller.py` `POST /ai/page-match` với `AIProviderDep`, `CurrentUserId`, `Depends(rate_limit("page_match", "rate_limit_page_match_per_minute"))` (pattern `summary_controller.py`); đăng ký router; đăng ký 2 quota operation mới vào cấu hình pricing; log chỉ metadata.

**Acceptance criteria:**
- [ ] Contract khớp plan.md; `python scripts/export_openapi.py` sinh OpenAPI chứa endpoint
- [ ] `413 PAGE_TOO_LONG` khi HTML vượt cap; `422 PAGE_NO_CONTENT` khi trích rỗng/timeout; `422` query rỗng/>500 ký tự
- [ ] `AI_PROVIDER=mock`: embed đúng 1 lần batch; verify JSON hợp lệ → `verified=true`; chat lỗi / JSON hỏng → `warning=VERIFY_UNAVAILABLE`, items theo score, không 502
- [ ] 2 lease quota reserve→commit đúng operation; lỗi AI → release, không giữ lease
- [ ] `match_ratio` đúng công thức; `mode="full_page"` khi ≥ 0.6
- [ ] Test kháng injection: trang chứa `‹/document›` giả + chỉ dẫn → prompt vẫn bọc đúng, mock không bị chỉ đạo
- [ ] Rate limit 6/phút → `429` có `Retry-After`

**Verification:**
- [ ] `pytest` pass (test service/controller/quota/fallback/injection)
- [ ] `ruff check .` pass
- [ ] Thủ công: curl/Swagger UI gọi endpoint với HTML mẫu → response đúng

**Phụ thuộc:** Task 1 · **Files:** `presentation/schemas/page_match.py`, `business/page_match/{prompts,page_match_service}.py`, `presentation/api/v1/controllers/page_match_controller.py`, `presentation/api/v1/router.py`, quota pricing config, tests · **Scope:** M

---

## ✅ Checkpoint 1 — Backend hoàn chỉnh (xem plan.md)

- [ ] `pytest` + `ruff` pass; OpenAPI export được
- [ ] Endpoint chạy đúng bằng HTML mẫu trên Swagger
- [ ] `docker compose build api` OK
- [ ] **Review với human → mới sang Phase 2**

---

## Phase 2 — Extension

### Task 3: Capture + plumbing (background gateway)

**Mô tả:** `content/injected.ts` thêm hàm **tự chứa** (không import — quy tắc hiện tại): `getRawHtml()` → clone `documentElement`, remove `script/style/noscript/template/svg`, serialize `outerHTML`, trả `{html, url, title, tooLong}` (client pre-check > 2MB → `tooLong: true` để background dừng sớm); `background/page-match.ts`: `runPageMatch(tabId, query)` (executeScript → `api.ai.pageMatch`) + `highlightInTab(tabId, items)`; `shared/messaging/protocol.ts` thêm `'pageMatch/run'`, `'pageMatch/highlight'` vào `RpcMap`; `handlers.ts` route (thiếu handler = lỗi biên dịch); `shared/api/endpoints.ts` thêm `ai.pageMatch` với `timeoutMs: config.pageMatchRequestTimeoutMs`; `shared/errors.ts` map `PAGE_TOO_LONG` ("Trang quá dài để quét…"), `PAGE_NO_CONTENT` ("Trang không hỗ trợ quét nội dung"); chạy `python scripts/export_openapi.py` + `npm run gen:api` → commit `openapi.json` + `schema.d.ts`.

**Acceptance criteria:**
- [ ] `getRawHtml` strip đúng danh sách thẻ, tự chứa hoàn toàn, không upload khi quá dài
- [ ] RPC 2 chiều type-safe qua `RpcMap`; handler bắt buộc đủ
- [ ] Mã lỗi mới map đúng message tiếng Việt; `402`/`429` xuyên suốt tới UI
- [ ] `schema.d.ts` regenerate khớp contract backend

**Verification:**
- [ ] `npm run typecheck` + `npm run test` (vitest: `getRawHtml` jsdom, handler, error map) + `npm run build` pass

**Phụ thuộc:** Task 2 · **Files:** `content/injected.ts`, `background/page-match.ts` (mới), `background/handlers.ts`, `shared/messaging/protocol.ts`, `shared/api/endpoints.ts`, `shared/errors.ts`, `shared/config.ts` · **Scope:** M

### Task 4: UI PageFinderView

**Mô tả:** Tab mới **"Tìm trong trang"** cạnh Notes/Search (theo `docs/ux/ui-map.md`), đăng ký trong `App.tsx`. Input query + nút Quét; loading 2 pha ("Đang đọc trang…" → "Đang thẩm định…"); danh sách kết quả: clamp 4 dòng, badge "✓ Đã xác nhận" / "Theo điểm tương đồng" (khi `VERIFY_UNAVAILABLE`), checkbox nhiều chọn (pattern màn `08-chon-nhieu`), click đoạn → RPC highlight (Task 5); thanh hành động "Lưu N đoạn thành ghi chú" → chọn thư mục (pattern quick note) → RPC `notes/create` (thêm vào `RpcMap`, background sinh Idempotency-Key, `title` = query, `url` = url trang, content = `"\n\n".join(texts)` theo thứ tự trang) → toast + broadcast `notes/changed`. States: empty "Không tìm thấy đoạn nào đủ tin cậy" (pattern màn `11`); `402` → pattern màn `17-het-quota`; `413` → gợi ý quét phần nhỏ hơn; `PAGE_NO_CONTENT` → toast "Trang không hỗ trợ".

**Acceptance criteria:**
- [ ] Render + flow query → kết quả → chọn → lưu hoạt động; content join đúng thứ tự
- [ ] Badge verified/unverified hiển thị đúng theo `warning`
- [ ] Mọi error state (empty/402/413/422 no-content/mất mạng) có UI riêng, không treo loading
- [ ] Lưu xong → toast + `notes/changed`; note xuất hiện trong thư viện

**Verification:**
- [ ] `npm run test` (vitest: render, chọn nhiều, join content, các error state) + `npm run typecheck` + `npm run build` pass

**Phụ thuộc:** Task 3 · **Files:** `ui/features/page-finder/PageFinderView.tsx` (mới), `ui/sidepanel/App.tsx`, `shared/messaging/protocol.ts`, `background/handlers.ts`, tests · **Scope:** M

### Task 5: Highlight + scroll trên trang

**Mô tả:** `content/injected.ts` thêm hàm tự chứa `highlightBlocksByText(items)`: chuẩn hoá whitespace cả item và `textContent` → với mỗi item tìm node khớp: exact → contains (mảnh split nằm trong node lớn) → fuzzy (first-80-chars, last resort); đếm lần xuất hiện để lấy đúng `occ`-th; `scrollIntoView({block:'center'})` + style nổi bật (outline + nền) tự tắt sau ~4s; **không gắn attribute vào DOM trang, không innerHTML**. Không tìm thấy → `{ok:false}` → sidepanel toast "Không tìm thấy đoạn trên trang". RPC `pageMatch/highlight` chạy hàm này trong tab.

**Acceptance criteria:**
- [ ] jsdom: khớp exact dù whitespace/newline khác nhau; `occ` đúng với text lặp; contains cho mảnh tách câu; fail → `ok:false` không throw
- [ ] Highlight nhiều item cùng lúc; style tự tắt; không đụng React/framework của trang
- [ ] DOM đổi giữa 2 lần gọi → `ok:false` + toast, không crash

**Verification:**
- [ ] `npm run test` (vitest jsdom) pass; manual trên trang nghị quyết thật

**Phụ thuộc:** Task 3 (song song được với Task 4) · **Files:** `content/injected.ts`, `background/page-match.ts`, tests · **Scope:** S

---

## ✅ Checkpoint 2 — Luồng chính end-to-end (xem plan.md)

- [ ] Trang nghị quyết mẫu: query → segments → chọn → lưu → note trong thư viện → click đoạn → highlight trang
- [ ] `npm run typecheck` + `npm run test` + `npm run build` pass
- [ ] **Review với human → mới sang Phase 3**

---

## Phase 3 — Hoàn thiện

### Task 6: Chế độ `full_page`

**Mô tả:** Khi response `mode="full_page"` (match_ratio ≥ 0.6): banner "Hầu như cả trang khớp truy vấn — nên lưu cả trang" + nút **"Lưu cả trang"** (content = toàn bộ blocks theo thứ tự, join `\n\n`) kèm cảnh báo kích thước/quota (confirm khi content lớn); user vẫn cherry-pick được như thường.

**Acceptance criteria:**
- [ ] Banner + nút chỉ hiện khi `mode="full_page"`; lưu cả trang qua cùng `notes/create`
- [ ] Cảnh báo trước khi lưu trang lớn; tests banner + điều kiện

**Verification:** `npm run test` + `npm run build` pass · **Phụ thuộc:** Task 4 · **Files:** `PageFinderView.tsx`, tests · **Scope:** S

### Task 7: Docs & QA

**Mô tả:** (1) `docs/api/conventions.md`: dòng endpoint `POST /ai/page-match` + 2 mã lỗi mới; (2) `docs/adr/0012-page-extraction-trafilatura.md` (mới): extraction qua Trafilatura trên backend + ProcessPool cùng container — supersede quyết định DOM-block trong plan v1 §4.1; (3) `docs/ux/`: flow + screen PageFinder + banner full_page theo pattern `screens/`; (4) `docs/qa/`: RTM + test-plan bổ sung (`PAGE_TOO_LONG`, `PAGE_NO_CONTENT`, `VERIFY_UNAVAILABLE`, `full_page`, injection); (5) `docs/demo-script.md` thêm cảnh AutoChunk; (6) `docs/architecture/README.md` + SDS bổ sung module `business/page_match`; (7) cập nhật `docs/plan/autochunk/autochunk.md` trạng thái → v2 implemented + ghi delta; (8) `docs/ai/`: khung đánh giá chất lượng verify trên bộ trang mẫu.

**Acceptance criteria:**
- [ ] Tất cả docs trên tồn tại và khớp code thật (không mô tả hàm/API không tồn tại)
- [ ] RTM có dòng ánh xạ cho mỗi acceptance criteria chính

**Verification:** Review human · **Phụ thuộc:** Task 1–6 · **Files:** ~8 file docs · **Scope:** M

### Task 8 (tuỳ chọn): Playwright E2E

**Mô tả:** E2E: mở trang mẫu nghị quyết → mở tab "Tìm trong trang" → query → mock/số liệu thật → chọn đoạn → lưu → note xuất hiện trong thư viện.

**Acceptance criteria:**
- [ ] 1 kịch bản E2E xanh trong CI local (`docker compose` + extension build E2E)

**Verification:** `npx playwright test` · **Phụ thuộc:** Task 6 · **Scope:** S
