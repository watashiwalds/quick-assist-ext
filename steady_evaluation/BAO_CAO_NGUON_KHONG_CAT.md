# Báo cáo phụ — Chỉ các nguồn không bị cắt nội dung

**Run gốc:** `20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local`
**Báo cáo chính:** [`BAO_CAO_GIAI_TRINH.md`](BAO_CAO_GIAI_TRINH.md)
**Dữ liệu tái tính:** `runs/20261119_045729_886201_.../analysis_by_truncation.json`

---

## 0. Kết luận ngắn

Khi loại 3 file TXT bị cắt còn 20.000 ký tự, bộ 8 nguồn HTML cho kết quả **rất khác** toàn bộ run:

| Chỉ số | Toàn bộ run (11 nguồn) | **Chỉ nguồn không cắt (8 HTML)** | Chỉ nguồn bị cắt (3 TXT) |
|---|---:|---:|---:|
| Search — số truy vấn | 38 | **22** | 16 |
| Search — Recall@5 | 0,7105 | **1,0000** | 0,3125 |
| Search — MRR | 0,6798 | **0,9697** | 0,2812 |
| Search — AnswerHit | 0,6842 | **1,0000** | 0,2500 |
| RAG — Token-F1 gold | 0,1707 | **0,2769** | 0,0247 |
| RAG — trích dẫn hợp lệ | 0,5263 | **0,7727** | 0,1875 |
| RAG — từ chối đúng (âm) | 1,0 (11/11) | **1,0 (9/9)** | 1,0 (2/2) |
| PageMatch segments — Hit | 0,8235 | **1,0000** | 0,5714 |
| PageMatch segments — Precision@5 | 0,2314 | **0,3083** | 0,1214 |
| PageMatch segments — Span coverage | 0,8468 | **1,0000** | 0,6280 |
| PageMatch full-page — Hit | 0,5000 | **0,5833** | 0,3750 |
| PageMatch full-page — Full-page F1 | 0,8156 | **0,8527** | 0,7601 |

**Diễn giải:** khoảng cách lớn giữa hai nhóm chủ yếu đến từ **mất nội dung ở bước tạo note**, không phải từ việc model “kém hơn” trên văn bản học thuật. Toàn bộ 11 ca search trượt top-5 của run gốc đều thuộc 3 file TXT bị cắt. Trên 8 nguồn không cắt, search đạt **22/22**, MRR **0,97**, AnswerHit **22/22**.

---

## 1. Phạm vi và phương pháp

### 1.1 Định nghĩa “không bị cắt”

Một nguồn được coi là **không bị cắt** khi case ingest có `truncated = false`, tức `content_chars` gửi lên bằng độ dài văn bản gốc. Trong run này:

- **8 file HTML**: tất cả `truncated = false`.
- **3 file TXT**: `truncated = true` vì vượt `MAX_NOTE_CHARS = 20.000`:

| File | Độ dài gốc | Đã index | Tỷ lệ |
|---|---:|---:|---:|
| `Attention Is All You Need.txt` | 39.587 | 20.000 | 50,5% |
| `LORA LOW-RANK ADAPTATION.txt` | 82.877 | 20.000 | 24,1% |
| `Evaluating Quantized Large Language.txt` | 156.885 | 20.000 | 12,7% |

### 1.2 Cách tạo báo cáo

Đây là **phân tích hậu kiểm trên raw của cùng run**, không phải lần chạy mới:

1. Đọc `raw_results.jsonl` + `run_manifest.json`.
2. Lấy tập file có `ingest.truncated = false` → 8 HTML.
3. Map `qid → source_file` từ `dataset/qa_pairs.csv`.
4. Lọc case của cả 4 module theo tập file đó.
5. Dựng lại `IngestCase` / `SearchCase` / `RagCase` / `PageMatchCase` và tái tính bằng đúng các hàm `aggregate_*` của harness.
6. Lưu kết quả vào `analysis_by_truncation.json`.

**Không gọi thêm API, không tiêu thêm token.** Vì vậy latency là lát cắt của run gốc (máy đang chịu tải + có 429), không phải benchmark sạch.

### 1.3 Điều quan trọng cần đọc đúng

Đây là **lọc theo nguồn của câu hỏi**, không phải chạy lại trên **corpus chỉ có HTML**:

- Search vẫn diễn ra trên **11 note** (8 HTML + 3 TXT giữ 20k đầu), nên TXT vẫn là đối thủ cạnh tranh trong top-5.
- `random_floor` vẫn là **5/11 = 0,4545**, không phải 5/8.
- Kết quả trả lời câu hỏi: “Nếu nguồn của câu hỏi không bị cắt thì chất lượng đo được là bao nhiêu?”, **không** trả lời “corpus HTML thuần thì sao?”. Muốn trả lời câu sau cần tạo dataset HTML-only và chạy lại (~20 phút, tốn quota).

---

## 2. Kết quả chi tiết — 8 nguồn không bị cắt

**Phạm vi:** 8 file HTML · 31 cặp hỏi–đáp (22 answerable, 9 unanswerable).

### 2.1 Ingest

| Chỉ số | Giá trị |
|---|---:|
| File READY | **8/8** |
| Tạo mới / replay / lỗi | 8 / 0 / 0 |
| Create p50 | **21,43 ms** |
| Chờ index p50 / p95 | **3.012,94 / 4.021,50 ms** |
| File bị cắt | **0** |

### 2.2 Search

| Chỉ số | Giá trị |
|---|---:|
| Truy vấn / hoàn thành / lỗi | 22 / 22 / 0 |
| **Recall@5** | **1,0000 (22/22)** |
| **MRR** | **0,9697** |
| **AnswerHit** | **1,0000 (22/22)** |
| Nguồn TB / note TB | 1,0 / 4,32 |
| Rỗng | 0,0 |
| p50 / p95 | **184,51 / 267,73 ms** |
| Sàn ngẫu nhiên (5/11) | 0,4545 |

Chi tiết đáng chú ý:

- 22/22 câu có gold nằm trong top-5; 21 câu ở **hạng 1**, 1 câu ở **hạng 3** (QA-016, bài “Tấm chắn Mặt Trời”).
- AnswerHit = 22/22, tức mọi note chứa gold đều thực sự chứa đoạn gold trong nội dung — không còn hiện tượng “rank 1 nhưng AnswerHit false” như QA-047 ở nhóm TXT.
- Tuy nhiên `sources_avg = 1,0` vì mọi note được tạo **không kèm `url`**, backend gán `domain = null` và gom tất cả vào một source `Không rõ nguồn`. `max_sources` vẫn chưa được kiểm chứng.

**Trích dẫn RAG theo từng nguồn HTML:**

| Nguồn | Cited / Answerable |
|---|---:|
| Quyền lực Nvidia… | 4/4 |
| Ông Lê Thanh Thản… | 2/4 |
| Hà Nội sắp mở bán nhà xã hội… | 3/3 |
| Messi rạn nứt… | 1/3 |
| Tấm chắn Mặt Trời… | 3/3 |
| Vận tải cơ chở 17 người… | 3/3 |
| Mỹ tấn công đảo chiến lược… | 1/1 |
| Mạng liên lạc tuyệt mật… | 0/1 |
| **Tổng** | **17/22 = 77,3%** |

### 2.3 RAG

**Answerable (22 câu):**

| Chỉ số | Giá trị |
|---|---:|
| Hoàn thành / lỗi | 22 / 0 |
| Token-F1 với gold (phụ) | **0,2769** |
| Trích dẫn hợp lệ / không trích dẫn | **0,7727 / 0,2273** |
| Số ngoài ngữ cảnh | **0** |
| Không nguồn / không ngữ cảnh | 0 / 0 |
| Ngữ cảnh TB | 15.673,9 ký tự |
| Token TB | 1.103,6 |
| First-event p50 | 243,61 ms |
| Total p50 / p95 | **3.011,90 / 9.310,93 ms** |

**Unanswerable (9 câu):**

| Chỉ số | Giá trị |
|---|---:|
| Hoàn thành / lỗi | 9 / 0 |
| Từ chối đúng | **1,0 (9/9)** |
| Trả lời bừa | **0,0** |
| Không nguồn | 0,0 |

So với toàn bộ run, F1 tăng từ **0,1707 → 0,2769** và tỷ lệ trích dẫn từ **52,6% → 77,3%**. Phần lớn khoảng cách còn lại nằm ở 5 câu không trích dẫn (Lê Thanh Thản 2, Messi 2, Mạng liên lạc 1) — đây là vấn đề hành vi trích dẫn, không phải mất nội dung.

### 2.4 PageMatch

31 case, **0 lỗi**; 1 case warning `VERIFY_UNAVAILABLE` (QA-003) được tách sang fallback.

**Segments (chất lượng chính):**

| Chỉ số | Giá trị |
|---|---:|
| Dương tính / âm tính | 10 / 6 |
| **Hit · Exact** | **1,0000 · 1,0000** |
| Precision@5 · Recall@5 · F1@5 | **0,3083 · 1,0000 · 0,4367** |
| Span Precision · **Coverage** · Span F1 | 0,1836 · **1,0000** · 0,3004 |
| FPR âm tính | **0,6667 (4/6)** |

**Full-page (báo riêng):**

| Chỉ số | Giá trị |
|---|---:|
| Dương tính / âm tính | 12 / 2 |
| **Hit · Full-page F1** | **0,5833 · 0,8527** |
| Precision@5 · Span Coverage | 0,1167 · 0,6491 |
| FPR âm tính | **1,0 (2/2)** |

**Fallback:** 1 case âm tính, `verified_fpr = 0,0`.

Tín hiệu khác:

- `full_page_mode_rate = 0,4839` (15/31).
- `truncated_rate = 0,0` — không case HTML nào bị cắt ở `PAGE_MATCH_MAX_CHARS = 50.000`.
- p50 **10.886,16 ms**, p95 **30.438,96 ms**.

**Cách đọc FPR:** vẫn như báo cáo chính — FPR đo “có trả ít nhất một block trong top-5 cho câu âm tính”, không đo “khẳng định sai”. API PageMatch luôn trả ứng viên, nên FPR 66,7% (segments) chưa phải lỗi chất lượng nghiêm trọng; cần ngưỡng `verified`/confidence để biến nó thành quyết định “không tìm thấy”.

---

## 3. Vì sao nội dung bị mất — phân tích backend

### 3.1 Chuỗi giới hạn hiện tại

1. **Harness cắt trước khi gửi.** `steady_flows.ingest_sources` cắt `content` còn `cfg.max_note_chars = 20.000` ký tự rồi mới `POST /notes`. Với 3 file TXT, phần đuôi **không bao giờ đến backend**.
2. **Backend cũng có trần cứng.** `NotesService._clean_text` kiểm tra `get_settings().max_note_chars` và trả `413 NOTE_TOO_LONG` nếu vượt (`apps/api/src/quickassist/business/notes/notes_service.py`). Cấu hình mặc định: `max_note_chars: int = 20_000` (`infrastructure/config.py`), `MAX_NOTE_CHARS=20000` trong `infra/.env`.
3. **Chunking chỉ chạy trên nội dung đã lưu.** Worker chia `note.content` thành chunk ~1.200 ký tự, overlap ~150 (`business/semantic_search/chunking.py`, `CHUNK_SIZE_CHARS=1200`). Vì `note.content` chỉ còn 20k, toàn bộ chunk cũng chỉ phủ 20k đầu.
4. **Search/RAG chỉ thấy chunk đã embed.** Đuôi tài liệu không có vector, không thể được xếp hạng hay đưa vào prompt.
5. **AnswerHit kiểm tra toàn văn note.** Với gold nằm ngoài 20k, `GET /notes/{id}` trả nội dung đã cắt → AnswerHit false dù search xếp note hạng 1. Đây chính là QA-047.
6. **PageMatch có trần riêng 50.000 ký tự.** `page_match_max_chars: int = 50_000` cắt `source_text` trước khi chia block; 11/49 case bị cắt (6 LORA + 5 Quantized). Với block 1.200 ký tự, phần đuôi cũng mất khỏi ứng viên.
7. **RAG có trần ngữ cảnh prompt 18.000 ký tự.** `chat_context_max_chars: int = 18_000` là một dạng “mất nội dung” khác — không phải mất khỏi index, mà mất khỏi prompt khi có quá nhiều chunk. Cần tách biệt khi chẩn đoán.

> **Vì sao “Tìm trong trang” chỉ cảnh báo mà file TXT vẫn bị cắt?**
>
> Hai luồng khác nhau, hai giới hạn khác nhau:
> - **“Tìm trong trang” là quét tạm** (PageMatch, stateless). Với nội dung dán vượt 50.000 ký tự, UI chỉ **cảnh báo chi phí** rồi cho chọn “Quét 50k đầu” hoặc “Quét toàn bộ”; chọn toàn bộ thì backend bỏ trần (`scan_all=true` → `max_chars=None`). Kết quả chỉ lưu các đoạn khớp đã chọn thành note, không lưu cả tài liệu.
> - **File `.txt` của bộ eval không đi qua “Tìm trong trang”** (extension không có chức năng import `.txt`). Harness tạo **note lưu trữ** qua `POST /notes`; đường này có trần cứng 20.000 ký tự, vượt thì trả `413 NOTE_TOO_LONG` và không có tùy chọn “quét toàn bộ”. Note editor trong extension cũng chặn lưu khi vượt 20.000 ký tự.
>
> Vì vậy “cảnh báo 50k” và “cắt 20k” không mâu thuẫn: cảnh báo thuộc luồng quét, còn cắt thuộc luồng lưu note — và chính harness thực hiện cắt trước để tránh `413`.

### 3.2 Vì sao các giới hạn này tồn tại

| Lý do | Giải thích |
|---|---|
| **UX của extension** | Sản phẩm chính là “bôi đen đoạn văn → lưu note”; 20k ký tự đã rộng hơn nhu cầu chọn đoạn thông thường. |
| **Chi phí embedding** | 154k ký tự ≈ 77 chunk so với 17 chunk của 20k; chi phí embedding và số vector tăng ~4,5 lần cho một tài liệu. |
| **Quota/token** | Mỗi chunk là một lượt embed; quota mặc định 1.000.000 token dùng chung cho chat + embed. |
| **Latency & RAM worker** | Batch embed lớn, giữ nhiều chunk trong RAM; worker hiện chạy tuần tự để tránh OOM. |
| **Kích thước DB** | `note.content` + `note_chunk` + vector; tài liệu 150k ký tự làm phình bảng nhanh nếu nhân với nhiều user. |
| **Chống lạm dụng** | Trần payload ngăn request quá lớn và bảo vệ API/worker. |

**Điểm mấu chốt:** giới hạn 20k là hợp lý cho **capture selection**, nhưng dataset đánh giá đang dùng nó cho **document import** (bài báo khoa học, tài liệu dài). Đây là lệch mục đích sử dụng, không phải lỗi chunking.

---

## 4. Phương hướng giải quyết trên backend

### 4.1 Ưu tiên 1 — Tách “document import” khỏi “selection note”

Thêm luồng nhập tài liệu dài, không thay đổi hành vi extension. Contract dưới đây là **đề xuất** (chưa có trong API hiện tại):

```
POST /api/v1/documents            (async)
{ "title": "...", "url": "...", "content": "<toàn văn>", "source_type": "import" }
→ 202 { "document_id": "...", "job_id": "...", "total_chars": 156885 }

GET /api/v1/documents/{document_id}
→ { "status": "INDEXING|READY|FAILED",
    "total_chars": 156885,
    "indexed_chars": 156885,
    "chunk_count": 131,
    "note_ids": [...] }
```

- Lưu toàn văn (DB hoặc object storage), worker chunk + embed theo lô, cập nhật tiến độ.
- `POST /notes` giữ nguyên trần 20k cho capture selection.
- Chunk vẫn 1.200 ký tự; điểm khác là chạy trên **toàn bộ** tài liệu, không chỉ 20k đầu.
- Có thể trả `note_ids` để search/RAG dùng lại contract hiện tại.

**Ưu điểm:** đúng mục đích, không phá vỡ extension; **nhược điểm:** thêm endpoint, job, trạng thái, migration.

### 4.2 Ưu tiên 1 — Chunked note + `document_id`, group theo document

Nếu chưa muốn thêm resource mới, mở rộng note. Các field dưới đây là **đề xuất**:

```
NoteOut += {
  "document_id": "...",       // null với note capture thường
  "chunk_index": 0,
  "total_chunks": 8,
  "original_chars": 156885,
  "indexed_chars": 20000,
  "truncated": true
}
```

- Client/harness chia tài liệu thành nhiều note ≤20k tại ranh giới đoạn/section.
- Search group theo `document_id` (fallback `domain`) thay vì chỉ domain; `max_sources` giới hạn **document**, mỗi document có nhiều note/chunk.
- Sửa luôn vấn đề `sources_avg = 1,0`: note không có URL vẫn có `document_id`.

**Ưu điểm:** tận dụng hạ tầng note/chunk hiện có; **nhược điểm:** cần quy ước chia, xử lý overlap, và UI phải gộp note theo document.

### 4.3 Ưu tiên 2 — Nâng trần có kiểm soát

- Tăng `max_note_chars` lên 100.000–200.000 cho **user/workspace được phép**, giữ 20k mặc định.
- Ước lượng token/chi phí trước khi nhận; trả `413` kèm `max_chars` và gợi ý chia nhỏ.
- Có thể thêm `source_type` (`selection` | `import`) để áp trần khác nhau.

**Ưu điểm:** nhanh, ít thay đổi schema; **nhược điểm:** vẫn là trần hữu hạn, tăng chi phí/latency/DB, không giải quyết tài liệu rất dài.

### 4.4 Ưu tiên 2 — Không im lặng khi mất nội dung

Dù chọn giải pháp nào, backend nên trả metadata mất mát:

- `NoteOut.truncated`, `original_chars`, `indexed_chars`, `content_hash`.
- `SearchOut`/`RagOut` có thể cảnh báo nếu note nguồn bị cắt.
- `GET /notes/{id}` trả `truncated=true` để client biết không nên coi là toàn văn.
- PageMatch trả `truncated`, `coverage_chars`, và **offset cửa sổ tiếp theo**.

Điều này biến “mất nội dung âm thầm” thành “mất nội dung có thể phát hiện và xử lý”.

### 4.5 Ưu tiên 3 — PageMatch theo cửa sổ

- Thêm `offset`/`window_chars` vào `POST /ai/page-match`, hoặc tự động trả nhiều cửa sổ.
- Trả `coverage` và `next_offset`; client có thể gọi tiếp phần đuôi.
- Với tài liệu dài, chạy song song theo cửa sổ nhưng giới hạn concurrency để không tăng RAM.

### 4.6 Ưu tiên 3 — RAG không bỏ đuôi

- Chọn chunk theo điểm và **độ phủ tài liệu**, không chỉ top-N.
- Với tài liệu dài, dùng map-reduce: tóm tắt từng cụm chunk rồi tổng hợp.
- Ghi rõ `context_chars`, `context_note_count`, `coverage` trong response để người dùng biết prompt đã bị giới hạn.

### 4.7 Bảng đánh đổi

| Giải pháp | Chi phí triển khai | Tác động chất lượng | Rủi ro |
|---|---|---|---|
| Document import async | Trung bình–cao | **Cao** (index 100%) | Thêm job/trạng thái, cần migration |
| Chunked note + document_id | Trung bình | **Cao** | Chia chunk, gộp UI, ranking |
| Nâng trần 100k–200k | Thấp | Trung bình | Chi phí/latency/DB |
| Metadata truncated | **Thấp** | Không tăng recall, tăng minh bạch | Không |
| PageMatch cửa sổ | Trung bình | Cao cho tài liệu dài | Nhiều request, cần concurrency |
| RAG map-reduce | Cao | Cao | Phức tạp, token tăng |

### 4.8 Tiêu chí nghiệm thu

1. Với tài liệu 156.885 ký tự: `indexed_chars == total_chars == 156.885`, `truncated = false`.
2. **Gold coverage = 1,0**: mọi đoạn `gold_text` trong dataset phải nằm trong ít nhất một chunk đã embed. Kiểm tra tự động trước khi chấm.
3. Search trên 3 file TXT đạt Recall@5 tương đương HTML (hiện 0,3125 so với 1,0), và không còn `gold_rank = null` vì thiếu đuôi.
4. AnswerHit chỉ false khi gold thực sự không có trong nguồn — không false vì cắt nội dung.
5. PageMatch: `truncated_rate = 0` với tài liệu dưới trần mới; có `coverage`/`next_offset` cho tài liệu dài.
6. Chi phí: ghi rõ delta token/embedding cho một tài liệu 150k ký tự; không vượt quota mặc định nếu không có cảnh báo.

### 4.9 Giải pháp tạm thời cho harness (nếu chưa sửa backend)

- Thêm `--split-long-sources N`: chia văn bản nguồn thành nhiều file/note ≤N ký tự tại ranh giới đoạn.
- Map mỗi `qid` tới **note chứa gold** (không phải note đầu tiên của file).
- Nhờ vậy có thể đo lại search/RAG trên nội dung đầy đủ mà không cần đổi backend.
- Đây là giải pháp **đánh giá**, không thay thế giải pháp sản phẩm.

---

## 5. Hạn chế của báo cáo phụ

1. **Hậu kiểm, không phải run mới.** Cùng raw, cùng thời điểm, cùng áp lực RAM; không có khoảng tin cậy.
2. **Corpus vẫn gồm 11 note**, không phải 8; TXT vẫn cạnh tranh trong top-5. `random_floor` vẫn 5/11.
3. **Khác biệt thể loại.** HTML là bài báo ngắn, TXT là bài báo khoa học dài; một phần khoảng cách đến từ độ khó/ngôn ngữ, không chỉ từ cắt nội dung.
4. **HTML không đại diện cho mọi tài liệu ngắn.** 22/22 có thể là hiệu ứng trần với corpus nhỏ (11 note, top-5).
5. **PageMatch FPR** vẫn là “có trả block”, không phải “khẳng định sai”.
6. **Không có reference answer**, nên F1 chỉ là trùng từ bề mặt.

---

## 6. Phụ lục

### 6.1 Tái tạo phân tích

Dữ liệu đã lưu:

```
runs/20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local/
└── analysis_by_truncation.json
```

Phương pháp: lọc `ingest.truncated = false` → map `qid → source_file` từ `dataset/qa_pairs.csv` → dựng lại case bằng `case_from_dict` → `aggregate_ingest/search/rag/pagematch`.

### 6.2 Liên kết

- Báo cáo chính: [`BAO_CAO_GIAI_TRINH.md`](BAO_CAO_GIAI_TRINH.md)
- Artifact run: `runs/20261119_045729_886201_.../`
- So sánh model: `runs/MODEL_COMPARISON.md`

---

*Báo cáo phụ được tái tính từ raw của run gốc; không phát sinh lời gọi API hay token mới.*
