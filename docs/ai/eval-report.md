# H03 / N04 / R01 — Báo cáo đánh giá tìm kiếm

> Owner: Mai Đức Vinh · Đo ngày 08/10/2026 · AI = **mock** (bag-of-words, chạy offline). Chạy lại với OpenAI thật khi có key.

## 1. Bộ đánh giá
- Dữ liệu: `apps/api/tests/eval/dataset_vi.json` — 20 ghi chú tiếng Việt (2 ghi chú dài nhiều đoạn), **46 truy vấn**: 30 *keyword*, 13 *không dấu*, 3 *diễn đạt khác* (paraphrase).
- Chạy toàn pipeline thật: API → job index → pgvector → `POST /search`: `python -m tests.eval.run_eval` (cần `TEST_DATABASE_URL`).
- Chỉ số: **Recall@5** (có ghi chú đúng trong top-5), **MRR**, **AnswerHit@5** (cụm đáp án nằm *trọn* trong 1 chunk trả về — đo chất lượng chia đoạn), p50/p95 latency.
- Cổng CI: `tests/eval/test_eval_gate.py` — Recall@5 ≥ 0.93, MRR ≥ 0.85, AnswerHit@5 ≥ 0.9, Recall không dấu ≥ 0.9, p95 < 3 s.

## 2. Kết quả

### 2.1 Trước / sau R01 (cấu hình mặc định, chunk 1200)
| Phiên bản nhánh từ khoá | Recall@5 | MRR | AnswerHit@5 | R@5 keyword | R@5 không dấu | R@5 paraphrase |
|---|---|---|---|---|---|---|
| Trước: `plainto_tsquery` (AND mọi từ, có dấu) | 0.913 | 0.899 | 0.913 | 1.0 | **0.769** | 0.5 |
| **Sau R01**: `qa_unaccent` + OR giữa các từ | **0.978** | **0.929** | **0.978** | 1.0 | **1.0** | 0.5 |

Hai thay đổi: (1) chỉ mục và truy vấn đều bỏ dấu (`unaccent`, migration `0002`) → gõ "cau rong phun lua" vẫn ra "Cầu Rồng phun lửa"; (2) OR giữa các từ → câu hỏi tự nhiên ("mua quà gì ở đà lạt") không cần chứa đủ mọi từ; `ts_rank_cd` vẫn xếp chunk khớp nhiều từ lên trước.

### 2.2 Chunking v1 vs v2 (N04) — chunk nhỏ 300/60 để lộ khác biệt
| Cấu hình | Số chunk | Recall@5 | MRR | AnswerHit@5 | R@5 không dấu |
|---|---|---|---|---|---|
| v1 (cửa sổ ký tự) | 39 | 0.978 | 0.917 | 0.913 | 0.923 |
| **v2 (theo câu tiếng Việt)** | **37** | **1.0** | **0.961** | **0.935** | **1.0** |
| v2, `SEARCH_CANDIDATE_K=10` | 37 | 1.0 | 0.951 | 0.978 | 1.0 |

v2 tạo ít chunk hơn (ít token embedding hơn) nhưng không cắt giữa câu/từ → cụm đáp án nằm trọn trong chunk nhiều hơn. Unit test bất biến (≤ size, không mất từ, đúng thứ tự) chạy trên 30 văn bản ngẫu nhiên: `tests/unit/business/test_chunking.py`.

### 2.3 Hạn chế đã biết
- Nhóm *paraphrase* chỉ có ý nghĩa với embedding thật; mock là bag-of-words nên điểm nhóm này không phản ánh chất lượng ngữ nghĩa.
- Dataset nhỏ (46 truy vấn) → chênh lệch 1 truy vấn = 2.2 điểm %. Cần bổ sung truy vấn thật từ buổi test người dùng (H05).

## 3. Quyết định cấu hình
`CHUNKING_STRATEGY=v2`, `CHUNK_SIZE_CHARS=1200`, `CHUNK_OVERLAP_CHARS=150`, `SEARCH_CANDIDATE_K=30`, `SEARCH_TOP_K=5` — tốt nhất/ngang bằng trên mọi chỉ số với ít chunk nhất. Đánh giá lại khi chạy với OpenAI.

## 4. Latency phần cơ sở dữ liệu
30 000 chunk (10 user × 3 000), truy vấn hybrid qua API in-process, AI mock: **p50 ≈ 97 ms, p95 ≈ 115 ms** (máy dev 2 vCPU). Cộng latency embed của OpenAI (P03) vẫn còn xa ngưỡng 3 s.

## 5. Chạy với OpenAI thật
```bash
cd apps/api
AI_PROVIDER=openai OPENAI_API_KEY=sk-... TEST_DATABASE_URL=... python -m tests.eval.run_eval --configs default v2-small
```
Kết quả ghi vào `tests/eval/results/openai.json`; dán bảng vào mục 2.
