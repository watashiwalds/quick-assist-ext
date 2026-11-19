# Báo cáo giải trình — Đánh giá QuickAssist bằng `steady_evaluation`

**Run chính thức:** `20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local`

**Thời gian:** 2026-11-19 11:57:29 → 12:18:10 (GMT+7), khoảng **20 phút 41 giây**

**Model:** BYOK local

- Chat: `Ternary-Bonsai-2-9B PQ2_0 MTP Q8_0`, alias `chat`, ctx 12.288, 99 layer trên GPU
- Embedding: `gte-Qwen2-1.5B-instruct Q4_K_M`, alias `embed`, CPU, ctx 3.072

**Backend:** FastAPI + worker + PostgreSQL/pgvector tại `http://localhost:8000/api/v1`; `health/live` và `health/ready` đều `ok`.

**Dataset:** 11 nguồn (8 HTML + 3 TXT), 49 cặp hỏi–đáp (38 answerable, 11 unanswerable), **0 dòng bị loại**, fingerprint `ef7c82ca643482ab`.

---

## 0. Kết luận điều hành

1. Pipeline chạy hết 3 module với **0 lỗi case**: ingest 11/11 `READY`, search 38/38, RAG 49/49, PageMatch 49/49.
2. Phát hiện và sửa **một bug của harness**: `Idempotency-Key` dài 112 ký tự, vượt giới hạn 100 của backend, khiến lần chạy đầu nhận `422` cho cả 11 note. Sau khi sửa: 50/50 test offline pass, `--recompute` khớp hoàn toàn.
3. Chất lượng có **hai vùng rất khác nhau**:
   - **8 nguồn HTML (22 câu):** search đạt Recall@5 **22/22**, RAG trích dẫn **17/22**.
   - **3 nguồn TXT dài (16 câu):** search chỉ **5/16** vào top-5, RAG chỉ **3/16** có trích dẫn. Nguyên nhân chính là giới hạn **20.000 ký tự** của backend buộc harness phải cắt nội dung trước khi tạo note (chỉ giữ 12,7–50,5% tài liệu), không phải model yếu.
4. RAG **từ chối đúng 11/11** câu không có căn cứ, **0 số ngoài ngữ cảnh**; nhưng **47,4%** câu answerable không có trích dẫn.
5. PageMatch tìm được block đúng khá tốt (hit 82,4% ở chế độ segments) nhưng **precision thấp** (23,1%) và **FPR cao** (66,7% segments, 100% full-page). Cần đọc FPR theo đúng ngữ nghĩa: API luôn trả block ứng viên, nên FPR ở đây đo "có trả block hay không", không phải "có khẳng định câu trả lời hay không".

---

## 1. Mục tiêu và phạm vi

Mục tiêu của đợt chạy là kiểm chứng pipeline đánh giá trên **hệ thống thật** (HTTP + PostgreSQL/pgvector + worker + model local), không dùng mock:

- Nạp toàn bộ dataset thành note và chờ index xong.
- Đo search: Recall@5, MRR, AnswerHit và latency.
- Đo RAG: chất lượng trả lời, trích dẫn, từ chối, số ngoài ngữ cảnh, token và latency.
- Đo PageMatch: chất lượng block, fallback, FPR và latency.
- Ghi artifact tái lập được (`manifest`, `raw_results.jsonl`, `metrics.json`, `report.md`).

Ngoài phạm vi: tóm tắt, fault-injection, prompt injection, ablation full-text/vector/hybrid, nhãn nhiều người, rubric entailment.

---

## 2. Cấu hình chạy

| Thành phần | Giá trị |
|---|---|
| Lệnh | `run_evaluation.py --model-label local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4 --provider openai --model chat --embedding-model embed --tag full-local --fresh-notes --cleanup-notes` |
| Modules | `search, rag, pagematch` |
| `top_k` (note) | 5 |
| `max_sources` | 5 |
| `pagematch_top_k` | 5 |
| Folder mode | `run` — thư mục riêng cho run |
| Idempotency | `--fresh-notes` — note mới cho mỗi run |
| Cleanup | `--cleanup-notes` — đã xoá 11 note + folder sau khi chấm |
| Evidence type | `quality` |
| Git commit | `b656d2388` |
| Eval-code SHA-256 | `59ae54a50…` |

**Giới hạn rate limit gặp trong run:** search 30/phút, AI 10/phút, page-match 6/phút. Harness đã gặp **31 lần `429`**, tổng thời gian chờ tường minh khoảng **199 giây**; vì vậy thời gian tường (20 phút 41 giây) dài hơn nhiều so với tổng latency từng request.

---

## 3. Kết quả tổng hợp

| Module | Chỉ số chính | Kết quả |
|---|---|---|
| Ingest | READY / tạo mới / lỗi | **11/11 · 11 · 0** |
| Ingest | create p50 · chờ index p50 / p95 | **22,38 ms · 3.015,5 ms / 7.037,1 ms** |
| Search | Recall@5 · MRR · AnswerHit | **0,7105 · 0,6798 · 0,6842** |
| Search | p50 / p95 · nguồn TB · note TB | **187,4 / 285,5 ms · 1,0 · 4,37** |
| RAG (answerable) | hoàn thành · lỗi | **38/38 · 0** |
| RAG (answerable) | trích dẫn hợp lệ · không trích dẫn | **0,5263 · 0,4737** |
| RAG (answerable) | total p50 / p95 · token TB | **2.902,9 / 9.310,9 ms · 1.035,2** |
| RAG (unanswerable) | từ chối đúng · trả lời bừa | **11/11 = 1,0 · 0,0** |
| PageMatch (segments) | hit · precision@5 · span coverage | **0,8235 · 0,2314 · 0,8468** |
| PageMatch (segments) | FPR âm tính | **0,6667 (4/6)** |
| PageMatch (full-page) | hit · full-page F1 · FPR | **0,5 · 0,8156 · 1,0 (4/4)** |
| PageMatch | p50 / p95 · lỗi | **15.082,0 / 32.847,8 ms · 0** |
| Quota | đã dùng / còn lại | **491.542 / 477.294 token** (tổng 1.000.000) |

---

## 4. Phân tích chi tiết

### 4.1 Ingest

- 11/11 file `READY`, không file nào `FAILED`/`TIMEOUT`, không replay idempotent.
- Tạo note rất nhanh (p50 **22,38 ms**); thời gian chờ index chiếm phần lớn (p50 **3,0 s**, p95 **7,0 s**) và phản ánh worker thật.
- **3 file TXT bị harness cắt còn 20.000 ký tự trước khi gửi** — `POST /notes` từ chối nội dung vượt `MAX_NOTE_CHARS` bằng `413 NOTE_TOO_LONG`, nên harness cắt trước để note vẫn được tạo:

| File | Độ dài gốc | Giữ lại | Tỷ lệ |
|---|---:|---:|---:|
| `Attention Is All You Need.txt` | 39.587 | 20.000 | 50,5% |
| `LORA LOW-RANK ADAPTATION.txt` | 82.877 | 20.000 | 24,1% |
| `Evaluating Quantized Large Language.txt` | 156.885 | 20.000 | **12,7%** |

Đây là nguyên nhân gốc của gần như toàn bộ lỗi search/RAG trên nhóm TXT (xem 4.2 và 4.3).

Lưu ý: đây là giới hạn của đường **lưu note** (20.000 ký tự, vượt thì `413 NOTE_TOO_LONG`), không phải giới hạn của “Tìm trong trang” — PageMatch chỉ **cảnh báo** khi nội dung dán vượt 50.000 ký tự và vẫn cho phép “Quét toàn bộ”. Hai luồng này độc lập; xem giải thích trong `BAO_CAO_NGUON_KHONG_CAT.md` §3.1.

### 4.2 Search — phát hiện chính

**Tổng:** 38 câu answerable, 38 hoàn thành, 0 lỗi; Recall@5 **0,7105** (27/38), MRR **0,6798**, AnswerHit **0,6842** (26/38); p50 187,4 ms, p95 285,5 ms; trung bình 1 nguồn và 4,37 note mỗi truy vấn.

Tách theo nguồn:

| Nguồn | Answerable | Hit@5 | AnswerHit |
|---|---:|---:|---:|
| Quyền lực Nvidia… (HTML) | 4 | **4/4** | 4/4 |
| Ông Lê Thanh Thản… (HTML) | 4 | **4/4** | 4/4 |
| Hà Nội sắp mở bán nhà xã hội… (HTML) | 3 | **3/3** | 3/3 |
| Messi rạn nứt… (HTML) | 3 | **3/3** | 3/3 |
| Tấm chắn Mặt Trời… (HTML) | 3 | **3/3** | 3/3 |
| Vận tải cơ chở 17 người… (HTML) | 3 | **3/3** | 3/3 |
| Mỹ tấn công đảo chiến lược… (HTML) | 1 | **1/1** | 1/1 |
| Mạng liên lạc tuyệt mật… (HTML) | 1 | **1/1** | 1/1 |
| **HTML cộng lại** | **22** | **22/22 = 100%** | **22/22** |
| Attention Is All You Need (TXT) | 7 | 3/7 | 3/7 |
| LORA LOW-RANK ADAPTATION (TXT) | 5 | 1/5 | 1/5 |
| Evaluating Quantized… (TXT) | 4 | 1/4 | 0/4 |
| **TXT cộng lại** | **16** | **5/16 = 31,25%** | **4/16** |

Hai kết luận quan trọng:

1. **Toàn bộ 11 ca trượt top-5 đều thuộc 3 file TXT bị cắt.** Trên HTML, search đạt 22/22. Vì vậy con số tổng 0,7105 đang bị kéo xuống bởi giới hạn ingest, không phải bởi chất lượng xếp hạng trên nội dung đã index.
2. Có trường hợp note được xếp **hạng 1 nhưng AnswerHit = false** (QA-047, file Quantized): search tìm đúng tài liệu, nhưng đoạn gold nằm ngoài 20.000 ký tự đã index nên `snippet` và toàn văn note đều không chứa gold.

**Hạn chế của phép đo nguồn:** `sources_avg = 1,0` cho cả 38 truy vấn. Nguyên nhân: harness tạo note **không kèm `url`**, nên backend gán `domain = null` và gom **toàn bộ 11 note vào một source duy nhất** nhãn `Không rõ nguồn` (kiểm tra raw: QA-001 và QA-032 đều trả 1 source/8 note). Hệ quả là `max_sources = 5` **không thực sự được kiểm chứng** trong corpus này; các chỉ số theo nguồn bị suy biến, chỉ số theo **note** mới có ý nghĩa. Muốn kiểm chứng `max_sources`, cần truyền URL/domain khi tạo note và có nhiều domain khác nhau.

**Sàn ngẫu nhiên:** `random_floor = 5/11 = 0,4545`. Với corpus chỉ 11 note và `top_k = 5`, cần đọc Recall@5 kèm sàn này; mức 0,71 cao hơn sàn nhưng chưa đủ để kết luận mạnh nếu chỉ nhìn con số tổng. Việc HTML đạt 22/22 cũng phản ánh phần nào hiệu ứng trần (mỗi tài liệu chỉ có 1 note).

### 4.3 RAG

**Answerable (38 câu):**

- 38/38 hoàn thành, **0 lỗi**.
- Token-F1 với gold: **0,1707** — chỉ là trùng từ bề mặt, không phải độ đúng ngữ nghĩa; nhiều câu trả lời diễn đạt lại nên F1 thấp là kỳ vọng.
- **Trích dẫn hợp lệ: 0,5263 (20/38)**; **không trích dẫn: 0,4737 (18/38)**.
- Số ngoài ngữ cảnh: **0**; không có nguồn: **0**; không có ngữ cảnh: **0**.
- Ngữ cảnh trung bình **17.355,8 ký tự**; token trung bình **1.035,2**.
- First-event p50 **265,0 ms**; total p50 **2.902,9 ms**, p95 **9.310,9 ms**.

Trích dẫn theo nhóm nguồn:

| Nhóm | Cited | Tổng | Tỷ lệ |
|---|---:|---:|---:|
| HTML | 17 | 22 | **77,3%** |
| TXT | 3 | 16 | **18,8%** |
| **Tổng** | **20** | **38** | **52,6%** |

Trong nhóm TXT, `LORA` và `Quantized` **không có câu nào trích dẫn** (0/5 và 0/4). Điều này khớp với việc phần lớn nội dung hai file không được index.

**Unanswerable (11 câu):**

- Từ chối đúng **11/11 = 1,0**; trả lời bừa **0,0**; không có nguồn **0,0**.
- Đây là tín hiệu tốt, nhưng mẫu nhỏ và phát hiện từ chối dựa trên marker ở câu đầu nên chưa đại diện cho mọi cách diễn đạt.

### 4.4 PageMatch

49 case, **0 lỗi**. Phân bố: 23 case `segments`, 26 case `full_page`; 2 case có warning `VERIFY_UNAVAILABLE` (QA-003, QA-047) được tách sang nhóm fallback, không gộp vào chất lượng.

**Segments (chất lượng chính):**

| Chỉ số | Giá trị |
|---|---:|
| Dương tính / âm tính | 17 / 6 |
| Hit · Exact | **0,8235 · 0,8235** |
| Precision@5 · Recall@5 · F1@5 | **0,2314 · 0,8235 · 0,3392** |
| Span Precision · Coverage · F1 | **0,1231 · 0,8468 · 0,2017** |
| FPR âm tính | **0,6667 (4/6)** |
| p50 | 14.917,8 ms |

**Full-page (báo riêng):**

| Chỉ số | Giá trị |
|---|---:|
| Dương tính / âm tính | 20 / 4 |
| Hit · Full-page F1 | **0,5 · 0,8156** |
| Precision@5 · Span Coverage | **0,1 · 0,5722** |
| FPR âm tính | **1,0 (4/4)** |

**Cách đọc FPR:** metric coi một ca âm tính là "dương tính giả" nếu tool trả **ít nhất một block trong top-5**, bất kể block đó có được xác minh là trả lời được hay không. PageMatch là API **retrieval**, luôn trả ứng viên tốt nhất, nên FPR cao phản ánh hành vi "không bao giờ rỗng" hơn là "khẳng định sai". Muốn đánh giá đúng hơn cần ngưỡng tin cậy/`verified` hoặc một quyết định "không tìm thấy".

Các tín hiệu khác:

- `full_page_mode_rate = 0,5306` — hơn nửa số case trả cả trang.
- `truncated_rate = 0,2245` (11/49): 6 case LORA + 5 case Quantized có `source_text` bị cắt ở 50.000 ký tự.
- 2 case segments trả **0 block** (QA-006, QA-026).
- p50 **15.082,0 ms**, p95 **32.847,8 ms** — chậm hơn nhiều so với search/RAG, một phần do prompt lớn và áp lực RAM.

---

## 5. Sự cố và cách khắc phục

### 5.1 Dataset CSV bị sai định dạng

Lần kiểm chứng đầu tiên, `dataset/qa_pairs.csv` bị padding cột bằng khoảng trắng và dấu `"` không nằm ở đầu field, nên CSV parser cắt sai. `--validate` báo:

```
qa_pairs: 0
Thiếu cột: ['answerable', 'gold_text', 'question', 'source_file']
Không còn cặp hỏi–đáp hợp lệ nào
```

Bạn đã định dạng lại file. Sau đó harness xác nhận:

```
source_files: 11 · qa_pairs: 49 · answerable: 38 · unanswerable: 11 · excluded_rows: 0
✓ Không có vấn đề kiểm chứng nào
```

### 5.2 Bug harness: `Idempotency-Key` vượt 100 ký tự

**Hiện tượng:** lần chạy đầu (`20261119_045531_300530_…_full-local`) nhận `422 VALIDATION_ERROR` cho **cả 11 file** ngay khi ingest. Không có note nào được tạo.

**Chẩn đoán:** gọi trực tiếp backend với key dài cho phản hồi:

```json
{"error":{"code":"VALIDATION_ERROR",
          "details":{"errors":[{"loc":["header","Idempotency-Key"],
                                "msg":"String should have at most 100 characters"}]}}}
```

Harness tạo key theo công thức:

```
"steady-" (7) + run_id (80) + "-" (1) + sha256(content)[:24] = 112 ký tự
```

`run_id` dài vì nhãn model dài (`local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4`). Smoke run trước đó dùng tag ngắn nên không lộ bug.

**Khắc phục:** trong `steady_flows.py`, nếu key vượt 100 ký tự thì băm `run_scope` thành 16 ký tự hex:

```
"steady-" (7) + sha256(scope)[:16] (16) + "-" (1) + digest (24) = 48 ký tự
```

Key vẫn **tất định trong cùng run** và **khác nhau giữa các run**, nên không phá cô lập corpus.

**Kiểm chứng:**

- Thêm 2 test hồi quy trong `tests/test_flows.py` (độ dài ≤ 100, tất định, khác scope/content).
- **50/50 test offline pass** (`python3 -m unittest discover -s tests -t .`).
- Chạy lại full: 11/11 note tạo mới thành công.
- `--recompute` trên run chính thức: **✓ khớp hoàn toàn**.

### 5.3 Run đầu thất bại

Artifact của run lỗi vẫn được giữ để đối chiếu tại:

```
runs/20261119_045531_300530_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local/
```

Trong `--compare`, run này xuất hiện với các cột metric để trống — đúng với trạng thái "fatal trước khi chấm".

### 5.4 Áp lực RAM và rate limit

- Tổng RAM 12 GB; lúc chạy đỉnh điểm dùng ~11 GB, swap ~2,5 GB.
- Nguyên nhân chính: model chat ~8,6 GB + model embedding ~1,9 GB (embedding được nạp lazy khoảng 4–5 phút sau khi run bắt đầu).
- 31 lần `429` với tổng chờ ~199 giây; một case search (QA-040) phải chờ 54,2 giây nên có latency **54.248,8 ms**, nằm ngoài p95 (p95 = 285,5 ms vì chỉ có 1 outlier).
- Vì vậy **latency của run này phản ánh máy đang chịu tải**, không phải benchmark sạch.

---

## 6. Hạn chế và cách đọc số liệu

1. **Cắt nội dung 20.000 ký tự** là hạn chế lớn nhất. Nó làm 3 file TXT chỉ còn 12,7–50,5% nội dung, khiến search/RAG/AnswerHit trên nhóm này không phản ánh năng lực model.
2. **Search nhóm theo domain**, nhưng note được tạo không kèm `url` nên mọi note có `domain = null` và bị gom vào một source `Không rõ nguồn`. Với corpus này `sources_avg = 1,0`, nên `max_sources` chưa được kiểm chứng; các chỉ số "nguồn" không có ý nghĩa thống kê.
3. **Sàn ngẫu nhiên 0,4545** với 11 note và top-5; Recall@5 tổng 0,71 chỉ cao hơn sàn ~0,26. Cần corpus lớn hơn để phân biệt chất lượng xếp hạng.
4. **Token-F1 0,17** chỉ đo trùng từ, không đo đúng nghĩa; không nên dùng làm kết luận chính.
5. **Trích dẫn** chỉ kiểm tra `[n]` nằm trong số nguồn và có ít nhất một trích dẫn, chưa kiểm chứng nguồn có thực sự hỗ trợ ý. Tỷ lệ 47,4% câu không trích dẫn là tín hiệu sản phẩm cần cải thiện, không phải lỗi metric.
6. **PageMatch FPR** đo "có trả block trong top-5" cho câu âm tính, không đo "khẳng định sai"; API luôn trả ứng viên nên FPR cao là kỳ vọng một phần.
7. **Phát hiện từ chối** dựa trên marker ở câu đầu; có thể bỏ lỡ cách diễn đạt khác.
8. **Chỉ chạy 1 lần**, không có khoảng tin cậy, không có reference answer, không chạy lặp để ổn định p50/p95.
9. **Latency end-to-end** gồm model local + áp lực RAM + chờ rate limit; chưa tách thời gian DB thuần.

---

## 7. Khuyến nghị

| Ưu tiên | Việc cần làm | Lý do |
|---|---|---|
| P0 | Chia nhỏ 3 file TXT thành nhiều note (chunking) hoặc nâng `MAX_NOTE_CHARS` cho eval | Gỡ bỏ nguyên nhân chính làm search/RAG nhóm TXT sai lệch |
| P0 | Truyền `url`/domain khi tạo note (hoặc gán domain riêng) và bổ sung nguồn khác domain | Để `max_sources` và metric theo nguồn thực sự có ý nghĩa |
| P1 | Cải thiện trích dẫn RAG (prompt "luôn trích nguồn", hoặc kiểm tra groundedness) | 47,4% câu answerable không có trích dẫn |
| P1 | Đánh giá PageMatch bằng ngưỡng `verified`/confidence thay vì "có block" | FPR hiện tại 66,7–100% nhưng chưa phản ánh quyết định "không tìm thấy" |
| P2 | Chạy lại trên máy thoáng (hoặc hạ ctx chat về 8192) để có latency sạch | Run hiện tại chịu áp lực RAM + 31 lần 429 |
| P2 | Thêm `reference_answer` cho các câu answerable | Có metric ngữ nghĩa phụ, không chỉ token-F1 |
| P3 | Chạy lặp 3 lần và báo p50/p95 liên run | Tăng độ tin cậy của latency |
| P3 | Commit các thay đổi harness + dataset đã định dạng | Tránh tái phát bug CSV/key ở lần sau |

---

## 8. Phụ lục

### 8.1 Artifact

```
steady_evaluation/runs/20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local/
├── run_manifest.json
├── raw_results.jsonl
├── metrics.json
├── metrics.recomputed.json
└── report.md
```

So sánh model: `steady_evaluation/runs/MODEL_COMPARISON.md`.

Log chạy đầy đủ: `/tmp/opencode/steady_full_run2.log`.

### 8.2 Tái lập

```bash
cd steady_evaluation
python3 run_evaluation.py --recompute 20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local
# → [recompute] ...: ✓ khớp hoàn toàn
```

### 8.3 Thay đổi mã nguồn của đợt này

| File | Thay đổi |
|---|---|
| `steady_flows.py` | Băm `run_scope` khi `Idempotency-Key` vượt 100 ký tự |
| `tests/test_flows.py` | Thêm 2 test hồi quy cho giới hạn 100 ký tự |
| `dataset/qa_pairs.csv` | Định dạng lại CSV (nội dung 49 dòng giữ nguyên) |
| `BAO_CAO_GIAI_TRINH.md` | Báo cáo này |

### 8.4 Trạng thái kiểm thử

```
Ran 50 tests in 0.378s
OK
```

---

*Báo cáo được tạo từ artifact của run `20261119_045729_886201`, đối chiếu trực tiếp `metrics.json`, `raw_results.jsonl` và log chạy. Các con số latency mang tính tham khảo trong điều kiện máy chịu tải.*
