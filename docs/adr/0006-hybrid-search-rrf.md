# ADR-0006: Hybrid search (vector + full-text) gộp bằng RRF trong SQL

**Bối cảnh.** SDS §5.1.3: top-5 theo độ tương đồng vector. Kịch bản #4: BM25 + vector + rerank. Ghi chú tiếng Việt chứa nhiều tên riêng/thuật ngữ mà embedding đôi khi bỏ lỡ.

**Quyết định.** Một câu SQL: nhánh vector (cosine, HNSW) và nhánh full-text (`tsvector simple`, `ts_rank_cd` ~ BM25), mỗi nhánh lấy 30 ứng viên **đã lọc `user_id` (+ `folder_id`)**, gộp bằng **Reciprocal Rank Fusion** `Σ 1/(60 + rank)`. Rerank bằng LLM để sau cờ `SEARCH_RERANK_ENABLED` (task R02) với timeout → fallback thứ tự RRF.

**Phương án đã loại.** Chỉ vector (kém với từ khoá hiếm); BM25 thật (extension `pg_search`/ParadeDB — thêm phụ thuộc cài đặt); cộng điểm có trọng số (phải chuẩn hoá thang điểm 2 nguồn, khó chỉnh).

**Hệ quả.** (+) 1 round-trip DB, không rò dữ liệu chéo user, không cần tham số chuẩn hoá. (−) `ts_rank_cd` không phải BM25 chuẩn; cấu hình `simple` không bỏ dấu → "pho" ≠ "phở" (có thể thêm `unaccent` sau, đo bằng bộ đánh giá H03).

## Cập nhật Phase 1 — source-first + ngưỡng OR (18/11/2026)

**Bối cảnh.** Hợp đồng cũ trả danh sách chunk phẳng top-5. Người dùng không biết kết quả đến từ
website nào, nhiều chunk cùng một note/domain chiếm hết chỗ, và RAG lẫn Thư viện có thể lọc khác nhau.
Kế hoạch UX self-sustained (§6.1) chuyển sang trả theo **nguồn** (domain) trước, note sau.

**Quyết định.**

1. **Giữ nguyên SQL hybrid + RRF**; thêm bước gom thuần logic `group_by_source()` dùng chung cho
   Thư viện và RAG, sau khi đã lấy ứng viên rộng hơn (`k = min(max_sources * notes_per_source * 3,
   candidate_k * 2)`) để bù việc nhiều chunk/note.
2. **Gom chunk → note**: `similarity`/`score` của note = tốt nhất trong các chunk; chunk đại diện là
   chunk có `(similarity, score)` lớn nhất, snippet cắt 240 ký tự.
3. **Ngưỡng OR ở mức note**: giữ note nếu `similarity >= 0.5` **hoặc** `score >= 0.03` (env
   `SEARCH_MIN_SIMILARITY`, `SEARCH_MIN_RRF`). Không dùng AND: RRF một mình loại câu diễn đạt lại
   chỉ khớp ngữ nghĩa; cosine một mình loại câu khớp từ khoá chính xác.
4. **Gom theo `Note.domain`** (hostname của URL): note không có domain vào nhóm `null` với label
   "Không rõ nguồn", **luôn xếp cuối**. Xếp hạng nguồn: `max(similarity)` → `max(RRF)` → `note_count`
   → domain (deterministic). Trả tối đa `max_sources` nguồn (mặc định 5, client được chọn 1–20),
   mỗi nguồn tối đa `notes_per_source` note (10); `note_count` là **tổng số note đạt ngưỡng trước khi
   cắt**, để UI không báo thiếu khi nguồn có >10 note khớp.
5. **Hợp đồng API grouped** (`SearchOut.sources: SearchSourceOut[]`) là nguồn sự thật cho cả hai màn;
   RAG dùng cùng `search_sources()` rồi mới dựng prompt, không có luồng lọc thứ hai.

**Phương án đã loại.** Trả phẳng top-5 chunk rồi để client tự nhóm (hai client lệch nhau, không có
`note_count`); nhóm theo `note.folder_id` (thư mục là cách tổ chức của người dùng, không phải "nguồn"
trên web); dùng AND hai ngưỡng (giảm recall rõ rệt); bỏ RRF, chỉ vector (mất khớp từ khoá hiếm).

**Hệ quả.** (+) UI giải thích được "nguồn nào", không trùng note giữa nhóm, RAG và Thư viện cùng một
thứ hạng. (+) Ngưỡng chỉnh bằng env, không sửa code. (−) Ngưỡng 0.5/0.03 vẫn là đề xuất **chưa đo
trên DB thật**; eval baseline (`tests/eval/run_eval.py`) phải chạy trước khi chốt, hạ 0.5 → 0.45 chỉ
cần đổi env. (−) RRF một nhánh không bao giờ đạt 0.03 (max ≈ 1/61), nên note chỉ khớp từ khoá phụ
thuộc cosine — hành vi cần theo dõi bằng `empty_rate`/recall.
