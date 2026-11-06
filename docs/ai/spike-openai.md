# P03 — Spike OpenAI cho văn bản tiếng Việt

> Owner: Mai Đức Vinh · Cập nhật: 08/10/2026 · Trạng thái: **phần đo offline xong; phần đo latency thật chờ API key**

## 1. Mục tiêu
Chốt model, kích thước chunk và hạn mức quota dựa trên số liệu: token / 1000 ký tự tiếng Việt, chi phí, latency p50/p95.

## 2. Phương pháp
| Hạng mục | Cách đo | Trạng thái |
|---|---|---|
| Token / 1000 ký tự | Đếm bằng tokenizer chính thức (`js-tiktoken`: `cl100k_base` cho text-embedding-3-small, `o200k_base` cho gpt-4o-mini) trên 20 ghi chú của `apps/api/tests/eval/dataset_vi.json` (7 915 ký tự) và 46 truy vấn | ✅ đã đo |
| Giá | Trang model chính thức của OpenAI (tra cứu 08/10/2026) | ✅ |
| Latency p50/p95 embedding + tóm tắt | `apps/api/scripts/spike_openai.py` gọi API thật, 3–5 vòng | ⏳ cần `OPENAI_API_KEY` của nhóm |

Chạy phần còn lại: `cd apps/api && OPENAI_API_KEY=sk-... python scripts/spike_openai.py --runs 5` → dán bảng in ra vào mục 4.

## 3. Kết quả đo offline

| Tokenizer | Dùng cho | Ký tự / token | Token / 1000 ký tự | Token trung bình / truy vấn |
|---|---|---|---|---|
| cl100k_base | text-embedding-3-small | **2.14** | **468** | 11.9 |
| o200k_base | gpt-4o-mini | **3.44** | **290** | 8.6 |

**Phát hiện:** ước lượng cũ `len // 3` (333 token/1000 ký tự) **thấp hơn thực tế ~29%** với embedding → giữ chỗ quota thiếu. Đã đổi `estimate_tokens()` thành `len // 2 + 1` (500 token/1000 ký tự — luôn dư, phần thừa trả lại khi commit). File: `infrastructure/openai/base.py`.

### Chi phí (giá niêm yết: embedding $0.02/1M token; gpt-4o-mini $0.15/1M input, $0.60/1M output)
| Thao tác | Token ước tính | Chi phí / lần |
|---|---|---|
| Embed 1 ghi chú trung bình (≈ 400 ký tự) | ≈ 190 | ≈ $0.000004 |
| Tìm kiếm (embed truy vấn ≈ 30 ký tự) | ≈ 12 | ≈ $0.0000002 |
| Tóm tắt ghi chú 2 000 ký tự (≈ 580 in + 80 system + ≤ 300 out) | ≈ 960 | ≈ $0.00028 |
| Tóm tắt tối đa 30 000 ký tự (≈ 8 700 in + ≤ 600 out) | ≈ 9 300 | ≈ $0.0017 |

Tải demo SDS §4.5 (50 user × 30 ghi chú/ngày = 1 500 ghi chú/ngày): embedding ≈ **$0.006/ngày**; 100 tóm tắt/ngày ≈ **$0.03/ngày**. Chi phí không phải rủi ro; rủi ro là **rate limit** (R-04).

## 4. Latency với API thật
| Chỉ số | Giá trị |
|---|---|
| embed p50 / p95 (1 ghi chú) | _chờ chạy script_ |
| embed 20 văn bản / 1 request | _chờ chạy script_ |
| summary p50 / p95 | _chờ chạy script_ |

Ngưỡng chấp nhận (NFR SDS §3.2): tìm kiếm < 3 s → embed truy vấn p95 phải < 1.5 s (phần SQL đo được p95 ≈ 115 ms trên 30 000 chunk — xem `eval-report.md` §4).

## 5. Đề xuất cấu hình (`.env`)
| Biến | Giá trị | Lý do |
|---|---|---|
| `EMBEDDING_MODEL` | `text-embedding-3-small` (1536 chiều) | Rẻ nhất, khớp cột `vector(1536)`; đổi model = migration + reindex |
| `CHAT_MODEL` | `gpt-4o-mini` | Đủ cho tóm tắt 5 gạch đầu dòng; o200k tiết kiệm token tiếng Việt hơn cl100k ~38% |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | `1200` / `150` | ≈ 560 token/chunk (xa giới hạn 8 191); eval H03 cho kết quả tốt nhất ở cấu hình mặc định với ít chunk nhất |
| `CHUNKING_STRATEGY` | `v2` | Theo câu tiếng Việt (N04) — không thua v1 ở mọi chỉ số |
| `QUOTA_DEFAULT_TOKENS` | `200000` (giữ) | ≈ 1 000 ghi chú hoặc ≈ 200 tóm tắt dài / user; trần chi phí xấu nhất ≈ $0.12/user |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | `30` / `2` | Tóm tắt dài có thể > 10 s; retry có backoff + jitter (P07) |
