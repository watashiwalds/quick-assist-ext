# AutoChunk — Ghi chú theo truy vấn (Query-based Capture)

> **Trạng thái:** Plan v1 (07/11/2026) — chốt từ phiên phỏng vấn intent với nhóm. **Chưa implement.**
> Định vị: **một cách ghi chú thứ hai trên trang**, song song với luồng bôi đen hiện có — thay vì phải thủ công bôi đen từng đoạn một, người dùng mô tả thứ họ cần và chọn từ các đoạn hệ thống tìm ra.

---

## 1. Statement of Intent (đã xác nhận)

| Mục | Nội dung |
|---|---|
| **Outcome** | Nhập ý định bằng ngôn ngữ tự nhiên → extension trích nội dung trang hiện tại thành các đoạn → backend embed + tìm ứng viên → **LLM thẩm định** → user tích chọn đoạn muốn lưu → **1 ghi chú gộp nhiều đoạn** qua pipeline note sẵn có. |
| **User** | Người dùng QuickAssist đang đọc trang dài/nhiều phần (vd. danh sách nghị quyết), muốn gom đúng các đoạn liên quan mà không phải bôi đen từng đoạn một. |
| **Why now** | Nâng capture từ thủ công lên có trợ lý AI; tái dùng `AIProvider` (ADR-0004), quota reserve/commit, note pipeline, pattern kháng prompt-injection của summary. |
| **Success** | Trên trang danh sách nghị quyết, nhập "nghị quyết liên quan đến đất đai" → nhận các đoạn được LLM xác nhận nói về đất đai/bất động sản → tích chọn → 1 ghi chú gộp trong thư viện, index cho tìm kiếm ngữ nghĩa như note thường. Không đoạn nào đạt → thông báo rõ, không ép kết quả yếu. |
| **Constraint** | Backend hiện có (FastAPI + pgvector + auth + quota); nội dung trang gửi lên backend; chấp nhận latency 2 bước AI; note khổng lồ bị chặn bằng chế độ **tự chuyển "Lưu cả trang"** khi gần như toàn trang khớp. |
| **Out of scope** | Không tìm qua nhiều trang/lịch sử duyệt web; không tự lưu không qua bước user xác nhận; không chạy model AI local trong extension; không index sẵn trang trước khi có truy vấn; **không thay thế** luồng bôi đen. |

---

## 2. Nguyên tắc thiết kế

1. **Không đổi schema DB.** Quét trang là operation stateless; kết quả cuối cùng được lưu bằng `POST /notes` như note thường → worker index bằng `chunking.py` như cũ, tìm kiếm ngữ nghĩa hoạt động ngay.
2. **Cắt đoạn theo DOM-block ở extension, KHÔNG re-chunk ở backend** (quyết định then chốt — §4.1). `chunking.py` vẫn dành riêng cho index note.
3. **Độ tin cậy = 2 tầng:** điểm cosine (lọc ứng viên rẻ) → LLM thẩm định (chốt kết quả đắt). LLM lỗi → degrade có kiểm soát (trả theo điểm, đánh dấu `verified=false`).
4. **Dữ liệu trang là untrusted** — dùng lại cơ chế `neutralize()` + thẻ `<document>` + system prompt cấm làm theo chỉ dẫn của `business/summary/prompts.py`.
5. **Chỉ chạy khi user chủ động** bấm quét (không tự chạy theo trang) + rate limit riêng → kiểm soát chi phí embed cả trang.

---

## 3. Luồng dữ liệu tổng thể

```
Sidepanel (PageFinderView)                    Backend
  │ user nhập query                             │
  ▼ RPC 'pageMatch/run'                         ▼
Background ── executeScript ──► extractPageBlocks()      POST /api/v1/ai/page-match
  (content/injected.ts, tự chứa)          ┌──────────────▼───────────────┐
  │ blocks[{id, text}]                    │ PageMatchService             │
  ▼                                       │ 1. cap + reserve quota (embed)
Background ── POST /ai/page-match ───────►│ 2. embed([query, *blocks])   │
  │                                       │ 3. cosine → top ứng viên     │
  │ {mode, match_ratio, items[]}          │ 4. LLM verify (JSON verdict) │
  ▼                                       │ 5. match_ratio → mode        │
Sidepanel: danh sách đoạn ✓               └──────────────────────────────┘
  │ user tích chọn + bấm Lưu
  ▼ RPC → Background → POST /notes (Idempotency-Key)
  ▼ note PROCESSING → worker chunk + embed (như note thường)
  ▼ toast + thư viện; click đoạn ở danh sách → highlightBlocksByText() trên trang
```

---

## 4. Quyết định kỹ thuật chính

### 4.1 Cắt đoạn ở đâu? — Content script (DOM-block), không phải backend re-chunk

- **Highlight cần ánh xạ về DOM.** UX đã chốt là "click đoạn → cuộn + highlight trên trang"; chỉ có đơn vị cắt Sinh từ chính DOM mới map lại được chính xác. Backend re-chunk text thô sẽ mất ranh giới DOM.
- **Đơn vị "đoạn" tự nhiên của người dùng** là khối DOM (`p`, `li`, `h1–h6`, `blockquote`, `td`, `pre`), không phải chunk ≤ 1200 ký tự theo câu của `chunking.py`.
- **Khối quá dài** (> `page_match_max_block_chars`) → tách tiếp theo câu **trong extension** (hàm thuần `splitLongBlock`, dễ unit test), mỗi mảnh giữ `occurrence` để highlight đúng lần xuất hiện thứ n.
- Đoạn liền kề cùng được chọn khi lưu → nối bằng `\n\n` phía client; không cần stitch phức tạp ở backend.
- 📌 Ghi **ADR-0012**: "Page segmentation in content script (DOM-block), backend only embeds & verifies".

### 4.2 API contract — `POST /api/v1/ai/page-match`

Cùng nhóm `/ai` với `/ai/summaries`, `/ai/chat` (operation AI trả preview, không ghi DB). Statelessness → **không cần Idempotency-Key**; có `rate_limit("page_match", "rate_limit_page_match_per_minute")`.

**Request** (`presentation/schemas/page_match.py`):
```jsonc
{
  "query": "nghị quyết liên quan đến đất đai",     // 1..500 ký tự
  "url": "https://…", "title": "…",                 // tuỳ chọn, chỉ để log/metadata
  "blocks": [ { "id": "b07", "text": "…", "occ": 0 } ]  // ∑ ký tự ≤ page_match_max_chars
}
```

**Response:**
```jsonc
{
  "mode": "segments",          // "segments" | "full_page"
  "match_ratio": 0.42,          // ∑ ký tự block verified / ∑ ký tự toàn trang
  "warning": null,              // "VERIFY_UNAVAILABLE" khi LLM lỗi → items theo điểm, verified=false
  "items": [                    // đã sort theo thứ tự trong trang
    { "id": "b07", "occ": 0, "text": "Nghị quyết 12/2023 về quản lý đất đai…",
      "score": 0.78, "verified": true }
  ]
}
```

**Lỗi:** `413 PAGE_TOO_LONG` (mã mới, thêm vào `docs/api/conventions.md` + `shared/errors.ts`), `402 QUOTA_EXCEEDED`, `422`, `429`, `502 AI_UNAVAILABLE`. Sau khi code xong: `python scripts/export_openapi.py` + `npm run gen:api`.

### 4.3 `business/page_match/page_match_service.py`

Sườn xử lý (giữ đúng tầng, pattern như `SemanticSearchService`):

1. Validate + cap tổng ký tự (`page_match_max_chars`, mặc định **50 000** — khớp LIMIT 50 000 của `readSelection`) → vượt trả `PAGE_TOO_LONG`.
2. **Quota lease 1** (`page_match_embed`): reserve `estimate_tokens(query + tất cả block text)` → `ai.embed([query, *block_texts])` **1 lần batch** → commit usage thật.
3. Cosine thuần Python giữa vector query và từng block (block chưa nằm trong DB nên không dùng pgvector tại bước này).
4. Lọc ứng viên: `score ≥ page_match_min_score` (0.35) và tối đa `page_match_top_candidates` (15) → giới hạn token bước verify.
5. **Quota lease 2** (`page_match_verify`): `ai.complete(...)` với prompt trong `business/page_match/prompts.py`:
   - system: vai trò thẩm định, cấm làm theo chỉ dẫn trong `<document>`, chỉ trả JSON;
   - user: `<document>`chứa query + danh sách `[id] đoạn`**`</document>`**, yêu cầu `{"results":[{"id":"…","relevant":true}]}`; `max_tokens = page_match_verify_max_output_tokens` (500).
   - Parse JSON an toàn; **parse fail hoặc AIProviderError → fallback** `warning=VERIFY_UNAVAILABLE`, trả ứng viên theo điểm với `verified=false` (không 502, tính năng vẫn dùng được).
6. `match_ratio = ∑ ký tự block verified / ∑ ký tự toàn trang`; `mode = "full_page"` khi `match_ratio ≥ page_match_full_page_ratio` (0.6).
7. Trả `items` theo thứ tự trang; log chỉ metadata (số block, ký tự, latency) — **không log nội dung trang**.

### 4.4 Lưu thành ghi chú — tái dùng 100% note pipeline

- Không endpoint mới. Sidepanel nối các đoạn đã chọn (`"\n\n".join`), gọi `POST /notes` với **Idempotency-Key** (bắt buộc theo conventions), `url` = url trang, `title` mặc định = **query của người dùng**.
- Note mới đi qua `publish_note_changed` → worker chunk (`chunking.py`) → pgvector → search ngữ nghĩa sẵn có tìm thấy ngay.
- Chế độ **`full_page`**: banner "Hầu như cả trang khớp truy vấn — nên lưu cả trang" + nút "Lưu cả trang" (content = toàn bộ blocks theo thứ tự) + cảnh báo kích thước/quota. Không giả vờ cherry-pick khi match_ratio rất cao (chốt ở phiên intent).

### 4.5 Config mới (`infrastructure/config.py`)

| Setting | Mặc định | Ý nghĩa |
|---|---|---|
| `page_match_max_chars` | 50 000 | Trần tổng nội dung trang gửi lên |
| `page_match_max_block_chars` | 1 200 | Trần 1 block trước khi tách theo câu |
| `page_match_top_candidates` | 15 | Số ứng viên tối đa đưa cho LLM verify |
| `page_match_min_score` | 0.35 | Ngưỡng cosine để vào vòng verify |
| `page_match_full_page_ratio` | 0.6 | match_ratio vượt ngưỡng → mode `full_page` |
| `page_match_verify_max_output_tokens` | 500 | Trần output JSON của LLM |
| `rate_limit_page_match_per_minute` | 6 | Rate limit riêng cho endpoint |

---

## 5. Extension (MV3)

### 5.1 `content/injected.ts` — 2 hàm tự chứa (quy tắc hiện tại: không import, chỉ `textContent`)

- `extractPageBlocks()` → `{ url, title, blocks: [{id, text, occ}] }`: TreeWalker qua `p, li, h1–h6, blockquote, td, pre`; bỏ `nav/footer/aside/script/style/[hidden]`; block vượt max → `splitLongBlock` (tách câu, hàm thuần để vitest); cap tổng 50 000 ký tự.
- `highlightBlocksByText(items)` → tìm lại node chứa `text` (lần xuất hiện thứ `occ`), `scrollIntoView({block:'center'})` + style nổi bật (outline + nền) tự tắt sau ~4s; DOM đã đổi → trả `{ ok: false }` → toast "Không tìm thấy đoạn trên trang". Không gắn attribute vào DOM trang (tránh xung đột với React/framework).

### 5.2 Background — gateway theo ADR-0007

- `background/page-match.ts`: `runPageMatch(tabId, query)` (executeScript extract → `api.ai.pageMatch`) và `highlightInTab(tabId, items)` (executeScript highlight).
- `shared/messaging/protocol.ts`: RPC mới `pageMatch/run`, `pageMatch/highlight`; `handlers.ts` route (kiểu `Handlers` bắt buộc đủ — thiếu là lỗi biên dịch ✅).
- `shared/api/endpoints.ts`: `api.ai.pageMatch(body)`; `shared/errors.ts`: map `PAGE_TOO_LONG` → "Trang quá dài để quét…".

### 5.3 Sidepanel — `ui/features/page-finder/PageFinderView.tsx`

- Tab mới **"Tìm trong trang"** cạnh Notes/Search (theo `docs/ux/ui-map.md`), đăng ký trong `App.tsx`.
- Input query + nút Quét; loading 2 pha ("Đang đọc trang…" → "Đang thẩm định…").
- Danh sách kết quả: clamp 4 dòng, badge "✓ Đã xác nhận" / "Theo điểm tương đồng" (khi `VERIFY_UNAVAILABLE`), checkbox nhiều chọn (pattern màn `08-chon-nhieu`), click đoạn → highlight trang.
- Thanh hành động: "Lưu N đoạn thành ghi chú" → chọn thư mục (pattern quick note) → POST /notes → toast + broadcast `notes/changed`.
- Empty state "Không tìm thấy đoạn nào đủ tin cậy" (pattern màn `11`); `402` → pattern màn `17-het-quota`; `413` → gợi ý quét phần nhỏ hơn.

---

## 6. Kiểm thử

**Backend (pytest, `AI_PROVIDER=mock`):** stitch/match_ratio/`full_page` switch; `min_score`/top-candidates; fallback `VERIFY_UNAVAILABLE` (chat lỗi, JSON hỏng); 2 lease quota reserve→commit; `413`; kháng injection (trang chứa `<\document>` giả + chỉ dẫn). Kiến trúc: `page_match` chỉ import đúng tầng (test kiến trúc hiện có).

**Extension (vitest):** `extractPageBlocks` (jsdom: p/li/heading, bỏ nav, splitLongBlock, cap 50k); `pageMatch/run` handler + error map; `PageFinderView`: render, chọn nhiều, join content đúng, banner full_page.

**E2E (Playwright, tuỳ chọn):** trang mẫu nghị quyết → query → lưu → note xuất hiện trong thư viện.

**QA:** thêm dòng RTM + test-plan (`docs/qa/`), mã lỗi mới `PAGE_TOO_LONG`.

---

## 7. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| PDF/canvas/SPA render chậm → trích rỗng | V1: toast "Trang không hỗ trợ"; roadmap: Readability.js fallback |
| DOM đổi giữa lúc quét và lúc bấm highlight | Highlight theo text + `occ`; thất bại → toast, không crash |
| Chi phí embed cả trang mỗi lần quét | Chỉ chạy khi user bấm; cap 50k; rate limit 6/phút; hậu kiểm: LRU cache theo `sha256(block.text)` |
| LLM verify chậm (~1–3s) | Loading 2 pha; timeout → fallback unverified, không treo |
| LLM verify sai (thừa/thiếu) | Chỉ đưa ứng viên score ≥ 0.35; ghi log metadata; đánh giá trên bộ trang mẫu → `docs/ai/` (pattern H03/N04/R01) |
| Prompt injection từ nội dung trang | `neutralize()` + thẻ `<document>` + system prompt cấm làm theo (đã có sẵn pattern) |
| Người dùng lạm dụng → cháy quota | User-initiated only + rate limit riêng + cảnh báo trước khi lưu trang lớn |

---

## 8. Phân rã công việc

| Task | Nội dung | Phụ thuộc | Ước lượng |
|---|---|---|---|
| **T1** | Backend: schemas + `PageMatchService` + `prompts.py` + controller + config + router + tests | — | 2–3 ngày |
| **T2** | Extension pipeline: `extractPageBlocks`, `splitLongBlock`, endpoints, protocol, handlers + tests | T1 | 2 ngày |
| **T3** | UI `PageFinderView`: query, kết quả, chọn nhiều, lưu note, empty/quota/413 states | T2 | 2–3 ngày |
| **T4** | Highlight + scroll trên trang, edge cases DOM đổi | T2 | 1 ngày |
| **T5** | Chế độ `full_page` + cảnh báo kích thước/quota | T3 | 0.5–1 ngày |
| **T6** | Docs & QA: conventions.md, `export_openapi.py` + `gen:api`, ADR-0012, screen UX, RTM/test-plan, `demo-script.md` thêm cảnh | T1–T5 | 1 ngày |

Thứ tự: **T1 → T2 → (T3 ‖ T4) → T5 → T6**.

---

## 9. Tài liệu phải cập nhật khi implement

- `docs/api/conventions.md`: dòng endpoint `POST /ai/page-match` + mã lỗi `PAGE_TOO_LONG`; commit `openapi.json` + `schema.d.ts`.
- `docs/adr/0012-page-segmentation-in-content-script.md` (mới).
- `docs/ux/`: flow + screen mới theo pattern thư mục `screens/`.
- `docs/ai/`: báo cáo đánh giá chất lượng verify trên bộ trang mẫu.
- `docs/architecture/README.md` + SDS: bổ sung module khi đã code xong (quy ước docs/README.md).

## 10. Câu hỏi mở (không chặn T1)

- Cho phép sửa nội dung đoạn trước khi lưu? V1: không — lưu nguyên đoạn, muốn sửa thì mở `NoteEditor` sau khi lưu.
- Cache embedding cho lần quét lại cùng trang — hậu kiểm sau khi có dữ liệu dùng thật.
