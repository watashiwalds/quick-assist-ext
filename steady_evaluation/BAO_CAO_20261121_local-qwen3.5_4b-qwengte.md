# Báo cáo đánh giá `steady_evaluation` — nhãn `local-qwen3.5_4b-qwengte`

**Run:** `20261121_050139_470458_local-qwen3-5-4b-qwengte_lat3-full-local`
**Thời gian:** 2026-11-21 12:01:39 → 12:17:13 (GMT+7) · **15 phút 34 giây**
**Nhãn model (do người chạy đặt):** `local-qwen3.5_4b-qwengte`
**Trạng thái:** hoàn tất 3 module · **0 lỗi case** · `--recompute` khớp hoàn toàn

> Báo cáo đọc từ artifact thật của run. Số tổng hợp lấy từ `metrics.json`; các bảng tách
> nhóm nguồn, đối chiếu refusal/số ngoài ngữ cảnh và PageMatch từng ca được tính lại từ
> `raw_results.jsonl` bằng chính hàm chấm của `steady_metrics.py` (metrics v4). Lần chạy
> này **chỉ đổi embedding** (Qwen3-Embedding-0.6B → gte-Qwen2-1.5B-instruct), chat model
> giữ nguyên Qwen3.5-4B — nên khác biệt so với run `local-qwen3.5_4b-qwen3embed` là A/B
> sạch trên embedding.

---

## 0. Kết luận điều hành

1. **Hạ tầng và ingest ổn định:** 11/11 tài liệu `READY`, 25/25 part `READY`, index đủ
   **316.032/316.032 ký tự (100%)**, không cắt file. Chi phí chờ index tăng (p50
   **2.014 → 3.020 ms**, p95 40.275 → 53.363 ms) — hệ quả trực tiếp của embedding model
   lớn gấp 2,5 lần chạy trên CPU; chỉ phát sinh một lần cho mỗi corpus.
2. **Search tụt mạnh và tụt có quy luật: Recall@5 0,9737 → 0,7105 (−26,3 điểm %),
   MRR 0,9342 → 0,6798.** Toàn bộ **10 ca mất hit đều ở nhóm TXT** (3 tài liệu học thuật
   tiếng Anh: Attention Is All You Need, LoRA, Evaluating Quantized LLM): TXT rơi từ
   **15/16 xuống 5/16**, còn nhóm HTML tiếng Việt **giữ nguyên 22/22**. Không phải nhiễu
   ngẫu nhiên — retrieval tất định theo embedding (mục 5.2).
3. **gte-Qwen2-1.5B kém hơn hẳn Qwen3-Embedding-0.6B trên corpus này** dù tham số lớn
   hơn. Số liệu retrieval của run này **trùng từng con số** với hai run cũ dùng dòng
   GTE-Qwen2 (R@k 0,7105 · MRR 0,6798) — chất lượng retrieval do **embedding quyết định**,
   không phụ thuộc chat model.
4. **RAG: trích dẫn giảm theo retrieval, nhưng không phải model bịa.** Trích dẫn hợp lệ
   **0,9211 → 0,7895**; cả **8 ca không trích dẫn** đều là dạng "Ghi chú của bạn chưa có
   thông tin…" — hậu quả trực tiếp của việc search trả **sai nguồn** (ví dụ hỏi LoRA
   nhưng ngữ cảnh là "tấm chắn Mặt Trời"). Token-F1 0,1638 → 0,1493.
5. **Điểm sáng: hai lỗi nội dung của run trước đã biến mất.** QA-033 nay trả đúng
   **WMT 2014 (BLEU 28,4 / 41,8)** thay vì WSJ/40.000; QA-009 hết nêu "năm 2024". Đổi lại
   QA-044 (gold "Microsoft Corporation") giờ **từ chối luôn** vì search không còn trả đúng
   nguồn — chưa giải quyết, chỉ đổi dạng lỗi.
6. **Proxy "số ngoài ngữ cảnh" run này hầu hết là dương tính giả:** QA-015 viết "4 kiến
   tạo" trong khi nguồn viết bằng chữ "bốn kiến tạo"; QA-011 nêu "28,2 triệu/m²" là quy
   đổi từ 282.000 đồng/m² có trong nguồn và "2022" suy ra từ "ba năm trước"; QA-008 nêu
   "(ID 2, 3, 4)" là đánh số nguồn. Riêng QA-010 là sai số nhỏ có thật ("gần 5.200 căn"
   trong khi nguồn ghi **5.158**).
7. **Từ chối trên nhóm không căn cứ tốt:** heuristic báo **9/11 (0,8182)** — cao nhất
   trong các run gần đây; đọc tay cả 11 ca đều có dấu hiệu từ chối hoặc thuộc nhóm tranh
   chấp nhãn dataset (QA-049 tiếp tục trả lời có căn cứ từ nguồn dù gắn nhãn `no`).
8. **PageMatch: hit nhích lên nhưng FPR xấu đi rõ rệt và chậm hơn.** `hit_all`
   **0,6579 → 0,6842** (26/38), `verified_recall` **0,6316 → 0,6579**, nhưng FPR
   **0,3636 → 0,6364** (7/11 ca âm trả về item) và `full_page_mode_rate` tăng
   **0,102 → 0,2449** (5 → 12 ca, chủ yếu HTML VnExpress chuyển segments → full_page);
   p50 **6.112 → 10.456 ms (+71%)**.
9. **Token tiêu thụ 586.791 (+4,3%)** so với 562.444. Quota BYOK đã vượt 1.000.000 từ
   trước (2.299.559) nhưng **enforcement tắt**, không ảnh hưởng run.

---

## 1. Điều kiện chạy — đã kiểm tra trước khi run

| Điều kiện | Cách kiểm tra | Kết quả |
|---|---|---|
| Backend sống | `GET /health/live` | `200 {"status":"ok"}` |
| DB sẵn sàng | `GET /health/ready` | `{"status":"ok","db":"ok"}` |
| Worker | `ps` | `python -m quickassist.worker` đang chạy |
| Model server | `GET :8080/v1/models` | `chat`, `embed` (router llama-server) |
| Embedding mới | `POST :8080/v1/embeddings` (`dimensions:1536`) | **1.536 chiều** — khớp hợp đồng `vector(1536)` của DB, không cần đụng migration |
| Xác thực | dev-login | OK |
| Dataset | `run_evaluation.py --validate` | 49 cặp, 0 dòng loại, exit 0 |
| Tái lập | `run_evaluation.py --recompute` | ✓ khớp hoàn toàn |

### Môi trường model thực tế

| Vai trò | Model | Cấu hình |
|---|---|---|
| Chat | `Qwen_Qwen3.5-4B-Q4_K_S.gguf` (alias `chat`) | 4,33B tham số · Q4_K_S · GPU 99 layer · ctx 8.192 · `reasoning off` |
| Embedding | `gte-Qwen2-1.5B-instruct-Q4_K_M.gguf` (alias `embed`) | **mới** · 1,5B · Q4_K_M · CPU 6 thread · ctx 4.096 · **1.536 chiều** · `pooling last` |
| Backend | `uvicorn quickassist.main:app` :8000 | FastAPI + PostgreSQL/pgvector + worker |

> **Nhãn:** `local-qwen3.5_4b-qwengte` do người chạy đặt, khớp cặp model đang chạy
> (`qwengte` = gte-Qwen2). `run_id` sanitize dấu chấm (`qwen3-5-4b`), manifest giữ nguyên
> `model_label`.

---

## 2. Cấu hình run

| Thành phần | Giá trị |
|---|---|
| Lệnh | `run_evaluation.py --model-label local-qwen3.5_4b-qwengte --provider openai --model chat --embedding-model gte-Qwen2-1.5B-instruct-Q4_K_M --tag lat3-full-local --fresh-notes --cleanup-notes` |
| Modules | `search, rag, pagematch` |
| `top_k` / `pagematch_top_k` / `max_sources` | 5 / 5 / 5 |
| `split_chars` | 20.000 (chia part, không cắt) |
| Folder | `run` (`a11bf531-…`), `--fresh-notes`, dọn note + folder sau khi chấm |
| Evidence type | `quality` |
| Dataset fingerprint | `ef7c82ca643482ab` (không đổi so với 2 run trước) |
| `eval_code_sha256` | `6808d78d…` (giống hệt run trước — cùng code chấm) |
| Git commit trong manifest | `46f5435` (commit sửa metric PageMatch — có trước khi run, sạch hơn run trước vốn dính commit giữa chừng) |
| Token tiêu thụ run này | **586.791** · quota sau run: 2.299.559 / 1.000.000 (BYOK, **enforcement tắt**) |

---

## 3. Dataset

Không đổi so với run trước (fingerprint trùng khớp):

| Chỉ số | Giá trị |
|---|---:|
| Nguồn | 11 (8 HTML + 3 TXT) |
| Cặp hỏi–đáp | 49 (38 answerable, 11 unanswerable) |
| Dòng bị loại | 0 |
| Độ dài văn bản | min 2.865 · median 5.964 · max 156.885 ký tự |

---

## 4. Ingest

| Chỉ số | Run này (gte) | Run trước (qwen3embed) |
|---|---:|---:|
| File READY | 11/11 (1,0) | 11/11 (1,0) |
| Tài liệu → part READY | 11 → 25/25 | 11 → 25/25 |
| Ký tự index | 316.032 (1,0) | 316.032 (1,0) |
| `create` p50 | 27,15 ms | 25,01 ms |
| Chờ index p50 / p95 | **3.019,69 / 53.363,06 ms** | 2.014,43 / 40.274,87 ms |

Chi phí chờ index **+50% (p50)** do embed model 1,5B (Q4_K_M) thay 0,6B (Q8_0) trên CPU.
Đây là chi phí một lần cho mỗi corpus, không nằm trên đường người dùng.

---

## 5. Tìm kiếm ngữ nghĩa (`POST /search`)

### 5.1 Tổng quan

| Queries | Hoàn thành | Recall@5 | MRR | AnswerHit | Nguồn TB | Note TB | Rỗng | p50 | p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | **0,7105** | **0,6798** | 0,7105 | **3,68** | 4,08 | **0,0** | **204,58 ms** | 276,86 ms |

So với run trước: Recall@5 **−26,3 điểm %**, MRR **−25,4 điểm %**, latency p50 **+78%**
(embed model lớn hơn trên CPU), nguồn trả về trung bình tăng 1,58 → 3,68 — trả **nhiều
nguồn hơn nhưng sai nguồn**. Sàn ngẫu nhiên (top_k=5, 11 tài liệu): 0,4545.

### 5.2 Tụt có quy luật — toàn bộ nằm ở TXT

| Nhóm nguồn | n | Recall@5 run này | Recall@5 run trước | Ca mất |
|---|---:|---:|---:|---|
| HTML (tin tiếng Việt) | 22 | **1,0000** | 1,0000 | 0 |
| TXT (học thuật EN) | 16 | **0,3125** (5/16) | 0,9375 (15/16) | **10** |

**10 ca mất hit:** QA-032, QA-034, QA-037, QA-039, QA-041, QA-043, QA-044, QA-045,
QA-046, QA-048. Cá biệt: QA-043 hỏi LoRA nhưng nhận **1 nguồn/1 note** thuộc tài liệu
khác; QA-048 nhận ngữ cảnh là thông báo bài viết VnExpress. Nhóm HTML không đổi (duy nhất
QA-016 giảm hạng 1 → 3, vẫn hit; QA-023, QA-033 còn tăng hạng).

**So chéo lịch sử — retrieval tất định theo embedding:**

| Run | Chat model | Embedding | Recall@5 | MRR |
|---|---|---|---:|---:|
| 20261119_173736 | bonsai-ternary-9b | gte-Qwen2 (1B Q4) | 0,7105 | 0,6798 |
| 20261121_023251 | qwenternary | gte-Qwen2 (Q4) | 0,7105 | 0,6798 |
| **20261121_050139 (run này)** | **Qwen3.5-4B** | **gte-Qwen2-1.5B Q4_K_M** | **0,7105** | **0,6798** |
| 20261121_030233 | qwenternary | Qwen3-Embedding-0.6B Q8_0 | 0,9737 | 0,9342 |
| 20261121_043458 | Qwen3.5-4B | Qwen3-Embedding-0.6B Q8_0 | 0,9737 | 0,9342 |

Ba run với ba chat model khác nhau cho **cùng kết quả bit-per-bit** khi cùng dòng GTE;
hai run Qwen3-Embedding cũng vậy. Kết luận: điểm tụt là **đặc tính của gte-Qwen2 trên
corpus này**, không phải nhiễu server.

**Giả thuyết kỹ thuật (cần verify riêng):** gte-Qwen2-instruct được huấn luyện bất đối
xứng — query cần bọc prompt hướng dẫn ("Instruct: … Query: …") mới đạt chất lượng thiết
kế, trong khi backend gửi query trần; phía tài liệu học thuật tiếng Anh dài và thuật ngữ
chuyên sâu khiến khoảng cách(query, chunk) sai lệch nhiều hơn tin tiếng Việt ngắn.

---

## 6. RAG hỏi đáp (SSE thật)

### 6.1 Câu có căn cứ

| n | Token-F1 gold (phụ) | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | Token TB | first-event p50 | total p50 / p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0,1493 | **0,7895** (30/38) | 0,2105 (8/38) | 0,0526 (2/38) | 1.434,1 | 217,31 ms | **4.341,97 / 7.957,40 ms** |

- `no_source_rate` = **0,0** · `no_context_rate` = **0,0** (run trước mỗi thứ 0,0263 —
  QA-038 nay nhận nguồn sai thay vì nguồn rỗng), ngữ cảnh TB 25.099 ký tự.
- total p50 **giảm 12,3%** (4.953 → 4.342 ms) — không phải model nhanh hơn, mà là câu trả
  lời **ngắn hơn** (576 so với 745 ký tự/ca) vì tỷ lệ lớn câu "từ chối ngắn".

**8 ca không trích dẫn — tất cả đều là từ chối trung thực do sai ngữ cảnh:**

| Ca | Nhóm nguồn | old citation | Hành vi |
|---|---|---:|---|
| QA-002 | HTML | 2 | Bảo "không đủ thông tin chi tiết" dù ngữ cảnh đúng — model thận trọng hơn run trước |
| QA-034 | TXT | 3 | "chưa có thông tin về kết quả của Transformer" (ngữ cảnh sai) |
| QA-037 | TXT | 1 | "chưa có thông tin về mã nguồn" (ngữ cảnh sai) |
| QA-038 | TXT | 0 | Vẫn không trả lời được — nay nhận 5 nguồn sai thay vì 0 nguồn |
| QA-043 | TXT | 6 | Hỏi LoRA, ngữ cảnh là "tấm chắn Mặt Trời" → từ chối |
| QA-045 | TXT | 7 | Hỏi chạy LLM tiết kiệm phần cứng, ngữ cảnh vệ tinh/Nvidia → từ chối |
| QA-046 | TXT | 3 | Hỏi định nghĩa quantization, ngữ cảnh VnExpress → từ chối |
| QA-048 | TXT | 5 | Hỏi dạng quantization, ngữ cảnh thông báo bài viết → từ chối |

7/8 ca thuộc nhóm TXT — **chuỗi hệ quả của lỗi search**, không phải model "lười trích
dẫn" hay bịa. Token-F1 giảm (0,1638 → 0,1493) cũng do nhiều câu trả lời loại "không có
thông tin" không khớp gold.

**Đối chiếu các lỗi nội dung của run trước:**

| Ca | Run trước (qwen3embed) | Run này (qwengte) |
|---|---|---|
| QA-033 | ❌ trả WSJ + "40.000 câu" không có trong nguồn | ✅ trả đúng **WMT 2014**, BLEU 28,4 / 41,8, có trích dẫn |
| QA-009 | ❌ nêu "Hoàn thành năm 2024" | ✅ năm 2025, 18.700 chỉ tiêu / 5.158 hoàn thành, đúng nguồn |
| QA-040 | ⚠️ proxy số `10.000` (khả năng FP) | ✅ không vi phạm, trả đúng cơ chế LoRA |
| QA-044 | ⚠️ bỏ sót gold "Microsoft Corporation" | ❌ từ chối hẳn — search không trả đúng nguồn |

Ba lỗi "bịa số/nội dung" của run trước biến mất trong khi chat model **không đổi** —
cho thấy chúng phần lớn do **thứ tự/ngữ cảnh retrieval** đưa vào prompt, và Qwen3.5-4B
trả lời khá "theo ngữ cảnh được cho".

**2 ca vi phạm số — đọc tay: gần như toàn dương tính giả của proxy:**

- **QA-015** (`'4'`): nguồn viết **"tám bàn và bốn kiến tạo"** bằng chữ; model chuyển ra
  số "8 bàn và 4 kiến tạo" — thông tin đúng, proxy không nhận diện số viết bằng chữ.
- **QA-011** (`'2022'`, `'28.2'`): "2022" suy ra từ "ba năm trước" (2025−3);
  "28,2 triệu/m²" là **quy đổi đơn vị** từ "282.000 đồng/m²" có nguyên văn trong nguồn.
- Nhóm không căn cứ: **QA-008** (`'3'`) đến từ câu "(ID 2, 3, 4)" — đánh số nguồn, không
  phải số liệu; **QA-010** (`'5200'`) là làm tròn **5.158 → "gần 5.200 căn"** — sai số
  nhỏ có thật (proxy bắt đúng hiện tượng số không nguyên văn, mức độ nhẹ).

### 6.2 Câu không đủ căn cứ

| n | Từ chối đúng (heuristic) | Trả lời bừa (heuristic) | Số ngoài ngữ cảnh |
|---:|---:|---:|---:|
| 11 | **0,8182 (9/11)** | 0,1818 (2/11) | 0,1818 (2/11) |

Heuristic điểm cao nhất trong các run gần đây. Đọc tay cả 11 ca:

- **9 ca có marker từ chối ngay câu đầu** ("chưa có thông tin", "không được đề cập"…).
- **QA-024**: câu đầu là dẫn nhập, phần sau mới khẳng định "chưa có thông tin xác nhận thủ
  phạm" → **âm tính giả của heuristic**, thực chất có từ chối.
- **QA-049**: trả lời bằng **ChatGLM3-6B** có căn cứ trong nguồn — tiếp tục là **tranh
  chấp nhãn dataset** (đã ghi nhận ở 2 run trước), không phải model bịa.
- 2 ca vi phạm số (QA-008, QA-010) đã phân tích ở 6.1 — không có ca nào bịa số liệu
  nghiêm trọng ở nhóm âm.

**Kết luận RAG:** chất lượng downgraded gần như hoàn toàn do retrieval; hành vi model
"trung thực theo ngữ cảnh" (không bịa khi ngữ cảnh sai). Ưu tiên xử lý embedding trước
khi tối ưu thêm gì khác ở RAG.

---

## 7. PageMatch

49 ca, **0 lỗi**. `verify_unavailable_rate` **0,0408** (2 ca, như cũ), `truncated_rate`
**0,2245** (11/49 — toàn bộ TXT, như cũ), `full_page_mode_rate` **0,2449 (12/49)** so với
0,102 (5/49) trước — **tăng gấp 2,4 lần**.

### 7.1 Chất lượng — segments (không warning, top-5)

| Dương tính | Hit | Exact | Precision@5 | Recall@5 | F1@5 | Span Precision | Span Coverage | Span F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 0,5862 | 0,5862 | 0,2598 | 0,5862 | 0,3322 | 0,1592 | 0,6255 | 0,1892 | 10 | **0,5000** |

### 7.2 Chất lượng — full-page

| Dương tính | Hit | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|
| 8 | 0,5000 | 0,7642 | 1 | 1,0 |

### 7.3 Toàn bộ item và nhóm `verified`

| Dương tính | `hit_all` | `hit5_page` | `hit5_score` | Precision all | Coverage all | Verified recall | Verified precision (macro/micro) | Âm tính | FPR any / verified FPR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | **0,6842** (26/38) | 0,5789 | 0,6316 | 0,2217 | 0,7252 | **0,6579** (25/38) | 0,2445 / 0,1376 | 11 | **0,6364 / 0,5455** |

### 7.4 So từng ca với run trước (hit theo đúng định nghĩa metric)

- **5 ca được thêm:** QA-004, QA-009, QA-016, QA-027, QA-030.
- **4 ca mất:** QA-021, QA-029, QA-040, QA-047.
- Net **+1 ca** (25 → 26) — `hit_all` nhích nhẹ, chưa phải cải thiện có ý nghĩa.

### 7.5 Vì sao FPR tăng gấp rưỡi?

9 ca đổi chế độ chạy, 8 ca trong số đó **segments → full_page** (QA-002, QA-003, QA-004,
QA-005, QA-006, QA-014, QA-019, QA-023 — gần như toàn bộ là HTML VnExpress); chỉ QA-046
đổi ngược lại. Chế độ full-page trả rất nhiều item (QA-003: 12 block, QA-049: 15,
QA-006: 10, QA-031: 7) nên xác suất chạm gold ở ca dương tăng — nhưng ở **ca âm** cũng
tăng theo: 7/11 ca âm nay trả về item so với 4/11 trước (QA-003 0→12 item, QA-006 0→10,
QA-031 1→7, QA-042 0→1, QA-024 0→1). Latency toàn module p50 **10.456 ms (+71%)**,
p95 21.484 ms — vẫn là hệ quả của việc vào full-page nhiều hơn.

**Đọc:** PageMatch bị ảnh hưởng gián tiếp qua embedding (chọn block/mode). Hit nhích +1
đáng giá hơn FPR tăng: nếu mục tiêu là giảm false positive thì cấu hình này **lùi lại**.

---

## 8. Hiệu năng và token — so chéo nhanh

| Chỉ số | gte-Qwen2-1.5B (run này) | Qwen3-Embedding-0.6B (run trước) | Δ |
|---|---:|---:|---:|
| Ingest chờ index p50 | 3.019,69 ms | 2.014,43 ms | +49,9% |
| Search p50 | 204,58 ms | 114,95 ms | +78,0% |
| RAG first-event p50 | 217,31 ms | 133,58 ms | +62,7% |
| RAG total p50 | 4.341,97 ms | 4.952,55 ms | −12,3% (trả lời ngắn hơn) |
| PageMatch p50 | 10.456,12 ms | 6.111,70 ms | +71,1% |
| Token tiêu thụ | 586.791 | 562.444 | +4,3% |

Latency phần embedding tăng xuyên suốt (ingest, search, first-event RAG, PageMatch) —
đúng kỳ vọng khi gấp 2,5× tham số embed model trên CPU. RAG total lại giảm vì cấu trúc
câu trả lời thay đổi (nhiều từ chối ngắn), không phải tốc độ sinh tốt hơn.

---

## 9. Kết luận và khuyến nghị

1. **Không nên giữ gte-Qwen2-1.5B-instruct cho corpus hiện tại.** Mất 26,3 điểm % Recall@5
   tập trung 100% ở nhóm TXT học thuật, kéo theo 8 ca RAG từ chối sai lý do "không có
   thông tin" và PageMatch FPR tăng 0,27 điểm %. Trong khi đó Qwen3-Embedding-0.6B (bé
   hơn, nhanh hơn) đạt Recall@5 0,9737. **Quay lại `Qwen3-Embedding-0.6B-Q8_0`** là quyết
   định mặc định hợp lý.
2. Nếu muốn tiếp tục với dòng GTE: (a) thử bọc **instruction prompt** cho query (đúng cách
   dùng `gte-Qwen2-instruct`); (b) thử bản **1B/non-instruct hoặc Q8** để loại trừ quantize;
   (c) chạy A/B chỉ module `search` với `--modules search` cho rẻ (không cần RAG).
3. **Lỗi chat model cũ không phải lỗi model:** QA-033/QA-009 tự hết khi thứ tự ngữ cảnh
   đổi — khi chấm RAG nên ghi nhớ rằng phần lớn biến động chất lượng câu trả lời đến từ
   retrieval. QA-044 (gold "Microsoft Corporation") vẫn chưa được trả lời đúng trong cả
   hai embedding — rà lại chunk chứa thông tin này trong `LORA LOW-RANK ADAPTATION.txt`.
4. **Proxy "số ngoài ngữ cảnh" cần cảnh giác với:** số viết bằng chữ trong nguồn ("bốn
   kiến tạo"), quy đổi đơn vị (282.000 đồng → 28,2 triệu), suy luận năm ("ba năm trước"
   → 2022), đánh số nguồn (ID 2, 3, 4). Chỉ QA-010 (5.158 → "gần 5.200") là sai số nhỏ
   có thật. Cân nhắc thêm normalizer số-từ (một/two/…) trước khi báo violation.
5. **Dataset:** giữ nguyên kiến nghị từ 2 run trước — rà lại nhãn `answerable=no` của
   QA-020 (Dyson Sphere) và QA-049 (ChatGLM3-6B sau quantization) vì nội dung trả lời có
   căn cứ trong nguồn; và cải thiện marker từ chối cho dạng "dẫn nhập → từ chối ở câu sau"
   (QA-024, QA-006).
6. **Tái lập:** `--recompute` khớp hoàn toàn; `eval_code_sha256` trùng run trước;
   git commit trong manifest là `46f5435` (metric PageMatch đã ổn định trước run — sạch
   hơn run trước vốn bị commit đè giữa chừng).

---

## 10. Artifact

```
runs/20261121_050139_470458_local-qwen3-5-4b-qwengte_lat3-full-local/
├── run_manifest.json          # model/provider/embedding, eval_code_sha256, command
├── raw_results.jsonl          # 147 record (11 ingest + 38 search + 49 rag + 49 pagematch*)
├── metrics.json               # metrics v4 — đã --recompute khớp
├── metrics.recomputed.json
└── report.md                  # report pipeline tự sinh
runs/MODEL_COMPARISON.md       # đã cập nhật --compare (nhóm ef7c82ca…)
```

\* RAG: 38 answerable + 11 unanswerable = 49; PageMatch: 49.
