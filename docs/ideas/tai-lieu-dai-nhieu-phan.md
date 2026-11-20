# Tài liệu dài như một note mở rộng — Chia phần + `document_id`

**Trạng thái:** đã chốt hướng D2, chia 3 lát  
**Ngày:** 2026-11-19  
**Phạm vi:** backend + extension + evaluation

## Problem Statement

> **HMW mở rộng giới hạn nội dung của note để một tài liệu 150k+ ký tự được lưu, index và tìm kiếm như một mục duy nhất — qua chính luồng note hiện có, không thêm loại đầu vào mới, không phá client cũ, và chi phí tăng có kiểm soát?**

## Người dùng mục tiêu

- **Ai:** người dùng hiện tại của QuickAssist đã dùng note/Thư viện để lưu bài báo, tài liệu học tập, biên bản dài — không phải người dùng mới chỉ muốn upload file.
- **Họ đang làm gì thay thế:** lưu nhiều note nhỏ, cắt bớt nội dung, hoặc chuyển sang Notion/Drive cho tài liệu dài.
- **Tần suất giả định:** vài lần mỗi tuần trong mùa học/nghiên cứu. Đây là **giả định cần validate**, không phải sự thật đã biết.
- **Không nhắm tới:** người dùng cần import PDF/Word/OCR — nhóm này cần một luồng đầu vào riêng, ngoài phạm vi.

## Bối cảnh và quyết định đã chốt

- Backend chặn `POST /notes` ở `MAX_NOTE_CHARS = 20.000` (`413 NOTE_TOO_LONG`). Harness evaluation đang cắt trước 20k, khiến 3 file TXT chỉ còn 12,7–50,5% nội dung.
- Chunking **đã tồn tại** (`note_chunks`, ~1.200 ký tự/chunk). Vấn đề không phải thiếu chunk, mà là một note không được dài quá 20k.
- Chia tài liệu thành nhiều note **không làm giảm tổng chi phí embedding**: 157k ký tự vẫn tạo ~131 chunk. Cái giảm được là payload mỗi request, khả năng index tăng dần và cô lập lỗi.
- Quyết định từ phiên thảo luận:
  - Đây là **năng lực sản phẩm**, nhưng theo hướng **mở rộng giới hạn của note**, không tạo một dạng đầu vào mới.
  - **Client/harness chịu trách nhiệm chia**; backend chỉ validate và lưu.
  - Thư viện hiển thị **một mục tài liệu**, mở ra xem các phần.
  - Ràng buộc: **không phá API cũ**, **hạn chế tăng chi phí**.
  - Thành công: chấp nhận tài liệu dài mà **không ảnh hưởng trải nghiệm note hiện tại**.

## Recommended Direction

**D2 — Tài liệu ảo nhiều phần.** Một tài liệu logic gồm nhiều note vật lý (part) ≤20k, cùng một `document_id`. Không thêm resource `/documents`; mọi thứ đi qua `POST /notes` hiện có với các field optional.

**Vì sao không phải D1:** D1 nhanh hơn nhưng dồn 157k vào một note, làm editor/sync và một job index chịu toàn bộ rủi ro. D2 giữ nguyên đơn vị note ≤20k, chỉ thêm identity để gộp — đúng với ràng buộc “không ảnh hưởng trải nghiệm note hiện tại”.

**Khác biệt:** tài liệu dài vẫn nằm trong cùng Thư viện/search/RAG, không bị đẩy sang một silo import riêng; người dùng không phải học một khái niệm mới.

Ba nguyên tắc:

1. **Một tài liệu = một `document_id`.** Các part chia sẻ title/url/folder; `part_index` đánh từ 0.
2. **Group key đổi thành `document_id ?? domain`.** Note cũ không có `document_id` vẫn gom theo domain như trước. Note mới có `document_id` được gom thành một mục, kể cả khi không có URL.
3. **Mỗi part ≤20k.** Sau khi chia, NoteEditor và sync chỉ phải xử lý từng part nhỏ như hiện tại; không có note 157k trong một row.

### Hợp đồng dữ liệu đề xuất

Thêm vào `notes` (migration mới):

```text
document_id     UUID NULL
part_index      INT NOT NULL DEFAULT 0
part_count      INT NOT NULL DEFAULT 1
original_chars  INT NULL          -- tổng ký tự của cả tài liệu
source_type     VARCHAR(20) NOT NULL DEFAULT 'selection'  -- selection | document
```

Ràng buộc:

```text
UNIQUE (user_id, document_id, part_index) WHERE document_id IS NOT NULL
INDEX  (user_id, document_id)
```

`POST /notes` giữ nguyên đường cũ, thêm đường mới:

```jsonc
// Client gửi một lần, backend tạo các part trong cùng transaction
{
  "title": "Bài báo",
  "url": null,
  "folder_id": null,
  "document_id": "uuid-do-client-sinh",   // optional
  "parts": ["phần 1...", "phần 2..."]      // optional; nếu có thì không gửi content
}
```

- `content` vẫn bắt buộc với client cũ; `parts` là đường optional cho client mới.
- Response trả part 0 kèm `document_id`, `part_count`, `part_ids` và metadata index.
- `GET /notes?document_id=...` trả các part để client poll trạng thái.
- `PATCH /notes/{id}` sửa nội dung một part; sửa title/folder/url lan sang các part cùng `document_id`.
- Xoá/di chuyển: dùng `POST /notes/bulk-delete` và `POST /notes/move` với toàn bộ `part_ids`; không đổi semantics của `DELETE /notes/{id}`.

### Grouping và hiển thị

- `SemanticSearchService` gom theo `document_id` nếu có, fallback `domain`.
- `SearchSourceOut` thêm `document_id`, `source_type`; `label` là title tài liệu với document, domain với note web.
- `SearchNoteOut` thêm `part_index`, `part_count` để UI hiện “Phần 3/8”.
- `groupNotes.ts` gom theo `document_id ?? domain`; group label lấy title của part 0.
- RAG thêm `source_label` và `part_index` vào `ChatSource`; prompt dùng `<source label="...">` khi không có domain. Citation vẫn theo part, nhưng hiển thị tên tài liệu + số phần.

## Ba lát cắt

### Lát 0 — Baseline evaluation (optional, ~0,5 ngày)

Mục đích: biết “nếu index đủ thì chất lượng là bao nhiêu” trước khi đầu tư schema.

- Harness tự chia 3 file TXT thành part ≤20k.
- Gán mỗi file một URL giả duy nhất (ví dụ `https://<slug>.eval.local/`) để grouping theo domain sẵn có tách đúng từng tài liệu.
- Không đổi backend, không đổi extension.
- Chỉ dùng để đo; không phải giải pháp sản phẩm.

**Done khi:** search/RAG/AnswerHit trên 3 file TXT phản ánh nội dung đầy đủ, tách biệt khỏi lỗi truncation.

### Lát 1 — Hợp đồng backend (~2–3 ngày)

- Migration thêm các cột và index ở trên.
- `POST /notes` nhận `parts`, tạo atomic, idempotent theo một key cho cả document.
- `GET /notes?document_id=...`; metadata trong `NoteOut`.
- Grouping `document_id ?? domain` trong search; field mới trong `SearchOut`.
- RAG dùng `source_label`; prompt/citation cập nhật.
- Test: note cũ không đổi hành vi; tạo document 157k; part READY; group đúng; xoá/move theo document.

**Done khi:** một document 157k tạo được qua API, tất cả part `READY`, search trả **một source** cho tài liệu, note ≤20k giữ nguyên contract.

### Lát 2 — Extension UX (~2–3 ngày)

- NoteEditor phát hiện nội dung > ngưỡng chia.
- Hiện modal: số ký tự, số phần, số chunk ước tính, token/quota ước tính; cho xác nhận hoặc huỷ.
- Chia tại ranh giới đoạn → câu → từ; không mất ký tự; target 18k, hard max 20k.
- Lưu một lần qua `POST /notes` với `parts`; hiện tiến độ index theo part.
- Thư viện gom một mục tài liệu; mở ra xem các phần.
- Settings nâng cao: ngưỡng chia mặc định 20k, cho phép hạ xuống; **không được vượt `MAX_NOTE_CHARS` của server**.
- MVP: reader gộp là **read-only**; sửa từng part như note thường.

**Done khi:** dán một tài liệu 157k vào NoteEditor, xác nhận chi phí, lưu thành một mục trong Thư viện, tìm lại được nội dung ở phần cuối.

### Lát 3 — Vòng đời và đo lại (~1–2 ngày)

- Xoá/di chuyển/reindex theo document từ UI.
- Harness bỏ truncation, dùng `document_id`/`parts`, map `qid` → document + part chứa gold.
- AnswerHit kiểm tra **toàn bộ part** của document, không chỉ part top-1.
- Chạy lại full evaluation; so sánh Recall@5, MRR, AnswerHit, RAG citation, PageMatch.
- Cập nhật `BAO_CAO_GIAI_TRINH.md`; chuyển `BAO_CAO_NGUON_KHONG_CAT.md` thành báo cáo “trước/sau” hoặc lưu trữ.

**Done khi:** số liệu TXT tiệm cận HTML; `sources_avg > 1` với corpus nhiều tài liệu; `max_sources` được kiểm chứng.

## Key Assumptions to Validate

### Must be true (dealbreakers)

- [ ] **Người dùng thật sự cần >20k**, không chỉ dataset eval. Đo bằng log độ dài note, số lần dán >20k, hoặc phỏng vấn 5 người dùng. Nếu sai, dừng ở lát 0.
- [ ] **Chia ở 20k không làm giảm retrieval.** A/B trên 3 file TXT với ngưỡng 8k/20k/40k; đo Recall@5, AnswerHit, RAG citation. Nếu giảm, thử overlap 200–500 ký tự hoặc prepend heading.
- [ ] **Một mục + các phần là đủ dễ hiểu.** Prototype với 5 người; task “tìm thông tin ở phần cuối tài liệu 157k”.
- [ ] **Chi phí 157k chấp nhận được.** Đo thực tế ~131 chunk/~40k token embed; kiểm tra quota 1M và thời gian index.

### Should be true (important)

- [ ] **Client cũ không bị ảnh hưởng.** Contract test: extension phiên bản cũ chạy với backend mới; note ≤20k giữ nguyên.
- [ ] **Ranh giới part không cắt mất ngữ cảnh.** Test câu hỏi có gold nằm sát ranh giới; nếu kém, thêm overlap có kiểm soát.
- [ ] **Grouping theo `document_id` không làm loãng search.** Mỗi document trả tối đa `notes_per_source` part; đo xem có bỏ sót part chứa gold không.
- [ ] **Atomic create hoạt động.** Không để lại part mồ côi khi một part lỗi/413; retry idempotent.

### Might be true (nice to have)

- [ ] Người dùng muốn chỉnh ngưỡng chia trong Settings.
- [ ] Composite reader read-only là đủ; chỉnh toàn văn để sau.
- [ ] Cần một bảng `documents` khi số part tăng hoặc cần trạng thái aggregate.

## MVP Scope

**Trong phạm vi:**

- Backend: cột `document_id`/part metadata, `POST /notes` nhận `parts`, grouping `document_id ?? domain`, metadata trong search/RAG, migration + test.
- Extension: chia khi lưu note dài, modal chi phí, lưu một document, Thư viện gom một mục, reader read-only, tiến độ index.
- Evaluation: harness chia nguồn, map qid → document/part, AnswerHit toàn document, chạy lại và so sánh.

**Ngoài phạm vi:**

- Resource `/documents` riêng.
- Import PDF/Word/OCR.
- Sửa toàn văn một lần.
- Chia sẻ, phân quyền, cộng tác.
- Nâng trần server cho mọi user.
- Re-split tự động khi sửa một part.
- Thư mục riêng cho từng part.

## Not Doing (and Why)

- **Resource `/documents`** — thêm migration, trạng thái, quyền và endpoint; lệch mục tiêu “không tạo dạng đầu vào mới”. `document_id` trên note là đủ cho MVP.
- **Nâng trần toàn cục lên 200k** — rủi ro chi phí/abuse và làm note editor/sync phải chịu nội dung lớn; D1 đã bị loại.
- **Import PDF/Word/OCR** — là dạng đầu vào mới, không phải mở rộng note hiện có.
- **Sửa composite document** — phức tạp nhất; MVP chỉ đọc gộp và sửa từng part.
- **Mỗi part một thư mục** — dễ lệch metadata; folder thuộc document.
- **Tự động chia lại khi sửa part** — có thể làm thay đổi `part_count` và phá mapping eval; để sau.
- **Tăng `notes_per_source` vô hạn cho RAG** — tốn context; chỉ tune có đo lường.

## Acceptance Criteria

- [ ] Tài liệu 156.885 ký tự: `indexed_chars == total_chars`, `truncated = false`, `part_count` đúng, tất cả part `READY`.
- [ ] Thư viện hiện **một mục** cho tài liệu; mở ra thấy các phần; không trộn vào “Không rõ nguồn”.
- [ ] Search trả **một source** cho tài liệu; `max_sources` hoạt động trên corpus nhiều tài liệu; `sources_avg > 1`.
- [ ] Gold nằm ngoài 20k vẫn tìm thấy; AnswerHit kiểm tra toàn bộ part.
- [ ] RAG trích dẫn đúng part và hiển thị tên tài liệu.
- [ ] Note ≤20k: hành vi/API không đổi; toàn bộ test cũ pass; client cũ chạy được.
- [ ] Ước lượng chi phí sai số ≤20%; không vượt quota; 157k được đo thực tế.
- [ ] Xoá/di chuyển/reindex document hoạt động nhất quán từ góc nhìn người dùng.

## Open Questions

- Ngưỡng chia mặc định là 20k hay thấp hơn (8k–12k) để retrieval tốt hơn?
- Có cần overlap giữa các part không, và bao nhiêu?
- Part có nên bị ẩn khỏi danh sách note thường, hay hiện dưới group?
- Citation nên ở cấp document hay cấp part?
- Có cần bảng `documents` để quản lý trạng thái/title/xoá atomic không, hay metadata trên part là đủ?
- `rag_notes_per_source` nên là bao nhiêu cho document nhiều part?
- Giới hạn tổng tài liệu là bao nhiêu (200k? 1M?) và trả lỗi thế nào?
- `document_id` do client sinh hay server sinh? Client sinh giúp idempotency; server sinh giúp tránh trùng.
- Khi một part lỗi giữa chừng, retry toàn document hay chỉ part lỗi?

## Implementation Notes

**Backend**

- `apps/api/src/quickassist/data/models/note.py` — thêm cột/index.
- `apps/api/migrations/versions/` — migration mới.
- `apps/api/src/quickassist/presentation/schemas/notes.py` — `parts`, metadata.
- `apps/api/src/quickassist/business/notes/notes_service.py` — validate/tạo atomic, propagate metadata.
- `apps/api/src/quickassist/business/semantic_search/grouping.py` — group key.
- `apps/api/src/quickassist/presentation/schemas/search.py` — field mới.
- `apps/api/src/quickassist/business/rag/rag_service.py`, `prompts.py` — label/part.

**Extension**

- `apps/extension/src/ui/features/notes/NoteEditor.tsx` — phát hiện/chia/modal.
- `apps/extension/src/ui/features/notes/groupNotes.ts` — group key.
- `apps/extension/src/ui/features/notes/NotesView.tsx`, `NoteReader.tsx` — một mục, đọc gộp.
- `apps/extension/src/shared/api/types.ts`, `schema.d.ts` — contract.
- `apps/extension/src/shared/config.ts` — ngưỡng chia.

**Evaluation**

- `steady_evaluation/steady_flows.py` — bỏ truncation, chia + `document_id`.
- `steady_evaluation/steady_backend.py` — create parts, list by document.
- `steady_evaluation/steady_metrics.py` — AnswerHit toàn document, source metric.
- `steady_evaluation/dataset/qa_pairs.csv` — map qid → document/part nếu cần.

## Rủi ro chính và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Search trả nhiều part cùng tài liệu, loãng kết quả | Group theo document; tune `notes_per_source`; đo trên corpus nhiều tài liệu |
| Part mồ côi khi tạo lỗi giữa chừng | Tạo atomic trong một transaction + idempotency key cho cả document |
| Ranh giới part cắt mất ngữ cảnh | Chia theo đoạn/câu; test gold sát ranh giới; thêm overlap nếu cần |
| Chi phí vượt quota | Ước lượng trước, xác nhận, chặn khi thiếu quota; đo 157k thực tế |
| UI rối vì nhiều part | Một group card, label “Phần i/n”, reader gộp read-only |
| Metadata lệch giữa các part | Service propagate title/folder/url; test xoá/move/reindex |
