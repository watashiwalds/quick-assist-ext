# Báo cáo đánh giá `steady_evaluation` — nhãn `local-qwenternary-qwenqte`

**Run:** `20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local`
**Thời gian:** 2026-11-21 09:32:51 → 09:49:10 (GMT+7) · **16 phút 19 giây**
**Nhãn model (do người chạy đặt):** `local-qwenternary-qwenqte`
**Trạng thái:** hoàn tất đủ 3 module · **0 lỗi case** · `--recompute` khớp hoàn toàn

> Báo cáo này đọc từ artifact thật của run: `run_manifest.json`, `raw_results.jsonl`,
> `metrics.json`, `report.md`. Mọi số dưới đây lấy từ `metrics.json`, trừ các bảng
> tách HTML/TXT được tính lại từ `raw_results.jsonl` bằng chính hàm chấm của `steady_metrics.py`.
> File `runs/MODEL_COMPARISON.md` đã được cập nhật bằng `--compare`.

---

## 0. Kết luận điều hành

1. **Pipeline chạy trọn vẹn trên hệ thống thật:** 11/11 nguồn `READY`, 38/38 search,
   38/38 RAG answerable + 11/11 RAG unanswerable, 49/49 PageMatch — **0 lỗi**, 0 case bị bỏ.
2. **Ingest đủ nội dung:** 25 part cho 11 tài liệu, index **316.032/316.049 ký tự (100%)**,
   không file nào bị cắt. Chờ index p95 = **53,4 s**, đến từ file TXT 156,9k ký tự (9 part).
3. **Search giữ nguyên hai vùng rất khác nhau:**
   - 8 nguồn **HTML** (22 câu): Recall@5 **22/22 = 1,0**; MRR **0,9697**.
   - 3 nguồn **TXT** (16 câu): Recall@5 **5/16 = 0,3125**; MRR **0,2812**. Toàn bộ 11 ca trượt
     top-5 đều thuộc nhóm TXT → **nút thắt là truy hồi cross-lingual trên văn bản học thuật
     tiếng Anh**, không phải giới hạn kích thước note.
4. **RAG:** trích dẫn hợp lệ **0,7368** (28/38), **0 số ngoài ngữ cảnh**, token-F1 gold 0,1629
   (metric phụ). Tách nhóm: HTML trích dẫn **20/22**, TXT chỉ **8/16**; 8 ca TXT không trích dẫn
   đều là câu **từ chối** vì không lấy được ngữ cảnh — khớp với Recall@5 thấp của TXT.
5. **Từ chối câu không có căn cứ:** heuristic báo **9/11 (0,8182)**, nhưng kiểm tra tay cho thấy
   **QA-006 thực chất đã từ chối** (“…tôi không tìm thấy lý do…”), chỉ bị bộ marker bỏ sót →
   tỷ lệ thật **10/11 (0,909)**. Ca trả lời bừa thật sự: **QA-049** (1/11).
6. **PageMatch:** segments hit **0,7895**, Precision@5 **0,2754**, Span Coverage **0,7952**;
   FPR **0,5** (6 ca âm). Chế độ full-page: hit **0,5**, Full-page F1 **0,7642**, FPR **1,0**.
   Độ trễ cao: p50 **10,8 s**, p95 **25,6 s**; **11/49 ca bị truncate** (đều là TXT).
7. **So với run cùng dataset/config gần nhất** (`20261119_173736`, cùng 49 cặp, cùng embedding):
   Recall/MRR **trùng khít từng chữ số** (search gần như tất định), trong khi RAG trích dẫn
   **+0,184**, PageMatch hit **+0,19** nhưng FPR **+0,167**, token tiêu thụ **+33%**.

---

## 1. Điều kiện chạy — đã kiểm tra trước khi chạy

| Điều kiện | Cách kiểm tra | Kết quả |
|---|---|---|
| Backend sống | `GET /api/v1/health/live` | `200 {"status":"ok"}` |
| DB sẵn sàng | `GET /api/v1/health/ready` | `{"status":"ok","db":"ok"}` |
| Worker chạy | `ps` | `python -m quickassist.worker` đang chạy |
| Model server | `GET :8080/v1/models` | `chat`, `embed` |
| Xác thực | `POST /auth/dev-login` với `steady-eval@quickassist.local` | `200`, cấp access/refresh token |
| Dataset hợp lệ | `run_evaluation.py --validate` | 49 cặp, 0 dòng bị loại, exit 0 |
| Tái lập | `run_evaluation.py --recompute <run>` | ✓ khớp hoàn toàn |

Không cần tạo `steady_evaluation/.env`: toàn bộ tham số truyền qua CLI (giá trị mặc định
`http://localhost:8000/api/v1` và email ở trên trùng với `.env.example`).

### Môi trường model thực tế (đọc từ tiến trình `llama-server` và `local_infer/models-preset.ini`)

| Vai trò | Model | Cấu hình |
|---|---|---|
| Chat | `Ternary-Bonsai-2-9B-PQ2_0-MTP-Q8_0.gguf`, alias `chat` | GPU 99 layer, ctx **8.192**, `parallel 1`, KV `q8_0`, `reasoning off`, `cache-prompt off`, `ctx-checkpoints 0` |
| Embedding | `gte-Qwen2-1.5B-instruct-Q4_K_M.gguf`, alias `embed` | CPU, 6 thread, ctx **4.096**, `pooling last`, KV `q8_0` |
| Backend | `uvicorn quickassist.main:app` cổng 8000 | FastAPI + PostgreSQL/pgvector + worker |

> **Lưu ý trung thực về nhãn:** `local-qwenternary-qwenqte` là **metadata do người chạy đặt**
> (đúng như yêu cầu), không được backend tự đọc ra. Model chat thực tế là Ternary-Bonsai-2-9B
> (bản ternary-quantized), embedding là gte-Qwen2-1.5B; cả hai là model local. Khi so sánh với
> run cũ, cần đọc thêm mục cấu hình vì nhãn khác nhau nhưng thiết bị model tương đương.

---

## 2. Cấu hình run

| Thành phần | Giá trị |
|---|---|
| Lệnh | `run_evaluation.py --model-label local-qwenternary-qwenqte --provider openai --model chat --embedding-model gte-Qwen2-1.5B-instruct --tag lat3-full-local --fresh-notes --cleanup-notes` |
| Modules | `search, rag, pagematch` |
| `top_k` (note) / `pagematch_top_k` | 5 / 5 |
| `max_sources` | 5 |
| `split_chars` | 20.000 (`--truncate-long` **tắt** → chia part, không cắt) |
| Folder | `run` — thư mục riêng cho run (`dde18d92-…`), `--fresh-notes`, dọn note + folder sau khi chấm |
| Evidence type | `quality` (dataset ≥ 20 cặp và có nhãn model) |
| Git commit | `6d09ed9c3565787ac3c88933cd40273970409efc` |
| `eval_code_sha256` | `824b467cfefb0aad04036665542cdc1f3d5af9b1607fbed03d4713a2b6417688` |
| Python | 3.14.4 |
| Quota | BYOK, 1.000.000 token, không bật enforcement; tiêu thụ **588.953**, còn 411.047 |
| Dataset fingerprint | `ef7c82ca643482ab` (giống run 19/11) |

---

## 3. Dataset

| Chỉ số | Giá trị |
|---|---:|
| Nguồn | 11 (8 HTML + 3 TXT) |
| Cặp hỏi–đáp | 49 (38 answerable, 11 unanswerable) |
| `reference_answer` | 0 |
| Dòng bị loại | **0** |
| Độ dài văn bản phẳng | min 2.865 · median 5.964 · max 156.885 ký tự |

Phân bố theo nhóm nguồn (dùng cho các bảng tách nhóm bên dưới):

| Nhóm | Answerable | Unanswerable | Tổng |
|---|---:|---:|---:|
| HTML | 22 | 9 | 31 |
| TXT | 16 | 2 | 18 |

---

## 4. Ingest (nạp note + chờ index)

| Chỉ số | Giá trị |
|---|---:|
| File | 11 — `READY` **11/11 (1,0)** |
| Tạo mới / replay | 11 / 0 |
| Tài liệu → part | 11 → **25 part**, part READY **25/25**, file đủ part READY **11/11** |
| Ký tự index | **316.032 / 316.049 (1,0)** |
| Part lớn nhất | 17.995 ký tự (dưới trần 20.000) |
| File bị cắt | 0 |
| `create` p50 | 25,83 ms |
| Chờ index p50 / p95 | 3.019,71 ms / **53.366,17 ms** |

Ba file chậm nhất (quyết định p95):

| File | Part | Ký tự | Chờ index |
|---|---:|---:|---:|
| `Evaluating Quantized Large Language.txt` | 9 | 156.876 | 53.366 ms |
| `LORA LOW-RANK ADAPTATION.txt` | 5 | 82.872 | 28.179 ms |
| `Attention Is All You Need.txt` | 3 | 39.584 | 13.078 ms |

**Đọc:** mọi nội dung đều được index đủ (không còn hiện tượng cắt 20k như run “trước” ngày
19/11). Chi phí chờ index tỷ lệ với số part của văn bản dài; đây là chi phí một lần cho mỗi
corpus, không nằm trên đường người dùng.

---

## 5. Tìm kiếm ngữ nghĩa (`POST /search`)

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Note TB | Rỗng | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0,7105 | 0,7105 | 0,6798 | 0,7105 | 0,7105 | 3,68 | 4,08 | 0,0 | 194,4 ms | 269,0 ms |

Sàn ngẫu nhiên với `top_k=5`, 11 tài liệu: **0,4545**. `max_sources` quan sát đúng bằng 5
(39,5% ca chạm trần nguồn), không có gold vắt qua ranh giới part.

### Tách theo nhóm nguồn

| Nhóm | n | Recall@5 | MRR | Ca trượt top-5 |
|---|---:|---:|---:|---|
| HTML | 22 | **1,0000** | **0,9697** | 0 |
| TXT | 16 | **0,3125** | **0,2812** | 11 (QA-032, 034, 037–039, 041, 043–046, 048) |

**Đọc:** search gần như hoàn hảo trên báo tiếng Việt (HTML) và yếu có hệ thống trên 3 bài báo
khoa học tiếng Anh (TXT). Vì index đã đủ 100% ký tự, nguyên nhân nằm ở **truy hồi
cross-lingual + ngưỡng tương đồng**, không phải mất nội dung. Độ trễ search rất thấp
(p95 < 300 ms), nên đây là vấn đề chất lượng thuần, không phải hiệu năng.

---

## 6. RAG hỏi đáp (SSE thật)

### 6.1 Câu có căn cứ (answerable)

| n | Hoàn thành | Lỗi | Token-F1 gold (phụ) | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | Token TB | first-event p50 | total p50 / p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0,1629 | **0,7368** (28/38) | 0,2632 (10/38) | **0,0** | 1.399,7 | 212,4 ms | 3.332,3 / 5.481,0 ms |

- `no_source_rate` = 0,0 · `no_context_rate` = 0,0 · ngữ cảnh trung bình **25.099 ký tự**.

| Nhóm | n | Trích dẫn hợp lệ | Không trích dẫn | Token-F1 gold |
|---|---:|---:|---:|---:|
| HTML | 22 | **20/22 = 0,9091** | 2/22 | 0,2635 |
| TXT | 16 | **8/16 = 0,5000** | 8/16 | 0,0246 |

10 ca không trích dẫn gồm 2 ca HTML (QA-009, QA-029) và **8 ca TXT** — cả 8 ca TXT đều là câu
trả lời dạng “Ghi chú của bạn chưa có thông tin…”, tức model **không nhận được ngữ cảnh chứa
đáp án** (khớp Recall@5 TXT = 0,3125), không phải model bịa. Đây là hệ quả trực tiếp của
truy hồi, không phải của prompt.

### 6.2 Câu không đủ căn cứ (unanswerable)

| n | Hoàn thành | Lỗi | Từ chối đúng (heuristic) | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0,8182 (9/11) | 0,1818 (2/11) | 0,0 |

Kiểm tra tay từng ca:

- **QA-006** (“Vì sao Mỹ tấn công Iraq?”) — model trả lời *“Dựa trên các nguồn thông tin đã
  cung cấp, **tôi không tìm thấy lý do** cụ thể…”* → **thực chất là từ chối**, nhưng bộ marker
  chỉ có `khong tim thay thong tin` / `khong tim thay ghi chu`, không có `khong tim thay ly do`
  → **âm tính giả của heuristic**.
- **QA-049** (“Mô hình LLM Trung Quốc có hiệu suất thế nào sau khi quantization?”) — model trả
  lời bằng nội dung benchmark 8-bit/FP16 lấy từ ngữ cảnh → **trả lời bừa thật** so với nhãn
  `answerable=no` của dataset.

⇒ Tỷ lệ từ chối đúng thực tế **≈ 10/11 (0,909)**, trả lời bừa thật **1/11**. Metric trong
`metrics.json` vẫn giữ 9/11 vì report phải tái lập được từ thuật toán hiện hành; đây là
**ranh giới đã biết** của heuristic, không phải lỗi dữ liệu.

---

## 7. PageMatch

49 ca, **0 lỗi**. `verify_unavailable_rate` = 0,0408 (2 ca), `full_page_mode_rate` = 0,4898
(24/49), `truncated_rate` = **0,2245** (11/49 — toàn bộ là TXT).

### 7.1 Chất lượng — segments (không warning, top-5)

| Dương tính | Hit | Exact | Precision@5 | Recall@5 | F1@5 | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 19 | **0,7895** | 0,7895 | **0,2754** | 0,7895 | 0,3737 | 0,1609 | **0,7952** | 0,2295 | 6 | **0,5000** | 10.781 ms |

### 7.2 Chất lượng — full-page (tách riêng)

| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 18 | **0,5000** | 0,5880 | **0,7642** | 4 | **1,0** |

Độ trễ toàn module: p50 **10.781 ms**, p95 **25.593 ms** — cao hơn RAG/search một bậc.

### 7.3 Tách theo nhóm nguồn (tính lại từ raw)

| Nhóm | Chế độ | Dương tính | Hit | Precision@5 | Span Coverage | Âm tính | FPR |
|---|---|---:|---:|---:|---:|---:|---:|
| HTML | segments | 10 | 0,900 | 0,368 | 0,900 | 5 | 0,40 |
| HTML | full-page | 12 | 0,583 | 0,117 | 0,626 | 3 | 1,00 |
| TXT | segments | 9 | 0,667 | 0,172 | 0,679 | 1 | 1,00 |
| TXT | full-page | 6 | 0,333 | 0,100 | 0,513 | 1 | 1,00 |

**Đọc:** khả năng “tìm đúng block” (Hit/Coverage) khá tốt ở segments, nhưng **precision thấp**
vì API trả nhiều block (tối đa top-5) và block trả về thường lớn hơn đoạn gold. FPR ở đây đo
“có trả block ứng viên hay không”, **không** phải “có khẳng định câu trả lời hay không” —
với full-page, API gần như luôn trả cả trang nên FPR = 1,0 là hệ quả thiết kế, cần đọc kèm
`full_page_mode_rate`. 11/49 ca TXT bị truncate đầu vào PageMatch, làm giảm cả chất lượng lẫn
tăng độ trễ của nhóm này.

### 7.4 Ca fallback (warning `VERIFY_UNAVAILABLE`)

2 ca (1 dương tính full-page: Hit 1,0, Coverage 1,0, Full-page F1 0,7346; 1 âm tính full-page
FPR 1,0 nhưng `verified_fpr` 0,0). Chỉ báo hành vi, **không gộp** vào chất lượng chính.

---

## 8. So sánh với run gần nhất cùng dataset/config

Cùng `dataset_fingerprint ef7c82ca643482ab`, cùng `top_k=5`, `max_sources=5`, cùng embedding
`gte-Qwen2-1.5B`:

| Chỉ số | `20261119_173736` (lat3-full) | **Run này** | Δ |
|---|---:|---:|---:|
| Search Recall@5 | 0,7105 | **0,7105** | 0 |
| Search MRR | 0,6798 | **0,6798** | 0 |
| RAG Token-F1 gold | 0,1694 | **0,1629** | −0,0065 |
| RAG trích dẫn hợp lệ | 0,5526 | **0,7368** | **+0,1842** |
| RAG từ chối đúng (heuristic) | 0,9091 | **0,8182** | −0,0909 |
| RAG total p50 | 3.782,7 ms | **3.332,3 ms** | −450 ms |
| PageMatch segments Hit | 0,6000 | **0,7895** | **+0,1895** |
| PageMatch segments FPR | 0,3333 | **0,5000** | +0,1667 |
| Token tiêu thụ | 442.183 | **588.953** | **+33,2%** |

**Diễn giải thận trọng:**

- Search trùng khít ⇒ với cùng corpus + cùng embedding, truy hồi gần như **tất định**; mọi
  khác biệt còn lại đến từ model chat / cấu hình serving.
- Trích dẫn tăng mạnh nhưng độ dài câu trả lời cũng tăng (token +33%), phù hợp với việc model
  trả lời dài hơn và chèn `[n]` nhiều hơn; **không** đồng nghĩa câu trả lời đúng hơn
  (Token-F1 còn giảm nhẹ).
- Đợt này `chat` chạy ctx **8.192** (bản preset hiện tại) so với 12.288 trong báo cáo 19/11;
  `cache-prompt`/`ctx-checkpoints` đều tắt. Đây là biến số môi trường cần ghi nhớ khi so sánh.
- Số từ chối thấp hơn một phần là do heuristic (QA-006) chứ không phải model trả lời bừa nhiều
  hơn; sau khi đối chiếu tay, chênh lệch thực chỉ còn 1 ca (QA-049).

---

## 9. Hạn chế & khuyến nghị

**Hạn chế của phép đo (đọc kèm mọi con số):**

- Token-F1 là trùng từ với đoạn gold — metric **phụ**, không phản ánh đúng ngữ nghĩa.
- Trích dẫn chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và có ít nhất một trích dẫn; **chưa
  kiểm chứng nguồn có thực sự hỗ trợ ý** (cần rubric người hoặc entailment).
- “Số ngoài ngữ cảnh” là proxy chuỗi trên toàn văn note, không phải kết luận bịa.
- Phát hiện từ chối là heuristic marker ở câu đầu → đã bỏ sót QA-006 (xem §6.2).
- PageMatch FPR đo “có trả block”, không đo “có khẳng định đáp án”; Full-page F1 so với văn bản
  do tool trích, không phải ground-truth của backend.
- Dataset 11 tài liệu ⇒ sàn ngẫu nhiên 0,4545 khi `top_k=5`; Recall@5 phải đọc kèm sàn này.
- Độ trễ là end-to-end HTTP (gồm provider), chưa tách thời gian DB thuần.

**Khuyến nghị ưu tiên:**

1. **Truy hồi TXT cross-lingual** là nút thắt lớn nhất: thử query expansion/dịch truy vấn, tăng
   trọng số hybrid, hoặc embedding đa ngữ mạnh hơn. Đây là thay đổi có khả năng nâng cả search,
   RAG citation và PageMatch TXT cùng lúc.
2. **Mở rộng bộ marker từ chối** (thêm `khong tim thay` tổng quát, `khong phat hien`, …) và
   thêm test hồi quy cho QA-006; ghi nhận QA-049 như ca trả lời bừa thật.
3. **PageMatch với văn bản dài:** 22,4% ca bị truncate và p95 ~25,6 s. Cân nhắc lọc block trước
   khi gọi model, hoặc tăng trần đầu vào; đồng thời thêm ngưỡng confidence để giảm FPR full-page.
4. **Bổ sung `reference_answer`** cho dataset để có thêm F1-reference, và tăng corpus/câu nhiễu
   để Recall@5 có ý nghĩa thống kê hơn.
5. **Cố định cấu hình serving** (ctx-size, cache flags, sampling) giữa các run và ghi vào
   manifest, vì đây là biến số ảnh hưởng trực tiếp tới token và chất lượng RAG/PageMatch.

---

## 10. Tái lập & artifact

```bash
cd steady_evaluation
python3 run_evaluation.py \
  --model-label "local-qwenternary-qwenqte" \
  --provider openai --model chat --embedding-model "gte-Qwen2-1.5B-instruct" \
  --tag lat3-full-local \
  --fresh-notes --cleanup-notes

python3 run_evaluation.py --recompute 20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local
python3 run_evaluation.py --compare
```

Artifact (trong `steady_evaluation/runs/20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local/`):

| File | Nội dung |
|---|---|
| `run_manifest.json` | cấu hình, model, dataset, fingerprint, `eval_code_sha256`, git commit, folder |
| `raw_results.jsonl` | 147 case thô (11 ingest + 38 search + 49 RAG + 49 PageMatch) |
| `metrics.json` | chỉ số tổng hợp, quota before/after, token tiêu thụ |
| `metrics.recomputed.json` | metrics tái tạo từ raw — **diff khớp hoàn toàn** |
| `report.md` | báo cáo do pipeline sinh |

Bảng so sánh tổng hợp: `steady_evaluation/runs/MODEL_COMPARISON.md`.
