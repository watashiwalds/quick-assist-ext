# Báo cáo đánh giá `steady_evaluation` — nhãn `local-qwen3.5_4b-qwen3embed`

**Run:** `20261121_043458_145357_local-qwen3-5-4b-qwen3embed_lat3-full-local`
**Thời gian:** 2026-11-21 11:34:58 → 11:48:29 (GMT+7) · **13 phút 31 giây**
**Nhãn model (do người chạy đặt):** `local-qwen3.5_4b-qwen3embed`
**Trạng thái:** hoàn tất 3 module · **0 lỗi case** · `--recompute` khớp hoàn toàn

> Báo cáo đọc từ artifact thật của run. Số tổng hợp lấy từ `metrics.json`; các bảng tách
> HTML/TXT và phần đối chiếu refusal được tính lại từ `raw_results.jsonl` bằng chính hàm
> chấm của `steady_metrics.py` (metrics v4). Run trước được chấm lại cùng định nghĩa để
> so sánh PageMatch công bằng.

---

## 0. Kết luận điều hành

1. **Hạ tầng và ingest ổn định:** backend, DB, worker đều sống; 11/11 tài liệu `READY`,
   25/25 part `READY`, index đủ **316.032/316.032 ký tự (100%)**, không cắt file.
2. **Search không đổi so với run cùng embedding:** Recall@5 **0,9737**, MRR **0,9342**,
   giống hệt run `local-qwenternary-qwen3embed`. Đây là dấu hiệu tốt về tính tất định:
   cùng corpus + cùng `Qwen3-Embedding-0.6B` thì kết quả retrieval lặp lại được.
   Vẫn còn đúng 1 ca search rỗng (QA-038).
3. **RAG: trích dẫn tốt hơn nhưng trả lời dài và chậm hơn rõ rệt.** Trích dẫn hợp lệ
   **0,8421 → 0,9211** (+7,9 điểm %), nhưng tổng thời gian p50 **2.645 → 4.953 ms**
   (+87,2%). Nguyên nhân chính là câu trả lời dài hơn khoảng **45%** (745 so với 514
   ký tự/câu); tốc độ sinh chữ xấp xỉ nhau (~150 ký tự/giây), không phải model chậm đi.
4. **RAG vẫn còn lỗi nội dung cần xử lý:** QA-033 trả sai bộ dữ liệu (WSJ thay vì
   WMT 2014) kèm số 40.000 không có trong ngữ cảnh; QA-009 nêu "năm 2024" không có
   trong nguồn; QA-044 bỏ sót gold "Microsoft Corporation". QA-040 là cảnh báo proxy
   số `10.000` (nguồn viết `10,000`), nhiều khả năng không phải bịa.
5. **Từ chối trên câu không có căn cứ nhìn chung vẫn tốt, dù metric heuristic giảm.**
   Heuristic báo 7/11 từ chối đúng (0,6364), nhưng đọc tay: QA-006 và QA-024 **có từ chối**
   (marker không nằm ở câu đầu), QA-020 và QA-049 là **tranh chấp nhãn dataset** —
   nội dung trả lời có căn cứ trong nguồn. Không có ca nào bịa số ở nhóm âm.
6. **PageMatch giảm ở chỉ số tổng nhưng đổi cấu trúc:** `hit_all` **0,7632 → 0,6579**,
   `verified_recall` **0,6842 → 0,6316**, trong khi FPR **0,5455 → 0,3636** (tốt hơn).
   Nhóm segments (không warning) lại tăng nhẹ (hit **0,5714 → 0,5938**); nguyên nhân
   giảm tổng chủ yếu do ít ca full-page hơn (18,4% → 10,2%) và 5 ca mất hit so với 1 ca
   được thêm. Đây là **đánh đổi chất lượng**, không phải "embedding hỏng" — embedding
   không đổi.
7. **Độ trễ PageMatch tốt hơn:** p50 **9.908 → 6.112 ms** (−38,3%), p95 **21.808 →
   18.287 ms** (−16,1%), nhờ ít full-page hơn và model chat 4B xử lý thẩm định nhanh hơn.
8. **Tiêu thụ token gần như không đổi:** **562.444** so với 561.371 (+0,19%). Quota BYOK
   đã vượt 1.000.000 token từ trước nhưng **enforcement đang tắt**, không ảnh hưởng run.

---

## 1. Điều kiện chạy — đã kiểm tra

| Điều kiện | Cách kiểm tra | Kết quả |
|---|---|---|
| Backend sống | `GET /health/live` | `200 {"status":"ok"}` |
| DB sẵn sàng | `GET /health/ready` | `{"status":"ok","db":"ok"}` |
| Worker | `ps` | `python -m quickassist.worker` đang chạy |
| Model server | `GET :8080/v1/models` | `chat`, `embed` |
| Embedding | `POST :8080/v1/embeddings` | **1.024 chiều**, alias `embed` |
| Xác thực | `POST /auth/dev-login` | OK (114 ms) |
| Dataset | `run_evaluation.py --validate` | 49 cặp, 0 dòng loại, exit 0 |
| Tái lập | `run_evaluation.py --recompute` | ✓ khớp hoàn toàn |

### Môi trường model thực tế

| Vai trò | Model | Cấu hình |
|---|---|---|
| Chat | `Qwen_Qwen3.5-4B-Q4_K_S.gguf` (alias `chat`) | 4,33B tham số · Q4_K_S · GPU 99 layer · ctx 8.192 · `reasoning off` |
| Embedding | `Qwen3-Embedding-0.6B-Q8_0.gguf` (alias `embed`) | CPU 6 thread · ctx 4.096 · **1.024 chiều** · `pooling last` |
| Backend | `uvicorn quickassist.main:app` :8000 | FastAPI + PostgreSQL/pgvector + worker |

> **Nhãn:** `local-qwen3.5_4b-qwen3embed` là metadata do người chạy đặt, khớp với cặp model
> đang chạy. `run_id` bị sanitize dấu chấm thành dấu gạch (`qwen3-5-4b`) nhưng
> `model_label` trong manifest giữ nguyên.

---

## 2. Cấu hình run

| Thành phần | Giá trị |
|---|---|
| Lệnh | `run_evaluation.py --model-label local-qwen3.5_4b-qwen3embed --provider openai --model chat --embedding-model Qwen3-Embedding-0.6B-Q8_0 --tag lat3-full-local --fresh-notes --cleanup-notes` |
| Modules | `search, rag, pagematch` |
| `top_k` / `pagematch_top_k` / `max_sources` | 5 / 5 / 5 |
| `split_chars` | 20.000 (`--truncate-long` tắt → chia part, không cắt) |
| Folder | `run` (`53429f93-…`), `--fresh-notes`, dọn note + folder sau khi chấm |
| Evidence type | `quality` |
| Dataset fingerprint | `ef7c82ca643482ab` (không đổi) |
| `eval_code_sha256` | `6808d78d446fb98372b42529fa0a82d139955a144531da27af7d61fdbfa71b3b` |
| Git commit trong manifest | `5b751bb1b103ad774690df43223c86d9e6ca5117` |
| Python | 3.14.4 |
| Token tiêu thụ run này | **562.444** · quota sau run: 1.712.768 / 1.000.000 (BYOK, **enforcement tắt**) |

> Trong lúc run đang chạy, repo có thêm commit `46f5435` (sửa metric PageMatch). Manifest
> vẫn ghi commit lúc bắt đầu (`5b751bb`), còn `eval_code_sha256` là hash thực tế của code
> đánh giá. `--recompute` bằng code hiện tại khớp hoàn toàn, nên artifact tái lập được.

---

## 3. Dataset

| Chỉ số | Giá trị |
|---|---:|
| Nguồn | 11 (8 HTML + 3 TXT) |
| Cặp hỏi–đáp | 49 (38 answerable, 11 unanswerable) |
| `reference_answer` | 0 |
| Dòng bị loại | 0 |
| Độ dài văn bản | min 2.865 · median 5.964 · max 156.885 ký tự |

| Nhóm | Answerable | Unanswerable | Tổng |
|---|---:|---:|---:|
| HTML | 22 | 9 | 31 |
| TXT | 16 | 2 | 18 |

---

## 4. Ingest

| Chỉ số | Giá trị |
|---|---:|
| File | 11 — `READY` **11/11 (1,0)**, tạo mới 11 / replay 0 |
| Tài liệu → part | 11 → **25 part**, part READY **25/25**, đủ part **11/11** |
| Ký tự index | **316.032 / 316.032 (1,0)** |
| Part lớn nhất | 17.995 ký tự · file bị cắt: **0** |
| `create` p50 | 25,01 ms |
| Chờ index p50 / p95 | **2.014,43 ms** / **40.274,87 ms** |

Chờ index p50 giảm so với run trước (3.018,77 → 2.014,43 ms), p95 gần như không đổi.
Đây là chi phí một lần cho mỗi corpus, không nằm trên đường người dùng.

---

## 5. Tìm kiếm ngữ nghĩa (`POST /search`)

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | **0,9737** | 0,8947 | **0,9342** | 0,9737 | 0,8947 | **1,58** | 3 | 2,42 | 0,0263 | **114,95 ms** | **185,14 ms** |

Sàn ngẫu nhiên (top_k=5, 11 tài liệu): **0,4545**. Không ca nào chạm trần `max_sources`.
Kết quả **giống hệt run trước** (Recall@5 0,9737; MRR 0,9342), đúng kỳ vọng vì embedding
không đổi.

### Tách theo nhóm nguồn

| Nhóm | n | Recall@5 | MRR | Ca trượt top-5 |
|---|---:|---:|---:|---|
| HTML | 22 | **1,0000** | **0,9773** | 0 |
| TXT | 16 | **0,9375** (15/16) | **0,8750** | 1 (QA-038 — trả **rỗng**) |

**Đọc:** retrieval vẫn là điểm mạnh nhất của cấu hình này. Nút thắt duy nhất vẫn là QA-038
(đơn vị nghiên cứu bài Transformer, văn bản TXT) trả 0 nguồn — kéo theo 1 ca RAG không
nguồn/không ngữ cảnh. Cần xem ngưỡng similarity cho câu hỏi ngắn trên tài liệu dài.

---

## 6. RAG hỏi đáp (SSE thật)

### 6.1 Câu có căn cứ

| n | Hoàn thành | Lỗi | Token-F1 gold (phụ) | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | Token TB | first-event p50 | total p50 / p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | **0,1638** | **0,9211** (35/38) | 0,0789 (3/38) | **0,0789** (3/38) | **1.209,7** | 133,58 ms | **4.952,55** / 9.395,09 ms |

- `no_source_rate` = 0,0263 · `no_context_rate` = 0,0263 · ngữ cảnh TB **26.155 ký tự**.
- 3 ca không trích dẫn: **QA-022**, **QA-038**, **QA-044**.
- 3 ca có số ngoài ngữ cảnh: **QA-009** (`2024`), **QA-033** (`40000`), **QA-040** (`10000`).

| Nhóm | n | Trích dẫn hợp lệ | Không trích dẫn | Token-F1 gold |
|---|---:|---:|---:|---:|
| HTML | 22 | **21/22 = 0,9545** | 1/22 (QA-022) | 0,2477 |
| TXT | 16 | **14/16 = 0,8750** | 2/16 (QA-038, QA-044) | 0,0485 |

**Đọc chất lượng câu trả lời:**

- **QA-033** là lỗi rõ nhất: hỏi bộ dữ liệu huấn luyện Transformer, gold là **WMT 2014**;
  model trả lời **WSJ** và nêu "40.000 câu" không có trong ngữ cảnh.
- **QA-009** nêu "Hoàn thành năm 2024" trong khi nguồn/gold chỉ nói năm 2025 — lỗi năm.
- **QA-044** nói không có thông tin dù gold là **Microsoft Corporation** — bỏ sót.
- **QA-022** không trích dẫn và bỏ sót chi tiết 17 người; câu trả lời chỉ đúng một phần.
- **QA-040** (`10.000`) nhiều khả năng là **dương tính giả của proxy số**: nguồn viết
  `10,000` và `10,000×`; cần đối chiếu tay trước khi kết luận bịa.
- **QA-017** bị heuristic coi là "từ chối" nhưng thực ra có nêu gold ("hàng chục nghìn tỷ
  USD") — đây là hạn chế của marker, không phải lỗi nội dung.

### 6.2 Câu không đủ căn cứ

| n | Hoàn thành | Lỗi | Từ chối đúng (heuristic) | Trả lời bừa (heuristic) | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | **0,6364** (7/11) | 0,3636 (4/11) | 0,0 |

Heuristic đánh dấu 4 ca "trả lời bừa": **QA-006, QA-020, QA-024, QA-049**. Đọc tay:

- **QA-006** và **QA-024** thực chất **có từ chối** ("không có mặt trong dữ liệu",
  "chưa có thông tin xác nhận thủ phạm") nhưng marker không nằm ở câu đầu → **âm tính giả
  của heuristic**.
- **QA-020** (Dyson Sphere) và **QA-049** (LLM Trung Quốc sau quantization) trả lời bằng
  nội dung **có trong nguồn**; dataset lại gắn `answerable=no`. Đây là **vấn đề nhãn
  dataset** đã được ghi nhận từ run trước, không phải model bịa.
- Không có ca nào có `number_violation` ở nhóm âm (0,0).

**Kết luận RAG:** chất lượng trích dẫn cải thiện, nhưng cần (a) yêu cầu trả lời ngắn gọn
hơn để giảm latency, (b) sửa các lỗi nội dung QA-009/QA-033/QA-044, (c) rà lại nhãn
QA-020/QA-049 và marker từ chối.

---

## 7. PageMatch

49 ca, **0 lỗi**. `verify_unavailable_rate` **0,0408** (2 ca), `full_page_mode_rate`
**0,102** (5/49), `truncated_rate` **0,2245** (11/49 — toàn bộ TXT).

### 7.1 Chất lượng — segments (không warning, top-5)

| Dương tính | Hit | Exact | Precision@5 | Recall@5 | F1@5 | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 | **0,5938** | 0,5938 | **0,2479** | 0,5938 | 0,3167 | 0,1872 | **0,6306** | 0,1852 | 10 | **0,3000** | 8.300 ms |

### 7.2 Chất lượng — full-page

| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 4 | **0,5000** | 0,7251 | **0,5427** | 1 | 1,0 |

Độ trễ toàn module: p50 **6.111,7 ms**, p95 **18.287,0 ms**.

### 7.3 Toàn bộ item và nhóm `verified`

| Dương tính | `hit_all` | `hit5_page` | `hit5_score` | Precision all | Coverage all | Verified recall | Verified precision (macro/micro) | Âm tính | FPR any / verified FPR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | **0,6579** (25/38) | 0,5789 | 0,5789 | 0,2445 | 0,6944 | **0,6316** (24/38) | 0,2438 / 0,1412 | 11 | **0,3636 / 0,3636** |

### 7.4 Tách theo nhóm nguồn

| Nhóm | Dương tính | `hit_all` | `verified_recall` | Âm tính | FPR any |
|---|---:|---:|---:|---:|---:|
| HTML | 22 | 0,6818 | 0,6364 | 9 | 0,3333 |
| TXT | 16 | 0,6250 | 0,6250 | 2 | 0,5000 |

### 7.5 Vì sao `hit_all` giảm?

So theo từng ca với run trước: **5 ca mất hit** (QA-009, QA-022, QA-035, QA-037,
QA-041), **1 ca được thêm** (QA-038). Đồng thời cơ cấu thay đổi:

- Full-page rate giảm **18,37% → 10,20%**, nên số ca full-page dương tính chỉ còn 4
  (trước 8) — full-page thường dễ hit hơn segments.
- Hai ca bị ảnh hưởng bởi `VERIFY_UNAVAILABLE`: QA-009 mất `hit_all`, QA-028 mất
  `verified` — tức bước thẩm định không chạy, không hẳn do model chọn sai.
- Nhóm segments không warning lại **tăng nhẹ** (hit 0,5714 → 0,5938), cho thấy ở các ca
  so sánh được, chất lượng block không xấu đi rõ rệt.

**Đọc:** PageMatch của cấu hình mới **không sụp**, nhưng `verified_recall` 0,63 và
`verified_precision` 0,24 vẫn rất thấp so với mục tiêu 0,85 trong tài liệu PageMatch.
Vấn đề nằm ở prompt/định nghĩa "verified" và ngưỡng candidate, không phải ở embedding
(embedding không đổi so với run trước).

---

## 8. Đối chiếu A/B — chỉ đổi model chat

Hai run cùng dataset `ef7c82ca643482ab`, cùng embedding `Qwen3-Embedding-0.6B`, cùng
`top_k`/`max_sources`/flags; biến số duy nhất là **chat model**:

- Run trước: `Ternary-Bonsai-2-9B` (nhãn `local-qwenternary-qwen3embed`)
- Run này: `Qwen3.5-4B-Q4_K_S` (nhãn `local-qwen3.5_4b-qwen3embed`)

| Chỉ số | Ternary-Bonsai-9B | **Qwen3.5-4B** | Δ |
|---|---:|---:|---:|
| Search Recall@5 | 0,9737 | 0,9737 | 0 |
| Search MRR | 0,9342 | 0,9342 | 0 |
| Search p50 / p95 | 110,1 / 152,6 ms | 114,95 / 185,14 ms | +4,4% / +21,3% |
| RAG trích dẫn hợp lệ | 0,8421 | **0,9211** | **+7,9 điểm %** |
| RAG Token-F1 gold | 0,1770 | 0,1638 | −0,0132 |
| RAG từ chối đúng (heuristic) | 0,8182 | 0,6364 | −0,1818 |
| RAG total p50 / p95 | 2.645 / 6.853 ms | 4.953 / 9.395 ms | **+87,2% / +37,1%** |
| RAG token TB | 1.121,7 | 1.209,7 | +7,8% |
| PageMatch `hit_all` | 0,7632 | 0,6579 | −0,1053 |
| PageMatch `verified_recall` | 0,6842 | 0,6316 | −0,0526 |
| PageMatch FPR any / verified | 0,5455 / 0,4545 | **0,3636 / 0,3636** | **−0,1818 / −0,0909** |
| PageMatch segments hit | 0,5714 | **0,5938** | +0,0224 |
| PageMatch full-page rate | 18,37% | 10,20% | −8,17 điểm % |
| PageMatch p50 / p95 | 9.908 / 21.807 ms | **6.112 / 18.287 ms** | **−38,3% / −16,1%** |
| Token tiêu thụ | 561.371 | 562.444 | +0,19% |

### Cách đọc A/B

1. **Search là hằng số** vì embedding không đổi — xác nhận pipeline ổn định.
2. **RAG tốt hơn ở trích dẫn nhưng đắt hơn ở thời gian.** Tốc độ sinh chữ xấp xỉ nhau
   (~150 ký tự/giây); câu trả lời của 4B dài hơn ~45% nên tổng thời gian tăng gần gấp đôi.
   Nếu latency là ưu tiên, cần prompt "trả lời ngắn" hoặc giới hạn độ dài đầu ra, không
   nhất thiết đổi model.
3. **Từ chối: metric giảm nhưng đọc tay không xấu đi.** 2 ca heuristic bỏ sót là từ chối
   thật; 2 ca còn lại là tranh chấp nhãn. Không có bằng chứng bịa số ở nhóm âm.
4. **PageMatch là đánh đổi:** ít full-page hơn, FPR thấp hơn, segments nhỉnh hơn, nhưng
   recall tổng thấp hơn. Nếu UI ưu tiên "không gợi ý sai", 4B có thể chấp nhận được; nếu
   ưu tiên "không bỏ sót đoạn đúng", cần tune lại prompt/verified.

---

## 9. Hạn chế & khuyến nghị

**Hạn chế phép đo (giữ nguyên từ harness):**

- Token-F1 là trùng từ với gold — metric phụ, không phản ánh đúng ngữ nghĩa.
- Trích dẫn chỉ kiểm tra `[n]` nằm trong số nguồn + có ít nhất một trích dẫn; **chưa kiểm
  chứng nguồn có thực sự hỗ trợ ý**.
- "Số ngoài ngữ cảnh" là proxy chuỗi; QA-040 cần đối chiếu tay.
- Từ chối là heuristic marker ở câu đầu; QA-006/QA-024 cho thấy còn âm tính giả.
- PageMatch FPR đo "có trả block", không đo "có khẳng định đáp án".
- Dataset 11 tài liệu ⇒ sàn ngẫu nhiên 0,4545; Recall@5 cao cần đọc kèm sàn.
- Độ trễ là end-to-end HTTP (gồm provider), chưa tách thời gian DB thuần.

**Khuyến nghị ưu tiên:**

1. **Giữ `Qwen3-Embedding-0.6B` cho search/RAG** — retrieval lặp lại chính xác, không có
   lý do đổi.
2. **Thêm ràng buộc độ dài câu trả lời** (prompt hoặc `max_tokens`) nếu dùng Qwen3.5-4B:
   mục tiêu giảm 30–40% độ dài mà vẫn giữ trích dẫn; đo lại p50/p95.
3. **Sửa lỗi nội dung RAG:** QA-033 (WMT 2014), QA-009 (năm), QA-044 (Microsoft); kiểm tra
   lại chunk/ngữ cảnh đưa vào cho các ca này.
4. **Rà nhãn dataset:** QA-020 và QA-049 nên được xem lại; nếu đổi nhãn, refusal rate sẽ
   phản ánh đúng hơn.
5. **Tune PageMatch riêng:** prompt "verified", ngưỡng `page_match_min_score`, số candidate;
   đo lại `verified_recall`/`verified_precision` trước khi kết luận model nào tốt hơn.
6. **Xử lý QA-038 (search rỗng)** và bổ sung `reference_answer`/corpus để metric retrieval
   có ý nghĩa thống kê hơn.

---

## 10. Tái lập & artifact

```bash
cd steady_evaluation
python3 run_evaluation.py \
  --model-label "local-qwen3.5_4b-qwen3embed" \
  --provider openai --model chat --embedding-model "Qwen3-Embedding-0.6B-Q8_0" \
  --tag lat3-full-local \
  --fresh-notes --cleanup-notes

python3 run_evaluation.py --recompute 20261121_043458_145357_local-qwen3-5-4b-qwen3embed_lat3-full-local
python3 run_evaluation.py --compare
```

Artifact trong `steady_evaluation/runs/20261121_043458_145357_local-qwen3-5-4b-qwen3embed_lat3-full-local/`:

| File | Nội dung |
|---|---|
| `run_manifest.json` | cấu hình, model, dataset, fingerprint, `eval_code_sha256`, git commit, folder |
| `raw_results.jsonl` | 147 case thô (11 ingest + 38 search + 49 RAG + 49 PageMatch) |
| `metrics.json` | chỉ số tổng hợp + quota before/after + token |
| `metrics.recomputed.json` | tái tạo từ raw — **diff khớp hoàn toàn** |
| `report.md` | báo cáo do pipeline sinh |

Bảng so sánh 5 run cùng nhóm chất lượng: `steady_evaluation/runs/MODEL_COMPARISON.md`.
