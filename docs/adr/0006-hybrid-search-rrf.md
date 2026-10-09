# ADR-0006: Hybrid search (vector + full-text) gộp bằng RRF trong SQL

**Bối cảnh.** SDS §5.1.3: top-5 theo độ tương đồng vector. Kịch bản #4: BM25 + vector + rerank. Ghi chú tiếng Việt chứa nhiều tên riêng/thuật ngữ mà embedding đôi khi bỏ lỡ.

**Quyết định.** Một câu SQL: nhánh vector (cosine, HNSW) và nhánh full-text (`tsvector simple`, `ts_rank_cd` ~ BM25), mỗi nhánh lấy 30 ứng viên **đã lọc `user_id` (+ `folder_id`)**, gộp bằng **Reciprocal Rank Fusion** `Σ 1/(60 + rank)`. Rerank bằng LLM để sau cờ `SEARCH_RERANK_ENABLED` (task R02) với timeout → fallback thứ tự RRF.

**Phương án đã loại.** Chỉ vector (kém với từ khoá hiếm); BM25 thật (extension `pg_search`/ParadeDB — thêm phụ thuộc cài đặt); cộng điểm có trọng số (phải chuẩn hoá thang điểm 2 nguồn, khó chỉnh).

**Hệ quả.** (+) 1 round-trip DB, không rò dữ liệu chéo user, không cần tham số chuẩn hoá. (−) `ts_rank_cd` không phải BM25 chuẩn; cấu hình `simple` không bỏ dấu → "pho" ≠ "phở" (có thể thêm `unaccent` sau, đo bằng bộ đánh giá H03).
