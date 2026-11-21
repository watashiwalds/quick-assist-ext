# Kế hoạch triển khai đánh giá các chức năng AI — QuickAssist

**Đầu vào bắt buộc:** `steady_evaluation(1).zip` do nhóm cung cấp.  
**Mục tiêu:** tạo bằng chứng có thể kiểm tra lại cho các chức năng AI của QuickAssist: tìm kiếm lai, PageMatch, hỏi đáp RAG và tóm tắt.  
**Nguyên tắc:** không sửa mã nguồn QuickAssist gốc, không bịa dữ liệu/nhãn/kết quả, không dùng API key thật trong tệp hoặc artifact.

---

## 1. Hiện trạng đã đối soát từ bộ dataset

| Hạng mục | Bằng chứng | Trạng thái | Cách dùng trong kế hoạch |
|---|---|---|---|
| Harness HTTP độc lập | `README.md`, `steady_backend.py`, `run_evaluation.py` | Có | Gọi backend thật qua HTTP; không import trực tiếp service của QuickAssist. |
| Corpus nguồn | `dataset/sources/` | Có 11 nguồn: 8 HTML, 3 TXT | HTML đi vào luồng PageMatch HTML; TXT đi vào luồng văn bản dán. |
| Bộ câu hỏi | `dataset/qa_pairs.csv` | Có 49 dòng: 38 `yes`, 11 `no` | `yes` dùng cho retrieval/PageMatch/RAG; `no` dùng cho từ chối RAG và false-positive PageMatch. |
| Gold evidence | cột `gold_text` | Có | Chỉ dùng khi loader `--validate` xác nhận đoạn gold còn tồn tại trong nguồn. |
| Đáp án tham chiếu hoàn chỉnh | cột `reference_answer` | Chưa có | Không được công bố F1/chính xác RAG dựa trên “đáp án đúng” trước khi người chấm tạo nhãn. |
| Luồng Summary trong harness | `steady_flows.py` | Chưa có | Cần add-on độc lập ở workspace đánh giá; tuyệt đối không sửa code app gốc. |
| Kết quả đo thật | `runs/` | Chưa có trong archive | Chỉ xuất hiện sau khi chạy backend + worker thật. |

**Lưu ý trung thực:** số dòng CSV không tự động là số case hợp lệ. Chỉ lấy `included_pairs`, `excluded_rows` trong `run_manifest.json` của lần chạy `--validate` làm mẫu số chính thức.

---

## 2. Ranh giới tác động bắt buộc

### 2.1. Cấu trúc thư mục được phép tạo

Đặt cạnh repository QuickAssist, **không đặt bên trong** repository:

```text
<parent-workspace>/
├── quick-assist-ext/                  # CODEBASE GỐC: chỉ đọc
└── quickassist_ai_evidence/           # DUY NHẤT được ghi bởi kế hoạch này
    ├── input/steady_evaluation/       # bản sao giải nén từ ZIP, giữ nguyên ban đầu
    ├── harness/                       # bản sao làm việc; mọi sửa script chỉ ở đây
    ├── configs/                       # .env đánh giá, KHÔNG commit key
    ├── dataset_derived/               # bản sao QA + metadata + nhãn người chấm
    ├── scripts/                       # script đo/kiểm chứng độc lập
    ├── runs/                          # raw JSONL, metrics, manifest theo từng run
    ├── review/                        # nhãn/rubric/phiếu đối soát của người chấm
    ├── evidence/                      # log đã lọc secret, ảnh/screenshot nếu có
    └── reports/                       # bảng đưa vào Final Report, chỉ sinh từ runs/
```

### 2.2. Quy tắc không được vi phạm

1. Không sửa, format, chạy migration, đổi schema, seed, hoặc commit bất kỳ tệp nào trong `quick-assist-ext/`.
2. Không sửa bộ dataset gốc trong `input/`; mọi thêm nhãn/đáp án ở `dataset_derived/`.
3. Không ghi API key vào `.md`, CSV, JSONL, report, screenshot hoặc Git. File cấu hình secret chỉ nằm ở `configs/.env.local`, có trong `.gitignore`.
4. Không tự sinh `gold_text`, `reference_answer`, nhãn đúng/sai hoặc số liệu bằng LLM.
5. Không ghi kết quả vào Final Report trước khi có `run_manifest.json`, `raw_results.jsonl`, `metrics.json` và phiếu review tương ứng.

### 2.3. Ngoại lệ duy nhất với codebase gốc

Chỉ khi không có cổng API/worker sẵn để đọc kết quả thực tế:

1. Kiểm tra trước: `GET <API_BASE_URL>/health/live` và `GET <API_BASE_URL>/health/ready`.
2. Nếu không có cổng, được chạy backend và worker từ codebase gốc bằng cấu hình runtime cục bộ; ưu tiên biến môi trường hoặc `.env` bị ignore.
3. Nếu thật sự phải bổ sung một cổng đọc output chưa tồn tại, lập tệp `review/EXCEPTION_REQUEST.md` trước, nêu: mục đích, tệp dự kiến tác động, output cần lấy, lý do không có API sẵn và cách hoàn nguyên. Chỉ làm sau khi nhóm phê duyệt.
4. Không được sửa thuật toán AI, prompt, schema, API contract hoặc test app gốc dưới danh nghĩa đánh giá.

---

## 3. Pha 0 — Chuẩn bị workspace và kiểm chứng đầu vào

### 3.1. Việc Antigravity phải thực hiện

1. Giải nén ZIP vào `input/steady_evaluation/`; sao chép sang `harness/` để chạy và chỉnh evaluator.
2. Ghi checksum SHA-256 của: file ZIP, toàn bộ file `dataset/sources/`, `qa_pairs.csv`, và các script trong `harness/` vào `evidence/input_inventory.sha256`.
3. Lưu `git rev-parse HEAD` của QuickAssist nếu repository có Git; nếu không có, ghi SHA-256 của các tệp backend/extension liên quan vào `evidence/code_snapshot.sha256`.
4. Chạy, không sửa dữ liệu trước:

```bash
cd quickassist_ai_evidence/harness
python run_evaluation.py --validate
python -m unittest discover -s tests -t .
```

5. Lưu stdout/stderr đã lọc token vào `evidence/validate.log` và `evidence/harness_tests.log`.
6. Nếu `--validate` có issue: dừng đánh giá chất lượng; lập `review/DATASET_ISSUES.md` ghi từng `qid`, lý do, nguồn và hành động đề xuất. Không dùng `--allow-partial` để che lỗi khi chạy chính thức.

### 3.2. Điều kiện qua pha

- Dataset validation không còn issue, hoặc các dòng loại được ghi rõ và không được đưa vào mẫu số.
- Toàn bộ test harness pass.
- Có inventory checksum và phiên bản code để tái lập.

---

## 4. Pha 1 — Chuẩn bị backend thật, provider và an toàn RPM

### 4.1. Runbook đã có thể chạy thật trên máy nhóm

Theo cấu hình Antigravity đã kiểm tra, `apps/api/.env` đã có Gemini API key hoạt động.
Harness **không cần và không được sao chép key**; nó chỉ gọi backend qua HTTP tại cổng 8000.

Mở **ba terminal riêng**, từ thư mục gốc `quick-assist-ext` của nhóm.

**Terminal 1 — API:**

```powershell
cd apps\api
uvicorn quickassist.main:app --port 8000
```

Giữ cửa sổ này mở. Chỉ sang bước tiếp theo khi có log Uvicorn nhận tại `http://127.0.0.1:8000`.

**Terminal 2 — worker (bắt buộc):**

```powershell
cd apps\api
python -m quickassist.worker
```

Worker xử lý job tạo embedding/index. Không có worker, note sẽ kẹt `PROCESSING`, nên
Search/RAG không tạo được số liệu chất lượng đáng tin.

**Terminal 3 — harness RPM-safe:**

```powershell
cd steady_evaluation_rpm_safe\steady_evaluation

# Xác nhận đang dùng ĐÚNG bản có pacing; nếu không thấy provider-rpm thì dừng.
python run_evaluation.py --help | Select-String "provider-rpm"

# Kiểm chứng dataset trước khi tốn quota Gemini.
python run_evaluation.py --validate
```

Chỉ khi hai kiểm tra trên thành công mới chạy đo thật. Lệnh run baseline:

```powershell
python run_evaluation.py `
  --model-label "gemma4-31b+gemini-emb" `
  --provider "gemini" `
  --model "<DUNG_TEN_CHAT_MODEL_TRONG_apps/api/.env>" `
  --embedding-model "<DUNG_TEN_EMBEDDING_MODEL_TRONG_apps/api/.env>" `
  --provider-rpm 10 `
  --folder-mode run `
  --fresh-notes `
  --cleanup-notes `
  --tag "gemini-baseline" `
  --evidence-type quality
```

`--folder-mode run` cô lập corpus theo từng run; `--fresh-notes` buộc tạo dữ liệu mới cho
lần đo; `--cleanup-notes` chỉ dọn note/thư mục trên CSDL **sau khi** artifact đã được lưu.
Kết quả trên ổ đĩa không bị xóa.

Ngay sau lệnh baseline, kiểm tra từ **Terminal 3**:

```powershell
# Thay <run_id> bằng thư mục vừa được in ra ở cuối lệnh trước.
Get-Content runs\<run_id>\metrics.json
Get-Content runs\<run_id>\report.md
python run_evaluation.py --recompute <run_id>
```

Nếu backend dùng tên model khác, chỉ thay các giá trị nhãn/metadata sau `--model` và
`--embedding-model`; không tự đổi model trong lúc cùng một run.

`GEMINI_API_KEY` chỉ nằm trong `apps/api/.env` hoặc environment của backend, không in/log/đưa vào harness.

### 4.2. Chống vượt RPM

1. Không chạy song song hai lệnh evaluator cho cùng tài khoản/provider.
2. Dùng runner đã có retry `429`; bổ sung pacing chủ động **trong bản sao `harness/`**, không sửa `quick-assist-ext/`.
3. Với máy hiện tại, Antigravity đề xuất `--provider-rpm 10`. Đây là **nhịp chạy của harness**, không phải tuyên bố quota chính thức Gemini. Nếu gặp `429`, hạ xuống 5, giữ lại artifact lỗi và chạy một run mới.
4. Lưu các tham số RPM, retry, timeout, model, embedding và command vào `run_manifest.json`.
5. Nếu có `429`: giữ artifact run, ghi `request_id`/`Retry-After` đã lọc secret, giảm RPM rồi chạy một run mới; không gộp hai run.

### 4.3. Quy tắc so sánh nhiều model

- **So sánh RAG generator:** cố định corpus, note/chunk, embedding, top-k, prompt, quota và dataset; chỉ đổi chat model.
- **So sánh end-to-end:** nếu đổi cả chat + embedding, đặt nhãn là “so sánh cấu hình end-to-end”, không kết luận chênh lệch do riêng LLM.
- Mỗi cấu hình tối thiểu chạy cùng dataset và cùng command (trừ model label), lưu run độc lập, không chọn lọc bỏ run lỗi.

---

## 5. Pha 2 — Kế hoạch đo cho từng chức năng AI

### 5.1. Cổng chung: Ingest và đánh chỉ mục

| Mã | Loại | Dữ liệu | Thao tác | Tiêu chí đạt | Artifact |
|---|---|---|---|---|---|
| AI-GATE-01 | Integration | 11 file nguồn | Nạp mỗi nguồn thành note qua HTTP; chờ worker | Mỗi note có trạng thái `READY` trước Search/RAG; lỗi/timeout tách riêng | raw JSONL ingest, `metrics.json`, log worker đã lọc |
| AI-GATE-02 | Black-box | Chạy lại cùng idempotency key | Nạp lại một nguồn | Không tạo bản sao ngoài dự kiến; trạng thái/index không thoái lui | response + số note trước/sau |
| AI-GATE-03 | White-box/integration | Worker tắt (môi trường test riêng) | Nạp 1 note rồi chờ | Runner báo `TIMEOUT`/`PROCESSING`, không tự chấm retrieval như pass | log run failure, không dùng vào metric chất lượng |

**Không được tính metric chất lượng Search/RAG nếu AI-GATE-01 không đạt.**

### 5.2. Tìm kiếm lai (Hybrid Search)

| Mã | Kỹ thuật | Tập case | Chỉ số/Oracle | Tiêu chí báo cáo |
|---|---|---|---|---|
| SEARCH-01 | Black-box API | Các dòng `answerable=yes` hợp lệ | `gold_text`/note chứa gold phải xuất hiện top-k | Recall@1/@3/@5, MRR, AnswerHit@k; nêu mẫu số hoàn thành |
| SEARCH-02 | Black-box robustness | Truy vấn tiếng Việt có dấu/không dấu, từ khóa riêng, diễn đạt (chỉ dùng case đã được người chấm xác nhận) | Gold evidence đúng | Báo tách theo nhóm truy vấn, không gộp nếu nhãn nhóm thiếu |
| SEARCH-03 | White-box/integration | Lỗi embedding/provider có kiểm soát ở môi trường test | Contract fallback API/log, không cần sửa source | Báo fallback pass/fail; không suy từ kết quả bình thường |
| SEARCH-04 | Performance | Toàn bộ case hoàn thành | HTTP elapsed trong raw | p50/p95 ms; kèm model, corpus, n, thời điểm, RPM |

**Cảnh báo bắt buộc:** corpus hiện có ít nguồn. Luôn báo `random_floor` và không dùng một Recall@5 cao đơn lẻ để kết luận hệ thống tốt.

### 5.3. PageMatch

| Mã | Kỹ thuật | Tập case | Chỉ số/Oracle | Tiêu chí báo cáo |
|---|---|---|---|---|
| PM-01 | Black-box | Nguồn HTML, `answerable=yes` | `gold_text` trong block match | Hit@k, Exact, Precision@k, Recall@k, Span Precision/Coverage/F1 |
| PM-02 | Black-box | Nguồn TXT, `answerable=yes` | Cùng gold evidence | Chứng minh luồng văn bản dán; tách bảng với HTML nếu n khác nhau |
| PM-03 | Black-box negative | 11 case `answerable=no` | Không trả đoạn khớp không liên quan | FPR và số false positive kèm case ID |
| PM-04 | Integration | HTML gốc | Kiểm tra `html` đi qua API, TXT đi `text`; không đánh giá Trafilatura nếu ngoài phạm vi | Lưu request metadata đã loại nội dung nhạy cảm |
| PM-05 | Performance | Case hoàn thành | elapsed response | p50/p95, tỷ lệ warning/fallback, error rate |

Không tự đổi HTML thành “HTML tối thiểu” để có điểm đẹp. Nếu cần kiểm thử đường text dán, dùng đúng file `.txt`; nếu cần HTML, dùng HTML nguồn nguyên gốc và giữ checksum.

### 5.4. Hỏi đáp RAG qua SSE

RAG có hai tầng cần tách: **retrieval/citation tự động** và **độ đúng ngữ nghĩa do người chấm**.

| Mã | Kỹ thuật | Tập case | Oracle | Chỉ số/Artifact |
|---|---|---|---|---|
| RAG-01 | Black-box SSE | `answerable=yes` | Có luồng `sources → delta → done`, không có lỗi | SSE event order, first-event ms, total ms, error rate |
| RAG-02 | Black-box | `answerable=yes` | Citation index hợp lệ và có source | citation presence/valid rate; đây chỉ là kiểm tra hình thức, không phải chứng minh source hỗ trợ câu trả lời |
| RAG-03 | Black-box negative | `answerable=no` | Từ chối/không có căn cứ theo contract | refusal-correct rate, FPR nguồn; người chấm xác nhận từng ca |
| RAG-04 | Human evaluation | Mọi case có câu trả lời hoặc mẫu ngẫu nhiên định trước | Rubric ở §6 | Correctness, groundedness, citation support; báo tỷ lệ và mẫu số đã review |
| RAG-05 | White-box/integration | Timeout/provider lỗi ở test environment | SSE error/settlement contract | Pass/fail theo log; không gộp vào chất lượng |

`token_f1` với `gold_text` chỉ là metric phụ, vì evidence passage không phải đáp án tự nhiên chuẩn. Không gọi nó là “độ chính xác RAG”.

### 5.5. Tóm tắt AI

API reference có `POST /ai/summaries`, nhưng harness hiện không có flow Summary. Tạo add-on **chỉ trong** `quickassist_ai_evidence/harness/`.

| Mã | Kỹ thuật | Tập case | Oracle | Artifact |
|---|---|---|---|---|
| SUM-01 | Black-box API | 11 nguồn hoặc mẫu phân tầng đã chốt trước | Response hợp lệ, không persist khi chưa xác nhận | raw response đã lọc, elapsed, token/quota nếu API trả |
| SUM-02 | Black-box integration | Một note, sau đó xác nhận lưu summary qua endpoint đã có | Lưu đúng summary, conflict/version xử lý đúng contract | response trước/sau, note read-back |
| SUM-03 | Human evaluation | Cùng tập SUM-01 | Rubric factuality/coverage/conciseness/readability | `summary_review.csv` |
| SUM-04 | Boundary/failure | Input rỗng, quá giới hạn, timeout/provider failure ở test env | 422/error đúng; quota không bị báo dùng sai | log + response đã lọc |

Không khẳng định hệ thống có cache summary nếu code/API chạy thật không chứng minh điều đó.

---

## 6. Pha 3 — Nhãn người chấm và kiểm tra tính đúng đắn trước khi đo

### 6.1. Tệp cần tạo trong `review/`

1. `annotation_guideline.md`: định nghĩa “có căn cứ”, “đúng một phần”, “từ chối đúng”, “citation hỗ trợ”.
2. `reference_answers_draft.csv`: bản sao cột `qid,source_file,question,gold_text,reference_answer,author,created_at`.
3. `reference_answers_review.csv`: `qid,reviewer,decision(accept/revise/reject),reason,reviewed_at`.
4. `rag_human_review.csv`: `run_id,qid,reviewer,answer_correct(0/1),grounded(0/1),citation_support(0/1),refusal_correct(NA/0/1),notes`.
5. `summary_review.csv`: `run_id,source_file,reviewer,factuality(1-5),coverage(1-5),conciseness(1-5),readability(1-5),critical_error(yes/no),notes`.
6. `adjudication_log.md`: ghi cách giải quyết khi hai người chấm khác nhau.

### 6.2. Quy trình nhãn

1. Người A viết `reference_answer` ngắn dựa **chỉ** vào source và `gold_text`.
2. Người B kiểm độc lập từng đáp án; không xem nhãn của A trước khi quyết định.
3. Nếu khác nhau, đánh dấu `revised`/`reject`; người thứ ba hoặc họp nhóm adjudicate; lưu lý do.
4. Đóng băng file nhãn bằng SHA-256 trước khi chạy đo.
5. Chỉ tính metric RAG/Summary chất lượng trên case có nhãn `accept`.

### 6.3. Rubric RAG

| Tiêu chí | 1 (Đạt) | 0 (Không đạt) |
|---|---|---|
| Đúng nội dung | Phù hợp đáp án tham chiếu và source | Sai, bịa, hoặc thiếu ý quyết định |
| Có căn cứ | Mọi ý chính có trong source truy xuất | Có ý chính không hỗ trợ bởi source |
| Citation hỗ trợ | Citation trỏ đúng nguồn hỗ trợ ý chính | Thiếu/sai citation hoặc citation không hỗ trợ |
| Từ chối đúng | Với case `no`, nói rõ thiếu căn cứ, không bịa | Trả lời như có căn cứ hoặc bịa |

### 6.4. Rubric Summary (1–5)

- **Factuality:** không thêm/sai thông tin so với note nguồn.
- **Coverage:** giữ được các ý chính đã xác định trước.
- **Conciseness:** ngắn hơn nguồn, không lặp vô ích.
- **Readability:** câu rõ, tiếng Việt tự nhiên, mạch lạc.
- **Critical error:** bất kỳ chi tiết bịa/sai nghiêm trọng nào; báo tỷ lệ riêng.

---

## 7. Pha 4 — Trình tự chạy chính thức và kết quả nhận được

1. Khởi động API và worker theo §4.1; giữ hai terminal đó hoạt động đến hết run.
2. Trong terminal harness, chạy `--help` kiểm tra `provider-rpm`, sau đó `--validate`.
3. Chạy baseline ở §4.1. Một run đầy đủ thực hiện: ingest → chờ index → Search → RAG SSE → PageMatch.
4. Runner sẽ tự tạo `runs/<run_id>/`. Đây là **kết quả thật** nhận được từ backend + PostgreSQL/pgvector + Gemini; không phải dữ liệu giả.
5. Đọc `metrics.json`, `report.md`, chạy `--recompute <run_id>` và lưu log. Nếu `fatal_error`, `429`, note chưa `READY` hoặc worker lỗi, gắn run là failure/blocked, không đưa vào bảng chất lượng.
6. Chạy Summary add-on theo cùng `run_id`/dataset fingerprint khi add-on ở §5.5 đã hoàn thành.
7. Người chấm hoàn thành review mà không xem metric tổng hợp trước.
8. Nếu so sánh model, lặp từ bước 3 với corpus/config frozen; không xóa run thất bại.

### Thời gian dự kiến

Với 49 case và pace provider 10 RPM, một run đủ Search + RAG + PageMatch có thể mất
**khoảng 25–40 phút** (cộng thêm thời gian Gemini/worker). Đây là hành vi mong đợi để tránh burst
và `429`, không phải runner bị treo. Không chạy hai run song song.

### Kết quả chắc chắn có sau một run thành công

| File | Có thể dùng làm gì |
|---|---|
| `run_manifest.json` | Chứng minh cấu hình, model metadata, command, dataset fingerprint và RPM. |
| `raw_results.jsonl` | Đối soát từng câu hỏi/câu trả lời/citation/độ trễ. |
| `metrics.json` | Lấy các số metric thực tế cho Search, RAG kỹ thuật, PageMatch, ingest và quota. |
| `report.md` | Bản bảng tóm tắt để chuyển vào Final Report sau khi rà soát. |
| `metrics.recomputed.json` | Xác minh lại metric được tính từ raw, không sửa tay. |

Không dùng `--allow-partial` hay `--allow-degraded` trong run chất lượng. Nếu buộc phải dùng để chẩn đoán, tag run là `failure` và tách khỏi báo cáo kết quả.

---

## 8. Pha 5 — Bằng chứng và bảng đưa vào Final Report

### 8.1. Artifact tối thiểu cho mỗi run

```text
runs/<run_id>/
├── run_manifest.json       # command, model, embedding, config RPM, dataset hash
├── raw_results.jsonl       # từng case thô, không có secret
├── metrics.json            # chỉ số runner tổng hợp
├── metrics.recomputed.json # kiểm tra tái lập từ raw
└── report.md               # bản tóm tắt sinh tự động
```

### 8.2. Bảng kết quả được phép công bố

| Nhóm | Chỉ số chính | Bắt buộc kèm theo |
|---|---|---|
| Ingest | READY/FAILED/TIMEOUT rate; wait-index p50/p95 | số nguồn, worker/config, timestamp |
| Search | Recall@1/@3/@5, MRR, AnswerHit@k | số case hoàn thành, random floor, corpus size, model/embedding |
| PageMatch | Hit/Exact/Precision/Recall/F1@k; Span Coverage; FPR | tách HTML/TXT, quality/fallback, n âm/dương |
| RAG kỹ thuật | SSE success, citation presence/valid, refusal-correct, p50/p95 | n, rate/error, citation chỉ là structural check |
| RAG người chấm | Correctness, groundedness, citation support | rubric, số reviewer, n reviewed, adjudication rule |
| Summary | điểm rubric trung bình/median, critical-error rate | rubric, n, reviewer, source version |

### 8.3. Các câu không được viết trong Final Report nếu chưa có bằng chứng

- “Mô hình đạt X% chính xác” khi chưa có nhãn người chấm/reference answer.
- “Gemini tốt hơn model khác” khi embedding/retrieval/prompt/corpus cùng lúc thay đổi.
- “Không vượt quota/RPM” nếu manifest/log không ghi pacing và không có run thật.
- “PageMatch chính xác” chỉ từ Hit@k mà không nêu false-positive, span coverage và loại input.
- “Tóm tắt có cache” nếu API/code thực tế không chứng minh.

---

## 9. Tiêu chí hoàn thành giao việc cho Antigravity

- [ ] Toàn bộ tệp mới/được sửa nằm trong `quickassist_ai_evidence/`.
- [ ] QuickAssist gốc không có thay đổi Git; nếu dùng ngoại lệ, có `EXCEPTION_REQUEST.md` và approval.
- [ ] `--validate` và test harness có log pass/fail thật.
- [ ] Có checksum input, fingerprint dataset và snapshot version code.
- [ ] Có run smoke và run quality tách riêng.
- [ ] Mỗi metric có n, đơn vị, phương pháp, run ID, model/embedding/config và timestamp.
- [ ] Có review độc lập/phiếu adjudication cho RAG và Summary trước khi công bố điểm chất lượng.
- [ ] Báo cáo chỉ dùng số từ `runs/` và `review/`, có phần hạn chế nêu rõ corpus hiện còn nhỏ.

## 10. Đầu ra Antigravity phải bàn giao

1. `quickassist_ai_evidence/README_EXECUTION.md`: hướng dẫn chạy lại từ đầu.
2. `quickassist_ai_evidence/review/`: guideline, form nhãn rỗng, và log adjudication mẫu (không điền kết quả giả).
3. `quickassist_ai_evidence/reports/EVIDENCE_REGISTER.md`: từng chức năng, evidence path, trạng thái `Verified / Missing evidence`.
4. `quickassist_ai_evidence/reports/FINAL_REPORT_AI_SECTION_DRAFT.md`: khung bảng cho báo cáo, mọi ô chưa đo phải ghi `[CẦN ĐIỀN SAU KHI CHẠY]`.
5. Không bàn giao “kết quả cuối” nếu chưa có backend/provider chạy thật và người chấm hoàn tất nhãn.
