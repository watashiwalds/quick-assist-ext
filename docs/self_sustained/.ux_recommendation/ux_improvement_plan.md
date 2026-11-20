# Kế hoạch tổng quan — Cải thiện UX Thư viện, Tìm trong trang, Hỏi AI

> Nguồn yêu cầu: `docs/self_sustained/ux_recommendation.md`  
> Trạng thái: kế hoạch tổng quan, chưa triển khai  
> Phạm vi: full-stack (FastAPI + extension React/TypeScript)

## 1. Problem Statement

**How Might We** — Làm cho việc tìm kiếm và duyệt ghi chú phản ánh đúng cấu trúc **"nguồn → ghi chú"**, giảm nhiễu danh sách và cho phép thao tác hàng loạt, trong khi vẫn kiểm soát chi phí AI và thống nhất giao diện giữa Thư viện – Tìm trong trang – Hỏi AI?

## 2. Người dùng & tiêu chí thành công

**Người dùng chính:** cá nhân tích lũy ghi chú từ nhiều website, thường tra cứu lại, hỏi AI trên ghi chú và cần dọn dẹp thư viện theo nguồn.

**Thành công khi:**

- Tìm được nguồn/ghi chú đúng trong **≤ 2 lần thử**; danh sách không bị pha loãng bởi quá nhiều ghi chú cùng một nguồn.
- Chuyển nhiều ghi chú sang thư mục khác trong **≤ 3 thao tác**, không phải sửa từng ghi chú.
- Tìm trong trang **không cắt im lặng**: người dùng biết trước độ dài/chi phí và chọn phạm vi quét.
- Hỏi AI dùng đúng **5 lượt gần nhất trong phiên đang mở**, không lẫn phiên khác; thời gian phiên chỉ đổi khi **gửi câu hỏi**.
- Không tăng đáng kể quota AI; các thay đổi retrieval có eval/kiểm thử trước khi chốt ngưỡng.

## 3. Nguyên tắc thiết kế

1. **Source-first:** "nguồn" = website/domain gốc (`Note.domain`, lấy từ hostname của URL). Chọn top 5 nguồn trước, rồi mới chọn ghi chú trong từng nguồn.
2. **Một contract truy xuất dùng chung** cho Thư viện và RAG, tránh hai luồng lọc/nhóm lệch nhau.
3. **Tin cậy phải giải thích được:** hiển thị confidence/score, nói rõ khi nào là fallback không có LLM.
4. **Dùng chung token/component** nhưng không big-bang redesign toàn bộ giao diện.
5. **Chi phí AI có kiểm soát:** ước lượng trước, chia lô, báo tiến độ, dùng quota lease và có thể huỷ.

## 4. Nhóm phạm vi & thứ tự thực hiện

| Thứ tự | Nhóm phạm vi | Nội dung chính | Phụ thuộc | Ước lượng thô |
|---|---|---|---|---|
| **Phase 0** | Quick wins & nền tảng | Chat timestamp, context per-session, câu hỏi gợi ý, token màu rail | — | 1–1,5 ngày |
| **Phase 1** | Truy xuất chung (backend) | Source-first top-5 domain, top-n note, ngưỡng OR, contract dùng chung, RAG 3 note/nguồn | — | 4–6 ngày |
| **Phase 2** | Thư viện | Nhóm theo nguồn, summary-first, 3 note/nguồn + Xem thêm, bulk move | Phase 1 | 4–5 ngày |
| **Phase 3** | Tìm trong trang | Cảnh báo trước quét, chọn phạm vi, batch + progress, confidence ≥ 50%, sort | Phase 0 | 3–5 ngày |
| **Phase 4** | Hỏi AI — hiển thị nguồn nhóm | Nhóm chip nguồn theo domain, citation theo note, chi tiết nguồn | Phase 1 | 1–1,5 ngày |
| **Phase 5** | Hardening | Component dùng chung, e2e/a11y, docs/ADR, hiệu năng/quota | Tất cả | 2–3 ngày |

**Thứ tự đề xuất:** Phase 0 → Phase 1 → Phase 2 → Phase 4 → Phase 5; Phase 3 có thể chạy song song với Phase 1–2 vì độc lập với retrieval.  
Nếu có hai người, Phase 3 (Tìm trong trang) và Phase 1–2 có thể làm song song.

---

## 5. Chi tiết theo nhóm

### 5.1. Chung — Source-first retrieval contract

**Hiện trạng:**

- `SemanticSearchService.retrieve()` trả `SearchResult` phẳng (chunk), `hybrid_search` chỉ trả điểm RRF, chưa có cosine.
- `Note.domain` đã có (hostname từ URL); `NoteBrief` đã có `domain`.
- Thư viện và RAG cùng gọi `SemanticSearchService.retrieve()` nhưng xử lý kết quả khác nhau.

**Thay đổi:**

1. **Mở rộng `ChunkHit`:** thêm `similarity` (cosine 0–1) bên cạnh `score` (RRF). SQL hybrid search trả thêm `1 - (embedding <=> query_vec)`.
2. **Gom theo nguồn:** nhóm chunk theo `NoteBrief.domain`; ghi chú không có domain vào nhóm `"Không rõ nguồn"`.
3. **Xếp hạng nguồn:** `source_score = max(similarity của các note)`, tie-break bằng `max(RRF)`, sau đó số note đạt ngưỡng.
4. **Top 5 nguồn**, mỗi nguồn lấy tối đa:
   - **Thư viện:** trả tối đa 10 note/nguồn, hiển thị 3 note + nút "Xem thêm".
   - **RAG:** 3 note/nguồn, 1 chunk tốt nhất/note (tối đa 15 chunk).
5. **Ngưỡng:** một note đạt nếu `similarity >= 0.5` **hoặc** `RRF >= 0.03` (OR, không AND).
   - `0.03` là ngưỡng RRF "khớp cả vector lẫn từ khoá"; `0.5` là cosine "tương đương 50% tin cậy".
   - Không dùng RRF 0.03 một mình vì sẽ loại câu hỏi diễn đạt lại chỉ khớp ngữ nghĩa.
6. **Contract mới:**
   - `SearchOut { sources: SearchSourceOut[] }`
   - `SearchSourceOut { domain, label, source_rank, note_count, notes: SearchNoteOut[] }`
   - `SearchNoteOut { note_id, title, url, summary, snippet, score, similarity }`
   - `ChatSource` thêm `source_index`, `source_domain`; `index` vẫn là số trích dẫn `[n]` theo note.
7. **RAG prompt:** nhóm theo nguồn, mỗi note có `[n]`; thêm trần ngữ cảnh (`CHAT_CONTEXT_MAX_CHARS`, ví dụ 18.000 ký tự) và cắt note xếp hạng thấp nếu vượt.
8. **Empty state:** "Không có nguồn/ghi chú đủ tin cậy" + gợi ý diễn đạt khác, bỏ lọc thư mục, hoặc chờ ghi chú được index.

**File dự kiến:**

- `apps/api/src/quickassist/data_access/repositories/note_chunk_repository.py`
- `apps/api/src/quickassist/business/semantic_search/semantic_search_service.py`
- `apps/api/src/quickassist/business/rag/rag_service.py`
- `apps/api/src/quickassist/business/rag/prompts.py`
- `apps/api/src/quickassist/presentation/schemas/search.py`, `rag.py`
- `apps/extension/src/shared/api/types.ts` (regenerate `schema.d.ts`)
- `apps/extension/src/background/handlers.ts`, `src/shared/messaging/protocol.ts`

**Kiểm thử:**

- Unit: gom domain, top 5, xếp hạng note, ngưỡng OR, nhóm "Không rõ nguồn", 3 note/nguồn.
- Integration: search API trả grouped; RAG nhận đúng 5 nguồn × 3 note × 1 chunk; prompt có đủ nguồn.
- Eval: 20–30 câu hỏi (trực tiếp, diễn đạt lại, không dấu, hỏi tổng quan) — đo recall, tỉ lệ rỗng, số nguồn trả về.

---

### 5.2. Thư viện

**Hiện trạng:**

- `NotesView` render danh sách phẳng `visible.map(NoteCard)`; `NoteCard` hiển thị `note.content` excerpt.
- `NoteReader` đã hiển thị `summary_text` trước nội dung, nhưng danh sách thì chưa.
- Chỉ có xoá hàng loạt; chưa có chuyển thư mục hàng loạt.
- `SearchView` (tab Tìm kiếm ẩn) cũng dùng `search/query` và render phẳng.

**Thay đổi:**

1. **Nhóm theo nguồn (cả browse và search):**
   - Danh sách mặc định: nhóm theo `domain`, sắp xếp nhóm theo số note/updated_at; trong nhóm sắp xếp theo updated_at.
   - Kết quả tìm kiếm: tối đa 5 nhóm nguồn, mỗi nhóm 3 note + "Xem thêm" (tối đa 10 note/nguồn).
   - Nhóm "Không rõ nguồn" đặt cuối.
2. **Summary-first:**
   - `NoteCard`: hiển thị `summary_text` nếu có, kèm badge "Tóm tắt"; nếu không, dùng excerpt nội dung.
   - Header nhóm: hiển thị domain, số note, và "Tóm tắt từ ghi chú" ghép từ tối đa 2 `summary_text`/excerpt gần nhất (cắt ngắn). **Không gọi AI.**
   - `NoteReader`: giữ summary card trước nội dung (đã có).
3. **Bulk move:**
   - Chế độ chọn đã có; thêm nút **"Chuyển thư mục"** cạnh "Xoá".
   - Dialog chọn thư mục đích (gồm Inbox); xác nhận số lượng.
   - **Chỉ di chuyển ghi chú đã chọn** (theo lựa chọn của bạn).
   - Header nhóm có nút **"Chọn cả nhóm"** để chọn nhanh toàn bộ note trong nhóm, sau đó người dùng bấm Chuyển thư mục.
   - API mới: `notes/move` (RPC + `POST /notes/move`), request `{ ids, folder_id }`, response `{ moved, missing }`.
   - Backend: kiểm tra ownership, folder hợp lệ, cập nhật `Note.folder_id` + `NoteChunk.folder_id` trong một transaction; broadcast `notes/changed`.
4. **Bộ lọc số nguồn:**
   - Đổi select "Tối đa 5/10/20" thành **"Số nguồn tối đa"**, mặc định 5; mỗi nguồn 3 note.
   - RAG cố định 5 nguồn.
5. **SearchView (tab ẩn):** dùng chung component `SearchResults` với Thư viện; không thiết kế lại.

**File dự kiến:**

- `apps/extension/src/ui/features/notes/NotesView.tsx`, `NoteCard.tsx`, `NoteReader.tsx`
- `apps/extension/src/ui/features/search/SearchView.tsx`
- `apps/extension/src/ui/features/notes/MoveNotesDialog.tsx` (mới)
- `apps/extension/src/ui/features/notes/SourceGroup.tsx` (mới)
- `apps/extension/src/background/handlers.ts`, `src/shared/messaging/protocol.ts`
- `apps/api/src/quickassist/business/notes/notes_service.py`
- `apps/api/src/quickassist/presentation/api/v1/controllers/notes_controller.py`
- `apps/api/src/quickassist/presentation/schemas/note.py`

**Kiểm thử:**

- UI: nhóm đúng domain, summary-first, "Xem thêm", chọn nhóm, move dialog, toast, reload sau move.
- API: ownership, folder không hợp lệ, note đã bị xoá, cập nhật chunk folder, transaction rollback.
- E2E: `c05-library.spec.ts` mở rộng cho group + bulk move.

---

### 5.3. Tìm trong trang

**Hiện trạng:**

- `page_match_max_chars = 50_000` là hard limit; `truncated` chỉ báo sau khi quét.
- LLM trả `relevant: true/false` nhị phân; `PageMatchItemOut` chỉ có `verified` và `score` (cosine).
- Backend sắp item theo thứ tự trang; UI không có sort toggle.
- `getRawHtml` chỉ trả HTML/bytes, chưa có ước lượng độ dài text trước khi quét.

**Thay đổi:**

1. **Cảnh báo trước khi quét:**
   - Thêm `textChars` vào `RawPage` (đếm `clone.textContent.length` sau khi bỏ script/style).
   - Với nội dung dán, dùng `pasted.length`.
   - Nếu `textChars > 50_000` (hoặc paste > 50.000), hiện dialog:
     - "Nội dung ~X ký tự, ước tính ~Y token, chia Z lô."
     - Chọn **"Quét 50k đầu"** (mặc định) hoặc **"Quét toàn bộ"**.
     - Có nút Huỷ; không tự quét khi chưa xác nhận.
2. **Quét toàn bộ:**
   - `pageMatch/run` nhận `scanAll?: boolean`; backend bỏ `max_chars` khi `scanAll=true` (không đặt trần, theo lựa chọn của bạn).
   - HTML payload vẫn có trần an toàn `page_match_max_html_bytes = 2 MB`.
   - Chia lô cố định: `page_match_embed_batch_blocks = 32` (hoặc ~16k ký tự/lô).
   - Embed query một lần; embed từng lô block; một quota lease cho toàn bộ; commit tổng usage; release khi lỗi/huỷ.
   - Timeout **tính theo lô** (`page_match_embed_timeout_seconds`, ví dụ 30s/lô); lô lỗi → dừng, báo lỗi có thể thử lại với 50k.
3. **Báo tiến độ:**
   - Thêm luồng SSE cho page-match (hoặc endpoint stream tương tự RAG):
     - event `extract`, `batch` (`i/n`), `verify`, `done`, `error`.
   - Background `runPageMatch` mở stream, forward `pageMatch/progress` qua broadcast.
   - UI hiện progress bar "Đang xử lý lô i/n" + nút Huỷ; không để người dùng nhìn spinner mơ hồ.
   - Nếu chưa làm SSE trong MVP: hiện progress không xác định + số lô ước tính; nhưng đây là **chi phí kỹ thuật lớn nhất** của Phase 3, nên đưa vào kế hoạch chính.
4. **Confidence ≥ 50%:**
   - Đổi prompt LLM trả `confidence: 0..1` cho từng block; parser chấp nhận cả `confidence` và `relevant` cũ (true → 1.0, false → 0.0).
   - `PageMatchItemOut` thêm `confidence`.
   - Lọc `confidence >= 0.5`; `verified = true` khi LLM đã đánh giá, `false` khi fallback.
   - Fallback khi LLM lỗi/timeout/JSON hỏng: dùng cosine `>= 0.5`, `verified=false`, banner "AI chưa thẩm định được".
   - Giữ `page_match_min_score = 0.35` làm ngưỡng **candidate** đưa vào LLM, không phải ngưỡng cuối.
5. **Sort toggle:**
   - Thêm segmented control: **"Thứ tự trong trang"** (mặc định) / **"Tin cậy giảm dần"**.
   - Sort ở client trên bản copy; `selected` theo id không đổi.
   - Khi lưu, luôn sắp theo **thứ tự trang** để ghi chú giữ mạch đọc; thêm hint nhỏ "Khi lưu, các đoạn xếp theo thứ tự trong trang."
   - Hiển thị `confidence` thay cho `score` ở badge; tooltip giải thích nguồn confidence.
6. **Empty state:** "Không tìm thấy đoạn nào đủ tin cậy" + gợi ý đổi cách diễn đạt, dùng từ khoá có trong trang, hoặc bôi đen thủ công.

**File dự kiến:**

- `apps/extension/src/content/injected.ts` (`RawPage.textChars`)
- `apps/extension/src/background/page-match.ts`
- `apps/extension/src/ui/features/page-finder/PageFinderView.tsx`
- `apps/extension/src/shared/messaging/protocol.ts`
- `apps/api/src/quickassist/business/page_match/page_match_service.py`, `prompts.py`
- `apps/api/src/quickassist/presentation/api/v1/controllers/page_match_controller.py`
- `apps/api/src/quickassist/presentation/schemas/page_match.py`
- `apps/api/src/quickassist/infrastructure/config.py`

**Kiểm thử:**

- Unit: parser confidence/relevant, threshold 0.5, fallback cosine 0.5, batching, timeout từng lô.
- UI: dialog cảnh báo, chọn 50k/toàn bộ, progress, sort toggle, lưu theo thứ tự trang.
- E2E: `ux-screens.spec.ts` / test page-finder; trang dài, paste dài, LLM lỗi.

---

### 5.4. Hỏi AI

**Hiện trạng:**

- `useChatSessions.merge()` luôn đặt `updatedAt: now`, kể cả khi `switchSession`/`pagehide` chỉ xem hoặc đóng phiên.
- `merge()` luôn đưa phiên vừa merge lên đầu mảng → xem phiên cũng làm phiên nhảy thứ tự.
- `useChat.replace()`/`reset()` chỉ set state, chưa cập nhật `msgsRef.current` ngay → nếu gửi ngay sau khi chuyển phiên có thể đọc nhầm history phiên cũ.
- `buildHistory()` lấy từ `msgsRef.current` của phiên đang mở (đúng thiết kế per-session), nhưng cần test hồi quy.
- `EXAMPLES` hiện là 3 câu hỏi cụ thể; rail `.session-pane`/`.session-foot` dùng `--surface` (xám) trong khi các rail khác dùng `--bg` (trắng).

**Thay đổi:**

1. **Timestamp & thứ tự:**
   - `merge()` chỉ bump `updatedAt` khi **số tin nhắn người dùng tăng** (gửi câu hỏi mới) hoặc phiên mới.
   - Khi chỉ xem/đổi phiên, nhận câu trả lời, đổi tên, đóng panel: giữ nguyên `updatedAt` và **không đưa phiên lên đầu**; cập nhật message tại chỗ.
   - `switchSession`/`pagehide` không bump; `renameSession` không bump.
2. **Context 5 lượt theo phiên:**
   - `replace()`/`reset()` cập nhật `msgsRef.current` (và `folderRef` nếu cần) ngay lập tức.
   - `buildHistory()` chỉ dùng messages của phiên đang mở; tối đa 5 cặp hỏi–đáp hoàn chỉnh.
   - Thêm hint nhỏ cạnh composer: "Ngữ cảnh: 5 lượt gần nhất trong phiên này."
   - Test hồi quy: tạo 2 phiên khác nhau, chuyển phiên, gửi câu hỏi → `askChat` chỉ nhận history của phiên đích.
3. **Câu hỏi gợi ý tổng quan:**
   - "Tóm tắt những chủ đề chính trong ghi chú của tôi"
   - "Ghi chú của tôi tập trung ở những nguồn nào?"
   - "Những ý chính nào xuất hiện trong nhiều ghi chú?"
   - (Có thể chỉnh copy; tránh câu hỏi cần dữ liệu thời gian vì prompt không gửi ngày.)
4. **Nguồn nhóm trong câu trả lời (sau Phase 1):**
   - `Sources` component nhóm chip theo `source_index`/`source_domain`; nhãn "Nguồn (5)" là số domain, bên trong là các note chip.
   - `Chi tiết nguồn` nhóm theo domain; citation `[n]` vẫn theo note để bấm mở đúng ghi chú.
   - Giữ `source-chip`/`source-card` hiện có, chỉ thêm lớp nhóm và số đếm.
5. **Màu rail:**
   - Thêm token `--rail-bg: var(--bg)` và `--rail-border: var(--border-soft)`.
   - `.session-pane`, `.session-foot` dùng token này thay vì `--surface`; áp dụng cùng token cho `.folder-rail`, `.pf-rail` để nhất quán.
   - Kiểm tra dark mode và test contrast hiện có.

**File dự kiến:**

- `apps/extension/src/ui/features/chat/useChatSessions.ts`
- `apps/extension/src/ui/features/chat/useChat.ts`
- `apps/extension/src/ui/features/chat/ChatView.tsx`
- `apps/extension/src/ui/styles.css`
- `apps/extension/tests/chat-sessions.test.ts`
- `apps/extension/tests/ui/chat-sessions.test.tsx`

---

### 5.5. Tài nguyên giao diện dùng chung

**Token mới (CSS):**

- `--rail-bg`, `--rail-border`, `--pane-head-h`, `--pane-pad`, `--card-pad`, `--group-head-bg`.

**Component nhỏ (TypeScript):**

- `PaneHeader` — title, subtitle, actions (dùng cho Thư viện, Tìm trong trang, Hỏi AI).
- `SourceChip` / `SourceCard` — hiển thị nguồn và note nguồn (tái dùng từ ChatView).
- `ConfidenceBadge` — hiển thị % tin cậy/score, có tooltip.
- `SegmentedControl` — sort toggle (trang/tin cậy).
- `BulkActionBar` — số đã chọn + hành động (chuyển thư mục/xoá).
- `GroupSection` — header nhóm nguồn có thể mở/đóng, `aria-expanded`.
- `MoveNotesDialog` — chọn thư mục đích.

**CSS:**

- Gom selector trùng: `.folder-rail` / `.pf-rail` / `.session-pane`; `.pane-head` / `.pf-head` / `.conv-head`.
- Giữ class cũ làm alias trong giai đoạn chuyển tiếp; không rename toàn bộ một lần.
- Chỉ tách component khi có ≥ 2 nơi dùng thật; tránh abstraction sớm.

---

## 6. Hợp đồng dữ liệu dự kiến

### 6.1. Search

```ts
type SearchOut = {
  sources: SearchSourceOut[]
}

type SearchSourceOut = {
  domain: string | null
  label: string          // domain hoặc "Không rõ nguồn"
  source_rank: number
  note_count: number
  notes: SearchNoteOut[]
}

type SearchNoteOut = {
  note_id: string
  title: string | null
  url: string | null
  summary: string | null
  snippet: string
  score: number          // RRF
  similarity: number     // cosine 0..1
}
```

### 6.2. Chat source

```ts
type ChatSource = {
  index: number          // số trích dẫn [n] theo note
  source_index: number   // nhóm nguồn 1..5
  source_domain: string | null
  note_id: string
  chunk_id: string
  title: string | null
  url: string | null
  snippet: string
}
```

### 6.3. Page match

```ts
type PageMatchItemOut = {
  id: string
  occ: number
  text: string
  score: number          // cosine
  confidence: number     // LLM confidence hoặc cosine fallback, 0..1
  verified: boolean      // true = LLM đã đánh giá
}

type PageMatchIn = {
  query: string
  html?: string
  text?: string
  scanAll?: boolean      // true = không giới hạn 50k, chia lô
}
```

### 6.4. Bulk move

```ts
// RPC notes/move
type NotesMoveIn = { ids: string[]; folderId: string | null }
type NotesMoveOut = { moved: number; missing: string[] }
```

---

## 7. Giả định cần kiểm chứng

- [ ] **Domain là khóa nhóm đúng** với người dùng: kiểm tra 20–30 ghi chú thực tế; xác nhận ghi chú cùng website nằm cùng nhóm, ghi chú không URL vào nhóm "Không rõ nguồn".
- [ ] **Ngưỡng OR giữ recall:** eval 20–30 câu hỏi; đo tỉ lệ rỗng, số nguồn trả về, chất lượng top-3 note. Nếu cosine 0.5 quá chặt, thử 0.45.
- [ ] **LLM confidence calibrated:** lấy 20–30 đoạn mẫu, so confidence với đánh giá người; điều chỉnh prompt/threshold nếu precision thấp.
- [ ] **Quét toàn bộ khả thi:** đo token/thời gian cho trang 50k/150k/300k ký tự; xác nhận batch size và timeout từng lô.
- [ ] **Bulk move selected-only đủ đáp ứng nhu cầu "move nhóm":** test usability với 3–5 người dùng; nếu họ muốn move cả nhóm một bấm, cân nhắc thêm "Chọn cả nhóm + move" (không tự động move note ẩn).
- [ ] **Component dùng chung không gây regression:** screenshot/e2e trước–sau; test contrast.
- [ ] **Context 5 lượt per-session không rò:** test 2 phiên; kiểm tra request body gửi server.

---

## 8. MVP scope

**Trong MVP:**

- Phase 0: timestamp, per-session context guard, câu hỏi gợi ý, rail color token.
- Phase 1: source-first top-5, top-3 note/nguồn, ngưỡng OR, search API grouped, RAG grouped + context budget.
- Phase 2: Thư viện nhóm theo nguồn, summary-first, 3 note/nguồn + Xem thêm, bulk move selected.
- Phase 3: cảnh báo trước quét + chọn 50k/toàn bộ, batch + progress, confidence ≥ 50%, fallback cosine 0.5, sort toggle, lưu theo thứ tự trang.

**Có thể cắt khỏi MVP nếu thời gian eo hẹp:**

- SSE progress cho page-match → thay bằng progress không xác định + ước lượng số lô (nhưng vẫn giữ batch/timeout).
- "Xem thêm" quá 10 note/nguồn → chỉ hiển thị 3 note + tổng số còn lại.
- Group summary ghép 2 note → chỉ hiển thị domain + số note.
- Sort toggle → có thể để Phase sau nếu Phase 3 quá tải.

**Không cắt:**

- Ngưỡng tin cậy và fallback (vì đây là yêu cầu cốt lõi).
- Bulk move selected + chọn cả nhóm.
- Per-session context + timestamp fix.

---

## 9. Not Doing (và lý do)

- **Không tự tạo summary nhóm bằng AI** — tốn quota, cần cache/trạng thái chờ; dùng summary_text/excerpt trước.
- **Không clustering theo chủ đề** — grouping theo domain là đủ cho phạm vi này; clustering cần embedding/ngưỡng riêng.
- **Không move toàn bộ note trong nhóm nếu chưa chọn** — bạn đã chọn "chỉ ghi chú đã chọn"; giữ an toàn dữ liệu.
- **Không thay search engine/RRF bằng reranker mới** — TODO R02 để phase sau; ưu tiên ổn định.
- **Không redesign toàn bộ navigation/tab** — chỉ dùng chung token/component trong các màn hiện có.
- **Không đồng bộ chat lên server** — giữ ADR-0012 (chat chỉ lưu cục bộ).
- **Không virtualization danh sách** trừ khi đo hiệu năng thấy cần; nhóm có thể mở/đóng giúp giảm tải.

---

## 10. Open questions

1. **Group summary:** ghép 2 summary gần nhất hay chỉ summary của note mới nhất? (Đề xuất: 2, cắt ngắn, label "Tóm tắt từ ghi chú".)
2. **"Xem thêm" tối đa bao nhiêu note/nguồn?** (Đề xuất: 10; quá 10 chỉ hiện "và N ghi chú khác".)
3. **Batch size page-match:** 32 block hay 16k ký tự/lô? (Đề xuất: 32 block, kiểm tra với block 1200 ký tự.)
4. **Fallback cosine 0.5** có quá chặt không? (Đo eval; nếu rỗng nhiều, hạ 0.45.)
5. **Copy câu hỏi gợi ý** có cần cá nhân hóa theo dữ liệu người dùng không? (Đề xuất: giữ tĩnh, tổng quan.)
6. **Có giữ select "Số nguồn tối đa" 5/10/20** hay cố định 5? (Đề xuất: giữ select, mặc định 5; RAG cố định 5.)
7. **Có cần nút Huỷ giữa chừng cho quét toàn bộ** ngay trong MVP? (Đề xuất: có, ít nhất đóng kết nối và release quota.)
8. **Search tab ẩn** có nên giữ hay gộp vào Thư viện? (Đề xuất: giữ, dùng chung component.)

---

## 11. Test & acceptance checklist

### Phase 0

- [ ] Gửi câu hỏi → `updatedAt` tăng; nhận câu trả lời → không tăng.
- [ ] Chuyển phiên, đổi tên, đóng panel → `updatedAt` không đổi, thứ tự phiên không nhảy.
- [ ] Chuyển phiên rồi gửi ngay → history gửi server chỉ thuộc phiên đích (5 cặp gần nhất).
- [ ] Rail Hỏi AI cùng màu nền với Thư viện/Tìm trong trang ở light & dark.
- [ ] 3 câu hỏi gợi ý mới hiển thị và bấm được.

### Phase 1

- [ ] Search trả tối đa 5 nguồn, mỗi nguồn tối đa 3 note (RAG) / 10 note (library response).
- [ ] Note chỉ khớp ngữ nghĩa (cosine ≥ 0.5) vẫn xuất hiện dù RRF < 0.03.
- [ ] Note khớp cả vector + keyword (RRF ≥ 0.03) vẫn xuất hiện dù cosine < 0.5.
- [ ] Ghi chú không URL vào nhóm "Không rõ nguồn".
- [ ] RAG prompt có 5 nguồn, tối đa 3 note/nguồn, 1 chunk/note; không vượt context budget.
- [ ] Eval: tỉ lệ rỗng không tăng đáng kể so với baseline.

### Phase 2

- [ ] Danh sách Thư viện nhóm theo domain; nhóm mở/đóng được, có `aria-expanded`.
- [ ] NoteCard hiển thị summary_text trước content; fallback excerpt.
- [ ] Search results nhóm theo nguồn, 3 note + Xem thêm.
- [ ] Chọn nhiều note → Chuyển thư mục → note biến mất khỏi thư mục cũ, xuất hiện ở thư mục mới.
- [ ] "Chọn cả nhóm" chọn đúng các note trong nhóm; không tự move note chưa chọn.
- [ ] API move kiểm tra ownership/folder; rollback khi lỗi.

### Phase 3

- [ ] Nội dung > 50k → dialog cảnh báo trước khi quét, có ước lượng token/lô.
- [ ] Chọn "50k đầu" → `truncated=true` và banner; chọn "Toàn bộ" → không cắt, có progress lô i/n.
- [ ] LLM trả confidence; item < 0.5 bị loại; fallback cosine ≥ 0.5 khi LLM lỗi.
- [ ] Sort toggle đổi thứ tự hiển thị; lưu vẫn theo thứ tự trang.
- [ ] Timeout từng lô; lỗi giữa chừng có thông báo và release quota.

### Phase 4

- [ ] Chip nguồn nhóm theo domain; "Nguồn (N)" đếm đúng số domain.
- [ ] Citation `[n]` vẫn mở đúng note; chi tiết nguồn nhóm đúng.
- [ ] Không có nguồn trùng lặp giữa các nhóm; note không domain vào nhóm "Không rõ nguồn".

### Phase 5

- [ ] `npm run typecheck`, `npm run test`, `npm run build` xanh.
- [ ] `pytest` xanh; test mới cho grouping, threshold, bulk move, page-match.
- [ ] E2E `c05-library`, `r05-search`, `x02-chat`, `ux-screens` xanh.
- [ ] Contrast/a11y test xanh; keyboard dùng được group header, sort toggle, dialog.
- [ ] `schema.d.ts` regenerate; không còn type `SearchHit` phẳng ở nơi dùng grouped.
- [ ] Docs/ADR cập nhật: ADR-0006 (threshold/grouping), ADR mới cho page-match streaming/progress nếu chọn SSE.

---

## 12. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Ngưỡng OR làm giảm recall hoặc tăng nhiễu | Trung bình | Eval trước–sau; điều chỉnh cosine 0.5 → 0.45 nếu cần |
| LLM confidence không calibrated | Trung bình | Đo trên mẫu; giữ fallback cosine; hiển thị rõ nguồn confidence |
| Quét toàn bộ tốn quota/thời gian | Cao | Ước lượng trước, batch, timeout/lô, progress, huỷ, quota lease |
| SSE page-match làm tăng độ phức tạp | Trung bình–cao | Tái dùng pattern SSE của chat; nếu MVP gấp, dùng progress không xác định |
| Bulk move ảnh hưởng index/chunks | Trung bình | Transaction, test rollback, broadcast reload |
| Refactor component gây regression | Trung bình | Tách từng bước, screenshot/e2e, giữ class alias |
| Session history rò giữa phiên | Thấp–trung bình | Cập nhật ref đồng bộ trong replace/reset; test 2 phiên |

---

## 13. Việc tiếp theo

1. Chốt 2 quyết định nhỏ: group summary (2 note hay 1 note) và batch size page-match (32 block hay 16k ký tự).
2. Làm Phase 0 trước để có quick win và test nền.
3. Với Phase 1, viết eval baseline trước khi đổi ngưỡng — không chốt 0.5/0.03 chỉ bằng cảm giác.
4. Cập nhật `docs/self_sustained/ux_recommendation.md` thành checklist trạng thái khi từng phase xong.
