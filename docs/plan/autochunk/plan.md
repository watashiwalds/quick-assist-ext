# Kế hoạch triển khai: AutoChunk — Ghi chú theo truy vấn (v2, Trafilatura)

> **Cơ sở:** Plan v1 (`docs/plan/autochunk/autochunk.md`, 07/11/2026) — Statement of Intent §1 giữ nguyên, đã xác nhận.
> **Thay đổi cốt lõi của v2 (xác nhận 07/11/2026):** tầng trích nội dung chuyển từ content script (DOM-block) sang **backend Trafilatura** (phương án A) — supersede quyết định §4.1 của plan v1. ADR-0012 mới sẽ ghi quyết định này.
> **Trạng thái:** Chưa implement. Task chi tiết (mô tả + acceptance criteria): `tasks/todo.md`.

---

## Overview

AutoChunk là **cách ghi chú thứ hai trên trang**, song song với luồng bôi đen: người dùng nhập ý định bằng ngôn ngữ tự nhiên → extension gửi **HTML thô đã làm nhẹ** của trang hiện tại → backend **Trafilatura** trích nội dung chính và cắt thành các block → embed + cosine lọc ứng viên → **LLM thẩm định** → user tích chọn các đoạn → **1 ghi chú gộp** qua `POST /notes` (pipeline note + index tìm kiếm ngữ nghĩa sẵn có, không đổi schema DB). Click đoạn trong danh sách → cuộn + highlight trên trang bằng text matching.

```
Sidepanel (PageFinderView)                       Backend (cùng container API)
  │ query ──► RPC pageMatch/run                    POST /api/v1/ai/page-match
  ▼                                                1. validate + cap HTML 2MB (413)
Background ─ executeScript ─► getRawHtml()         2. Trafilatura (ProcessPool, timeout 10s)
  clone DOM, strip script/style/noscript/             → blocks[{id, text, occ}] (422 nếu rỗng)
  template/svg ─► serialize outerHTML              3. quota lease 1: embed([query, *blocks])
  │                                                4. cosine → lọc min_score 0.35, top 15
  └── POST /ai/page-match {html, query, url, title} 5. quota lease 2: LLM verify JSON
  │                                                6. match_ratio → mode segments|full_page
  ◄─── {mode, match_ratio, warning, items[]}       (LLM lỗi → VERIFY_UNAVAILABLE, verified=false)
  ▼
Danh sách đoạn ✓ ── tích chọn ──► Lưu: join "\n\n" ─► RPC notes/create ─► POST /notes (Idempotency-Key)
  │ click đoạn ──► RPC pageMatch/highlight ─► highlightBlocksByText(): chuẩn hoá whitespace
                                                + contains/fuzzy + occ ─► scroll + nổi bật ~4s
```

## Architecture Decisions

| # | Quyết định | Lý do |
|---|---|---|
| **AD-1** | **Trích nội dung = backend Trafilatura**, thay `extractPageBlocks()` của plan v1. Extension chỉ còn `getRawHtml()` + `highlightBlocksByText()` | Chất lượng segment là sản phẩm: bỏ boilerplate (nav, cookie banner, widget) trên **mọi trang**; cap 50k chars trở thành "50k nội dung thật"; embed rẻ hơn, cosine ít nhiễu; 1 code path. Highlight vốn map theo text+occ (không giữ node ref) nên block sinh từ backend vẫn highlight được |
| **AD-2** | Trafilatura chạy **trong cùng container API**, parse trong **ProcessPoolExecutor** (timeout 10s, kill khi treo, crash không lan vào API, không block event loop). Không sidecar ở V1 | Đóng gói: `pip install trafilatura` — lxml có sẵn manylinux wheels cho py3.11 slim, không compile, +30–50MB image, không tải model lúc chạy, không ghi đĩa (tương thích read-only fs). Compose **không đổi topology** (1 image cho api+worker+migrate). Isolation cho HTML untrusted (lxml/libxml2 CVE) ở mức process pool |
| **AD-3** | **Privacy/payload:** content script clone DOM + strip `script/style/noscript/template/svg` trước khi serialize; cap mới `page_match_max_html_bytes` = 2MB → `413 PAGE_TOO_LONG`; backend chỉ log metadata | Giảm 30–50% payload, hạn chế dữ liệu nhạy cảm (`__NEXT_DATA__`, token form) rời máy; cap chặn DoS CPU/RAM |
| **AD-4** | **Không đổi schema DB.** Kết quả lưu bằng `POST /notes` (Idempotency-Key bắt buộc), title mặc định = query; worker chunk (`chunking.py`) + pgvector như note thường | Page match là operation stateless trả preview; search ngữ nghĩa hoạt động ngay không cần thay đổi |
| **AD-5** | **Độ tin cậy 2 tầng:** cosine lọc rẻ (`min_score` 0.35, tối đa 15 ứng viên) → LLM verify chốt (JSON verdict, `max_tokens` 500). LLM lỗi/JSON hỏng → `warning=VERIFY_UNAVAILABLE`, trả theo điểm `verified=false` | Giới hạn token bước đắt; degrade có kiểm soát, tính năng không chết khi AI lỗi |
| **AD-6** | **Chống prompt injection:** `neutralize()` + thẻ `<document>` + system prompt cấm làm theo chỉ dẫn — dùng lại pattern `business/summary/prompts.py` | Dữ liệu trang là untrusted; pattern đã kiểm chứng trong repo |
| **AD-7** | **Highlight = text matching:** chuẩn hoá whitespace 2 phía → exact → contains (block tách câu) → fuzzy (last resort); đếm `occ` cho lần xuất hiện thứ n; thất bại → toast, không crash | Block sinh từ Trafilatura có thể lệch nhẹ với DOM (gộp block, chuẩn hoá text); cơ chế toast dự phòng đã có trong plan v1 §5.1 |
| **AD-8** | **Cosine thuần Python** giữa vector query và từng block (block không nằm trong DB, không dùng pgvector ở bước này) | Đúng plan v1 §4.3 bước 3 |
| **AD-9** | **Chỉ chạy khi user bấm Quét** + rate limit riêng `page_match` = 6/phút; timeout HTTP client riêng `pageMatchRequestTimeoutMs` | Kiểm soát chi phí embed + latency LLM |
| **AD-10** | `splitLongBlock` (tách câu, block > 1200 chars) chuyển về **backend Python** trong `extractor.py`; extension không còn hàm cắt | Block sinh từ backend; pytest dễ test hơn jsdom |

## Hợp đồng API — `POST /api/v1/ai/page-match` (delta so với plan v1 §4.2)

```jsonc
// Request (presentation/schemas/page_match.py)
{
  "query": "nghị quyết liên quan đến đất đai",   // 1..500 ký tự
  "html": "<!DOCTYPE html>…",                     // HTML đã strip; ≤ page_match_max_html_bytes
  "url": "https://…", "title": "…"                // tuỳ chọn, chỉ log/metadata
}
// Response
{
  "mode": "segments",              // "segments" | "full_page"
  "match_ratio": 0.42,             // ∑ ký tự block verified / ∑ ký tự nội dung trích được
  "warning": null,                 // "VERIFY_UNAVAILABLE" khi LLM lỗi
  "items": [                       // sort theo thứ tự trong trang
    { "id": "b07", "occ": 0, "text": "Nghị quyết 12/2023 về quản lý đất đai…",
      "score": 0.78, "verified": true }
  ]
}
```

**Lỗi mới:** `413 PAGE_TOO_LONG` (HTML vượt cap), `422 PAGE_NO_CONTENT` (Trafilatura trích rỗng / timeout parse / trang không có nội dung chính — PDF, canvas). Kèm mã hiện có: `402 QUOTA_EXCEEDED`, `422` validate, `429`, `502 AI_UNAVAILABLE`. Cập nhật `docs/api/conventions.md` + `shared/errors.ts`; sau khi code: `python scripts/export_openapi.py` + `npm run gen:api`.

## Config mới (`infrastructure/config.py` + `infra/.env.example`)

| Setting | Mặc định | Ý nghĩa |
|---|---|---|
| `page_match_max_html_bytes` | 2 000 000 | Trần HTML extension gửi lên (413) |
| `page_match_extract_timeout_seconds` | 10 | Timeout parse Trafilatura trong process pool |
| `page_match_max_chars` | 50 000 | Trần tổng ký tự block sau khi trích (bound chi phí embed) |
| `page_match_max_block_chars` | 1 200 | Trần 1 block trước khi tách theo câu |
| `page_match_top_candidates` | 15 | Số ứng viên tối đa đưa cho LLM verify |
| `page_match_min_score` | 0.35 | Ngưỡng cosine vào vòng verify |
| `page_match_full_page_ratio` | 0.6 | match_ratio vượt ngưỡng → mode `full_page` |
| `page_match_verify_max_output_tokens` | 500 | Trần output JSON của LLM |
| `rate_limit_page_match_per_minute` | 6 | Rate limit riêng endpoint |
| `pageMatchRequestTimeoutMs` (extension config) | 30 000 | Timeout HTTP client sidepanel |

## Docker / Triển khai (đã đánh giá — xác nhận với user)

- Thêm `trafilatura` vào `pyproject.toml`; **không đổi** `apps/api/Dockerfile` lẫn `infra/docker-compose*.yml`.
- Ảnh lớn hơn ~30–50MB; parse chạy process pool → timeout + isolation; verify build: `docker compose -f infra/docker-compose.yml build api` ở Task 1.
- Worker không cần trafilatura (extraction chỉ trong request path của API) — vẫn dùng chung 1 image theo thiết kế hiện có.

## Task List

### Phase 1 — Backend (nền tảng)
- [ ] **Task 1:** Extraction core — `business/page_match/extractor.py` (Trafilatura + ProcessPool + block splitting) + config + fixtures
- [ ] **Task 2:** `POST /ai/page-match` — schemas + `PageMatchService` + `prompts.py` + controller + rate limit + tests (AI mock)

### ✅ Checkpoint 1 — Backend hoàn chỉnh
- [ ] `pytest` + `ruff check .` pass; `export_openapi.py` chạy được
- [ ] Gọi thủ công `/ai/page-match` bằng HTML mẫu → response đúng contract (413/422/VERIFY_UNAVAILABLE/full_page)
- [ ] `docker compose build api` thành công
- [ ] **Review với human trước khi sang Phase 2**

### Phase 2 — Extension
- [ ] **Task 3:** Capture + plumbing — `getRawHtml()`, `background/page-match.ts`, protocol/handlers, `endpoints.ts`, `errors.ts`, `gen:api`
- [ ] **Task 4:** UI `PageFinderView` — query, 2-phase loading, kết quả, chọn nhiều, lưu note, empty/402/413/no-content states
- [ ] **Task 5:** Highlight + scroll — `highlightBlocksByText()` (chuẩn hoá + fuzzy + occ), DOM đổi → toast

### ✅ Checkpoint 2 — Luồng chính end-to-end
- [ ] Trang nghị quyết mẫu: query → segments → chọn → lưu → note trong thư viện → click đoạn → highlight trang
- [ ] `npm run typecheck` + `npm run test` + `npm run build` pass
- [ ] **Review với human trước khi sang Phase 3**

### Phase 3 — Hoàn thiện
- [ ] **Task 6:** Chế độ `full_page` — banner + "Lưu cả trang" + cảnh báo kích thước/quota
- [ ] **Task 7:** Docs & QA — conventions, ADR-0012, UX screens, RTM/test-plan, demo-script, architecture/SDS, cập nhật autochunk.md
- [ ] **Task 8 (tuỳ chọn):** Playwright E2E trang mẫu → lưu → note trong thư viện

### ✅ Checkpoint 3 — Hoàn thành
- [ ] Mọi acceptance criteria trong `tasks/todo.md` đạt
- [ ] Docs khớp code thật; sẵn sàng review

## Risks and Mitigations

| Rủi ro | Impact | Mitigation |
|---|---|---|
| Trafilatura gộp block/chuẩn hoá text → highlight lệch DOM | Med | Chuẩn hoá whitespace + contains + fuzzy + `occ`; thất bại → toast (AD-7); tune `favor_recall` trên bộ fixture (Task 1) |
| lxml/libxml2 CVE khi parse HTML untrusted trong API | Med | ProcessPool isolation (AD-2) + cap 2MB + pin version + theo dõi security checklist |
| Trang không có nội dung chính (PDF/canvas/SPA rỗng) | Med | `PAGE_NO_CONTENT` → toast "Trang không hỗ trợ" (giữ hành vi V1 của plan v1) |
| HTML payload lớn/chậm mạng | Low | Strip client-side + cap 2MB + `pageMatchRequestTimeoutMs` |
| Chi phí embed cả trang mỗi lần quét | Med | User-initiated only + cap 50k sau trích + rate limit 6/phút; hậu kiểm: LRU cache theo hash |
| LLM verify chậm (~1–3s) / sai | Med | Loading 2 pha; timeout → fallback unverified; chỉ verify top 15 score ≥ 0.35; đánh giá trên bộ trang mẫu → `docs/ai/` |
| Prompt injection từ nội dung trang | High | `neutralize()` + `<document>` + system prompt cấm làm theo (AD-6) + test injection |
| Quota operation mới chưa có pricing | Low | Đăng ký `page_match_embed`, `page_match_verify` vào cấu hình quota như các operation AI hiện có (Task 2) |

## Open Questions (không chặn Task 1)

- Tune tham số Trafilatura (`favor_recall` vs `favor_precision`, `include_comments`, `include_tables`) trên bộ fixture thật — quyết ở Task 1/2.
- Ngưỡng bỏ block quá ngắn (heading 1–2 chữ) — tune theo bộ mẫu, tránh xoá mất heading có ý nghĩa.
- Cache embedding theo hash nội dung cho lần quét lại — hậu kiểm sau khi có dữ liệu dùng thật (giữ nguyên quyết định plan v1 §10).
- Cho phép sửa nội dung đoạn trước khi lưu — V1: không (giữ quyết định plan v1 §10).
