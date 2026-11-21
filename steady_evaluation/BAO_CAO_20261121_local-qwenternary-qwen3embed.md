# Báo cáo đánh giá `steady_evaluation` — nhãn `local-qwenternary-qwen3embed`

**Run:** `20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local`
**Thời gian:** 2026-11-21 10:02:33 → 10:15:49 (GMT+7) · **13 phút 16 giây**
**Nhãn model (do người chạy đặt):** `local-qwenternary-qwen3embed`
**Trạng thái:** hoàn tất 3 module · **0 lỗi case** · `--recompute` khớp hoàn toàn

> Báo cáo đọc từ artifact thật của run. Số tổng hợp lấy từ `metrics.json`; các bảng tách
> HTML/TXT và phần đối chiếu refusal được tính lại từ `raw_results.jsonl` bằng chính hàm
> chấm của `steady_metrics.py`. `runs/MODEL_COMPARISON.md` đã cập nhật bằng `--compare`.

---

## 0. Kết luận điều hành

1. **Đây là phép A/B sạch cho embedding:** so với run `20261121_023251` (nhãn `local-qwenternary-qwenqte`),
   **dataset, harness (`eval_code_sha256`), cờ chạy và model chat đều giữ nguyên**; biến số duy nhất
   là embedding đổi từ `gte-Qwen2-1.5B-instruct` sang **`Qwen3-Embedding-0.6B-Q8_0`**.
2. **Truy hồi cải thiện rất mạnh:** Recall@5 **0,7105 → 0,9737** (+26,3 điểm %), MRR
   **0,6798 → 0,9342**, Recall part **0,7105 → 0,8947**. Nhóm TXT từ **5/16 lên 15/16**.
3. **RAG hưởng lợi:** trích dẫn hợp lệ **0,7368 → 0,8421** (+10,5 điểm %); Token-F1 gold
   **0,1629 → 0,1770**; độ trễ tổng p50 **3.332 → 2.645 ms** (−20,6%); token tiêu thụ **−4,7%**.
4. **PageMatch lại giảm:** segments hit **0,7895 → 0,5714**, Precision@5 **0,2754 → 0,1696**,
   Span Coverage **0,7952 → 0,6304**. Cùng một embedding nuôi cả `/search` và `/ai/page-match`,
   nên đây là **đánh đổi cần xử lý riêng cho PageMatch**, không phải nhiễu.
   → **Đính chính (M0):** các số này dùng định nghĩa cũ (5 item đầu theo thứ tự trang) và so
   hai cohort khác nhau. Số đo lại trên toàn bộ item/`verified` ở **§8A**: mức giảm thật khoảng
   **−0,08**, không phải −0,22.
5. **Ingest và vận hành ổn định:** 11/11 `READY`, 25 part, index **316.032/316.032 ký tự (100%)**;
   embedding mới trả **1.024 chiều** và được backend **zero-pad lên 1.536** đúng thiết kế
   (cosine không đổi) — đã kiểm chứng bằng ingest thật, không có lỗi chiều vector.
6. **Chất lượng câu trả lời:** 0 lỗi case; từ chối đúng 9/11 theo heuristic và **không còn ca
   từ chối nào bị bỏ sót** (QA-006 lần này từ chối rõ). 2 ca bị tính “trả lời bừa” là QA-020
   (trả lời có nội dung liên quan lấy từ nguồn — **nhãn dataset cần rà lại**) và QA-031
   (nêu tội danh nhưng thiếu mức án), không ca nào bịa số. 1 ca search trả rỗng (QA-038)
   kéo theo 1 ca RAG không có nguồn.

---

## 1. Điều kiện chạy — đã kiểm tra

| Điều kiện | Cách kiểm tra | Kết quả |
|---|---|---|
| Backend sống | `GET /health/live` | `200 {"status":"ok"}` |
| DB sẵn sàng | `GET /health/ready` | `{"status":"ok","db":"ok"}` |
| Worker | `ps` | `python -m quickassist.worker` đang chạy |
| Model server | `GET :8080/v1/models` | `chat`, `embed` |
| **Embedding mới** | `POST :8080/v1/embeddings` | **1.024 chiều**, alias `embed` |
| Xác thực | `POST /auth/dev-login` | `200` |
| Dataset | `run_evaluation.py --validate` | 49 cặp, 0 dòng loại, exit 0 |
| Tái lập | `run_evaluation.py --recompute` | ✓ khớp hoàn toàn |

### Chiều vector — điểm cần kiểm tra của embedding mới

Backend lưu vector cố định **1.536 chiều** (`note_chunks.embedding`). Với provider BYOK,
`CanonicalEmbeddingProvider` **zero-pad** vector ngắn hơn lên 1.536 chiều; phép pad **không đổi
cosine** vì `cos([q,0],[v,0]) = cos(q,v)`. `Qwen3-Embedding-0.6B` trả 1.024 chiều → được pad
lên 1.536. Ingest thật đã xác nhận đường này hoạt động: 11/11 file `READY`, 25/25 part `READY`,
không có lỗi `AI_PROVIDER_ERROR` về số chiều.

### Môi trường model thực tế

| Vai trò | Model | Cấu hình |
|---|---|---|
| Chat | `Ternary-Bonsai-2-9B-PQ2_0-MTP-Q8_0.gguf` (alias `chat`) — **không đổi** | GPU 99 layer, ctx 8.192, `reasoning off`, cache-prompt/checkpoint tắt |
| **Embedding** | **`Qwen3-Embedding-0.6B-Q8_0.gguf`** (alias `embed`) | CPU, 6 thread, ctx 4.096, `pooling last`, KV `q8_0`, **1.024 chiều** |
| Backend | `uvicorn quickassist.main:app` :8000 | FastAPI + PostgreSQL/pgvector + worker |

> **Nhãn:** `local-qwenternary-qwen3embed` là metadata do người chạy đặt (đúng yêu cầu);
> model embedding thực tế đọc từ tiến trình llama-server là `Qwen3-Embedding-0.6B-Q8_0`.

---

## 2. Cấu hình run

| Thành phần | Giá trị |
|---|---|
| Lệnh | `run_evaluation.py --model-label local-qwenternary-qwen3embed --provider openai --model chat --embedding-model Qwen3-Embedding-0.6B-Q8_0 --tag lat3-full-local --fresh-notes --cleanup-notes` |
| Modules | `search, rag, pagematch` |
| `top_k` / `pagematch_top_k` / `max_sources` | 5 / 5 / 5 |
| `split_chars` | 20.000 (`--truncate-long` tắt → chia part, không cắt) |
| Folder | `run` (`d832b2da-…`), `--fresh-notes`, dọn note + folder sau khi chấm |
| Evidence type | `quality` |
| Dataset fingerprint | `ef7c82ca643482ab` (không đổi) |
| `eval_code_sha256` | `824b467cfefb0aad04036665542cdc1f3d5af9b1607fbed03d4713a2b6417688` (không đổi) |
| Git commit | `6d09ed9c3565787ac3c88933cd40273970409efc` |
| Python | 3.14.4 |
| Token tiêu thụ run này | **561.371** · quota user sau run: 1.150.324 / 1.000.000 (BYOK, **enforcement tắt**) |

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
| `create` p50 | 26,98 ms |
| Chờ index p50 / p95 | 3.018,77 ms / **40.279,39 ms** |

Chờ index p95 giảm so với run dùng `gte-Qwen2` (53,4 s → 40,3 s): embedding 0,6B nhẹ hơn,
cùng 25 part. Vẫn là chi phí một lần cho mỗi corpus, không nằm trên đường người dùng.

---

## 5. Tìm kiếm ngữ nghĩa (`POST /search`)

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | **0,9737** | 0,8947 | **0,9342** | 0,9737 | 0,8947 | **1,53** | 3 | 2,34 | 0,0263 | **110,1 ms** | **152,6 ms** |

Sàn ngẫu nhiên (top_k=5, 11 tài liệu): 0,4545. **Không ca nào chạm trần `max_sources`**
(0%, trước là 39,5%) — retrieval trả ít nguồn hơn nhưng chính xác hơn rõ rệt.

### Tách theo nhóm nguồn

| Nhóm | n | Recall@5 | MRR | Ca trượt top-5 |
|---|---:|---:|---:|---|
| HTML | 22 | **1,0000** | **0,9773** | 0 |
| TXT | 16 | **0,9375** (15/16) | **0,8750** | 1 (QA-038 — trả **rỗng**) |

**Đọc:** đây là thay đổi lớn nhất của run. Với `gte-Qwen2-1.5B`, nhóm TXT chỉ đạt 5/16; với
`Qwen3-Embedding-0.6B`, nhóm TXT đạt 15/16. Nút thắt truy hồi cross-lingual trên văn bản học
thuật tiếng Anh gần như được giải quyết. Ca duy nhất còn lại (QA-038) trả 0 nguồn — cần xem
ngưỡng similarity/`max_sources` cho trường hợp này; hệ quả kéo sang RAG (`no_source_rate` 2,63%).

---

## 6. RAG hỏi đáp (SSE thật)

### 6.1 Câu có căn cứ

| n | Hoàn thành | Lỗi | Token-F1 gold (phụ) | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | Token TB | first-event p50 | total p50 / p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | **0,1770** | **0,8421** (32/38) | 0,1579 (6/38) | **0,0263** (1/38) | **1.121,7** | 130,0 ms | **2.645,2** / 6.852,7 ms |

- `no_source_rate` = 0,0263 · `no_context_rate` = 0,0263 · ngữ cảnh TB **25.257 ký tự**.

| Nhóm | n | Trích dẫn hợp lệ | Không trích dẫn | Token-F1 gold |
|---|---:|---:|---:|---:|
| HTML | 22 | **19/22 = 0,8636** | 3/22 | 0,2664 |
| TXT | 16 | **13/16 = 0,8125** | 3/16 | 0,0541 |

6 ca không trích dẫn: QA-014, QA-027, QA-029 (HTML) và QA-038, QA-039, QA-041 (TXT). Trong đó
QA-038 là ca search rỗng; các ca còn lại trả lời thiếu trích dẫn dù có nguồn.

**Số ngoài ngữ cảnh:** 1/38 (QA-040, câu “LoRA giảm 10.000 lần tham số”). Đây là **proxy chuỗi**;
con số này có trong bài báo nguồn nhưng có thể bị lệch định dạng (`10,000` / `10.000`), nên cần
đối chiếu tay trước khi kết luận là bịa.

### 6.2 Câu không đủ căn cứ

| n | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | **0,8182** (9/11) | 0,1818 (2/11) | 0,0 |

- **QA-006** (từng bị heuristic bỏ sót ở run trước) lần này từ chối rõ: *“Dựa trên các nguồn
  thông tin được cung cấp, không có thông tin giải thích lý do…”* → **heuristic không còn âm
  tính giả** ở ca này.
- 2 ca bị tính “trả lời bừa”:
  - **QA-020** (“Thông tin mới nhất về dự án vũ trụ Dyson Sphere?”): model trả lời chi tiết
    tài trợ 530.000 USD, chương trình 75 triệu USD, 6 giải pháp… **lấy từ nguồn**, rồi bổ sung
    phần còn thiếu. Nội dung này có căn cứ, nhưng dataset lại gắn nhãn `answerable=no` →
    nhiều khả năng **nhãn dataset cần rà lại**, không phải model bịa.
  - **QA-031** (“Bản án toà tuyên cho ông Thản…”): nêu tội danh và thiệt hại nhưng **không
    nêu mức án** → trả lời thiếu, không từ chối.
- **Không có số ngoài ngữ cảnh ở nhóm âm** (0,0).

---

## 7. PageMatch

49 ca, **0 lỗi**. `verify_unavailable_rate` **0,102** (5 ca), `full_page_mode_rate` **0,1837**
(9/49, trước là 49%), `truncated_rate` **0,2245** (11/49 — toàn bộ TXT).

### 7.1 Chất lượng — segments (không warning, top-5)

| Dương tính | Hit | Exact | Precision@5 | Recall@5 | F1@5 | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 28 | **0,5714** | 0,5714 | **0,1696** | 0,5714 | 0,2488 | 0,1429 | **0,6304** | 0,1799 | 8 | **0,5000** | 10.529 ms |

### 7.2 Chất lượng — full-page

| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 7 | **0,4286** | 0,5959 | **0,6362** | 1 | 1,0 |

Độ trễ toàn module: p50 **9.907,5 ms**, p95 **21.807,5 ms**.

### 7.3 Tách theo nhóm nguồn

| Nhóm | Chế độ | Dương tính | Hit | Precision@5 | Span Coverage | Âm tính | FPR |
|---|---|---:|---:|---:|---:|---:|---:|
| HTML | segments | 18 | 0,611 | 0,194 | 0,659 | 7 | 0,57 |
| HTML | full-page | 2 | 1,000 | 0,200 | 1,000 | 0 | — |
| TXT | segments | 10 | 0,500 | 0,127 | 0,579 | 1 | 0,00 |
| TXT | full-page | 5 | 0,200 | 0,080 | 0,434 | 1 | 1,00 |

### 7.4 Fallback (`VERIFY_UNAVAILABLE`)

5 ca (trước 2): 2 dương tính — hit 1,0, Precision@5 0,375, Coverage 1,0; 2 âm tính — FPR 0,5.
Chỉ báo hành vi, không gộp vào chất lượng chính.

**Đọc:** PageMatch dùng **cùng embedding** để chọn block ứng viên (embed query + embed block →
cosine → lọc `min_score` → LLM thẩm định). Việc `Qwen3-Embedding-0.6B` trả ít nguồn hơn và
mạnh hơn ở mức tài liệu lại đi kèm **giảm hit ở mức block**. Hai giả thuyết cần kiểm chứng:
(1) ngưỡng `page_match_min_score` / số candidate chưa được chỉnh cho phân bố cosine mới;
(2) `Qwen3-Embedding` được huấn luyện **instruction-aware** (query nên có tiền tố hướng dẫn),
trong khi harness gửi query thô — ảnh hưởng mạnh hơn ở truy vấn ngắn so với block dài.
Đồng thời `full_page_mode_rate` giảm mạnh (49% → 18%) nên thành phần ca được chấm cũng đổi
(segments 19 → 28 dương tính), cần đọc Hit kèm cơ cấu này.

---

## 8. Đối chiếu A/B — chỉ đổi embedding

Hai run cùng dataset `ef7c82ca643482ab`, cùng `eval_code_sha256 824b467`, cùng cờ chạy, cùng
model chat `Ternary-Bonsai-2-9B`, ctx 8.192:

| Chỉ số | `gte-Qwen2-1.5B` (run 023251) | **`Qwen3-Embedding-0.6B` (run này)** | Δ |
|---|---:|---:|---:|
| Search Recall@5 | 0,7105 | **0,9737** | **+0,2632** |
| Search Recall part | 0,7105 | **0,8947** | +0,1842 |
| Search MRR | 0,6798 | **0,9342** | **+0,2544** |
| Search `sources_avg` | 3,68 | **1,53** | −2,15 |
| Search `notes_returned_avg` | 4,08 | **2,34** | −1,74 |
| Search rỗng | 0,0 | 0,0263 | +1 ca |
| Search p50 / p95 | 194,4 / 269,0 ms | **110,1 / 152,6 ms** | ≈ −43% |
| RAG trích dẫn hợp lệ | 0,7368 | **0,8421** | **+0,1053** |
| RAG Token-F1 gold | 0,1629 | **0,1770** | +0,0141 |
| RAG từ chối đúng (heuristic) | 0,8182 | 0,8182 | 0 |
| RAG total p50 | 3.332,3 ms | **2.645,2 ms** | **−20,6%** |
| Token tiêu thụ | 588.953 | **561.371** | −4,7% |
| PageMatch segments Hit | 0,7895 | **0,5714** | **−0,2181** |
| PageMatch segments P@5 | 0,2754 | 0,1696 | −0,1058 |
| PageMatch segments Coverage | 0,7952 | 0,6304 | −0,1648 |
| PageMatch full-page rate | 0,4898 | **0,1837** | −0,3061 |
| PageMatch p50 | 10.781 ms | **9.908 ms** | −8,1% |
| `verify_unavailable_rate` | 0,0408 | 0,102 | +5 ca |

**Kết luận A/B:** đổi sang `Qwen3-Embedding-0.6B` là **thắng lớn cho search + RAG**
(chính xác hơn, nhanh hơn, ít token hơn) nhưng **thua cho PageMatch ở mức block**. Không nên
kết luận “embedding mới tốt hơn toàn diện”; cần cấu hình lại PageMatch (ngưỡng, số candidate,
tiền tố query theo khuyến nghị của Qwen3) trước khi dùng chung một model cho cả hai đường.

> **Đính chính (M0 — 2026-11-21):** các dòng PageMatch trong bảng trên dùng định nghĩa cũ
> `Hit@5` = 5 item đầu **theo thứ tự trang**, không phải top-5 theo score. Đọc §8A để có số
> đo lại trên toàn bộ item và nhóm `verified` — mức giảm thật khoảng **−0,08**, không phải
> −0,22. Các kết luận search/RAG ở trên không đổi.

---

## 8A. Đính chính metric PageMatch (M0 — 2026-11-21)

> **Bổ sung, không xoá kết luận cũ.** Các bảng ở §7 và §8 vẫn đúng theo **định nghĩa cũ**
> (`Hit@5` = 5 item đầu theo thứ tự trang). Mục này thay thế cách diễn giải “PageMatch giảm
> 0,22” bằng chỉ số khớp với trải nghiệm UI.

### 8A.1. Vì sao phải đính chính

- Metric cũ `_score_pagematch_case` lấy `items[:top_k]` — tức **5 đoạn đầu theo thứ tự trang**,
  không phải 5 đoạn tốt nhất theo `score`. Server trả `items` theo thứ tự trang.
- UI hiển thị **tất cả** item và auto-select các đoạn `verified=true`. Vì vậy `Hit@5` cũ
  không đo “5 kết quả tốt nhất”, cũng không đo “toàn bộ kết quả người dùng thấy”.
- Khi `full_page_mode_rate` giảm 49% → 18%, tập ca `segments` đổi từ 19 lên 28 ca dương.
  So `0,7895` với `0,5714` là so **hai cohort khác nhau**, không phải cùng một tập.

### 8A.2. Số đo lại trên cùng 38 ca dương / 11 ca âm

Bảng dưới tính bằng `steady_metrics.py` phiên bản `metrics_version = 4`; cột Qwen3 lấy từ
`metrics.recomputed.json` của run này, cột gte là số tham chiếu cùng định nghĩa trên run
`20261121_023251`.

| Chỉ số | gte-Qwen2 | Qwen3-Embed | Δ thật |
|---|---:|---:|---:|
| Gold nằm trong **bất kỳ item** (`hit_all`) | 30/38 = **0,7895** | 29/38 = **0,7632** | **−0,0263** |
| Gold nằm trong item **verified** (`verified_recall`) | 29/38 = **0,7632** | 26/38 = **0,6842** | **−0,0789** |
| Verified FPR (11 ca âm) | 7/11 = **0,6364** | 5/11 = **0,4545** | **−0,1818** |
| FPR bất kỳ item | 8/11 = 0,7273 | 6/11 = 0,5455 | −0,1818 |
| `precision_all` | 0,1710 | 0,1626 | −0,0084 |
| `coverage_all` | 0,8260 | 0,7964 | −0,0296 |
| Verified precision (macro) | 0,1882 | 0,1555 | −0,0327 |
| Verified precision (micro) | 0,1068 | 0,1015 | −0,0053 |
| HTML — `hit_all` | 20/22 = 0,9091 | 17/22 = 0,7727 | −0,1364 |
| TXT — `hit_all` | 10/16 = 0,6250 | 12/16 = 0,7500 | **+0,1250** |
| Full-page rate (49 ca) | 48,98% | 18,37% | −30,61 pp |
| `hit5_page` (metric cũ) | 25/38 = 0,6579 | 22/38 = 0,5789 | −0,0789 |
| `hit5_score` (top-5 theo score) | 24/38 = 0,6316 | 24/38 = 0,6316 | 0 |
| `verify_unavailable` | 2 ca | 5 ca | +3 |

### 8A.3. Kết luận thay thế

1. **Qwen3 không “sụp” PageMatch.** Mức giảm thật ở recall của các đoạn được auto-select là
   khoảng **−0,08**, không phải −0,22. Con số −0,2181 ở §0.4/§8 là do so hai cohort khác nhau
   dưới định nghĩa top-5 theo thứ tự trang.
2. **Cấu trúc thay đổi, không phải mất năng lực:** TXT tốt hơn rõ (`hit_all` +0,1250), HTML
   kém hơn (−0,1364), ít full-page hơn, ít false positive hơn (`verified_fpr` −0,1818).
3. **`hit5_score` giống hệt nhau (0,6316)** → vấn đề không nằm ở xếp hạng top-5 theo score.
4. **Verified precision của cả hai run chỉ 0,10–0,19**, rất xa mục tiêu 0,85 trong
   `docs/ai/page-match-eval.md`. Đây là vấn đề định nghĩa “đúng”/prompt thẩm định, không phải
   chỉnh ngưỡng là giải quyết được.
5. **Hệ quả:** phải sửa metric trước khi tune (đã làm ở M0). Nếu tune trên metric cũ, UI sẽ
   tối ưu một chỉ số không khớp với trải nghiệm thật.

### 8A.4. Thay đổi kỹ thuật

- `steady_metrics.py`: thêm nhóm `pagematch.overall` với `hit_all`, `hit5_page`,
  `hit5_score`, `precision_all`, `coverage_all`, `span_precision_all`,
  `verified_recall`, `verified_precision_macro`, `verified_precision_micro`,
  `fpr_any`, `verified_fpr`; giữ nguyên mọi khóa cũ.
- `metrics_version` 3 → **4**; `--recompute` vẫn khớp hoàn toàn với metrics cũ (chỉ bỏ qua
  trường `metrics_version` khi diff).
- `report.md` của run này đã render thêm bảng “toàn bộ item / verified”;
  `runs/MODEL_COMPARISON.md` dùng `PM Hit@all`, `PM vRecall`, `PM vFPR` làm cột chính.
- Không sửa `raw_results.jsonl`.

---

## 9. Hạn chế & khuyến nghị

**Hạn chế phép đo (giữ nguyên từ harness):**

- Token-F1 là trùng từ với gold — metric phụ, không phản ánh đúng ngữ nghĩa.
- Trích dẫn chỉ kiểm tra `[n]` nằm trong số nguồn + có ít nhất một trích dẫn; **chưa kiểm chứng
  nguồn có thực sự hỗ trợ ý**.
- “Số ngoài ngữ cảnh” là proxy chuỗi (1 ca QA-040 cần đối chiếu tay).
- Từ chối là heuristic marker ở câu đầu; run này không còn âm tính giả rõ ràng, nhưng QA-020 và
  QA-031 vẫn có thể gây tranh cãi khi gắn nhãn “trả lời bừa”.
- PageMatch FPR đo “có trả block”, không đo “có khẳng định đáp án”.
- Dataset 11 tài liệu ⇒ sàn ngẫu nhiên 0,4545; Recall@5 cao cần đọc kèm sàn.
- Độ trễ là end-to-end HTTP (gồm provider), chưa tách thời gian DB thuần.
- Quota BYOK đã vượt 1.000.000 token nhưng **enforcement tắt**; không ảnh hưởng run.

**Khuyến nghị ưu tiên:**

1. **Chốt `Qwen3-Embedding-0.6B` cho `/search` + RAG** — mức cải thiện lớn và nhất quán trên
   cả HTML lẫn TXT, kèm giảm latency và token.
2. **Tinh chỉnh PageMatch riêng:** hạ/nâng `page_match_min_score`, tăng `page_match_top_candidates`,
   và thử **query instruction prefix** theo khuyến nghị Qwen3-Embedding; đo lại Hit/Precision
   trước khi kết luận. Nếu không đủ, cân nhắc embedding riêng cho PageMatch.
3. **Xử lý QA-038 (search rỗng):** kiểm tra ngưỡng similarity với câu hỏi ngắn trên tài liệu TXT;
   hiện 1/38 ca rỗng làm giảm Recall@5 và tạo 1 ca RAG không nguồn.
4. **Kiểm chứng QA-040** (10.000 lần) để phân biệt lỗi định dạng số với bịa thật.
5. **Bổ sung `reference_answer`** và tăng corpus/câu nhiễu để Recall@5 có ý nghĩa thống kê hơn.

---

## 10. Tái lập & artifact

```bash
cd steady_evaluation
python3 run_evaluation.py \
  --model-label "local-qwenternary-qwen3embed" \
  --provider openai --model chat --embedding-model "Qwen3-Embedding-0.6B-Q8_0" \
  --tag lat3-full-local \
  --fresh-notes --cleanup-notes

python3 run_evaluation.py --recompute 20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local
python3 run_evaluation.py --compare
```

Artifact trong `steady_evaluation/runs/20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local/`:

| File | Nội dung |
|---|---|
| `run_manifest.json` | cấu hình, model, dataset, fingerprint, `eval_code_sha256`, git commit, folder |
| `raw_results.jsonl` | 147 case thô (11 ingest + 38 search + 49 RAG + 49 PageMatch) |
| `metrics.json` | chỉ số tổng hợp, quota before/after, token |
| `metrics.recomputed.json` | tái tạo từ raw — **diff khớp hoàn toàn** |
| `report.md` | báo cáo do pipeline sinh |

Bảng so sánh 4 run cùng nhóm chất lượng: `steady_evaluation/runs/MODEL_COMPARISON.md`.
