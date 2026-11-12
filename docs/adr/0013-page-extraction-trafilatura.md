# ADR-0013: AutoChunk — trích nội dung trang bằng Trafilatura ở backend (process pool cùng container API)

- **Trạng thái:** Chấp nhận (10/11/2026) · Kế hoạch: `upgrade-plan/autochunk/` (plan v2) · Liên quan: ADR-0004 (AI port/adapter), ADR-0007 (background gateway), ADR-0010 (rate limit)
- **Thay thế:** quyết định §4.1 của plan v1 ("cắt đoạn ở content script theo DOM-block"). Plan v1/UI-evolution gọi quyết định này là "ADR-0012", nhưng số 0012 đã được dùng cho chat RAG → đánh số **0013**.

## Bối cảnh
AutoChunk là cách ghi chú thứ hai trên trang: người dùng mô tả điều cần tìm ("nghị quyết liên quan đến đất đai") → hệ thống
tìm các đoạn khớp trên **trang đang xem** → người dùng tích chọn → lưu thành **một** ghi chú gộp qua `POST /notes`.
Chất lượng "đoạn" quyết định chất lượng tính năng: nếu trộn menu, cookie banner, widget "tin liên quan"… thì embedding nhiễu,
LLM tốn token thẩm định rác, và giới hạn 50 000 ký tự bị chiếm bởi boilerplate.

## Quyết định
1. **Extension chỉ chụp HTML** (`content/injected.ts › getRawHtml`): làm trên bản sao DOM, bỏ `script/style/noscript/template/svg/iframe/canvas/…`,
   ô nhập ẩn/mật khẩu và mọi `value` → giảm payload, hạn chế dữ liệu nhạy cảm (`__NEXT_DATA__`, token form) rời máy. > 2 MB → dừng ở máy.
2. **Backend trích nội dung chính bằng Trafilatura** (`business/page_match/extractor.py`), XML → khối `p/head/item/quote/cell/code`
   theo thứ tự tài liệu; khối > 1 200 ký tự tách theo câu; mỗi khối có `id` và `occ` (lần xuất hiện thứ n của cùng text).
   Cap 50 000 ký tự **nội dung thật** theo biên khối.
3. **Trafilatura chạy trong `ProcessPoolExecutor` (spawn) ngay trong container API** — không sidecar. Timeout cứng 10 s: treo/crash
   → giết cả pool, tạo lại ở lần gọi sau; lỗi parse lxml/libxml2 không lan vào event loop. Chỉ `business/page_match` được import
   `trafilatura`/`lxml` (kiểm bằng `tests/architecture/test_layers.py::test_L8`).
4. **Độ tin cậy 2 tầng:** embed `[query, *blocks]` một batch → cosine thuần Python (khối không nằm trong DB) → lọc
   `min_score 0.35`, tối đa 15 ứng viên → **LLM thẩm định** trả JSON `{"results":[{"id","relevant"}]}`. LLM lỗi / quá 20 s /
   JSON hỏng / hết quota ở bước này → `warning=VERIFY_UNAVAILABLE`, trả ứng viên theo điểm với `verified=false` (không 502).
5. **Kháng prompt injection** như tóm tắt: dữ liệu trang bọc `<document>`, thẻ `document/query/block` giả bị vô hiệu hoá,
   system prompt cấm làm theo chỉ dẫn; chỉ chấp nhận `id` đã gửi đi.
6. **Highlight theo text** (`highlightBlocksByText`): so khớp sau khi bỏ mọi khoảng trắng → exact → contains → 80 ký tự đầu;
   phần tử sâu nhất, đúng `occ`. Nổi bật bằng CSS Custom Highlight API + `adoptedStyleSheets` — không thêm node/thuộc tính vào DOM trang.
7. **Không đổi schema DB.** `POST /ai/page-match` stateless (không cần Idempotency-Key); 2 lease quota `page_match_embed`,
   `page_match_verify`; rate limit riêng 6/phút. Kết quả lưu bằng `POST /notes` (Idempotency-Key do background sinh) → worker
   chunk + embed như note thường.
8. **Quyền đọc trang:** side panel không được cấp `activeTab` khi người dùng đã chuyển trang → `optional_host_permissions`
   `http(s)://*/*`, chỉ xin khi người dùng bấm "Cho phép đọc trang". Quyền bắt buộc không đổi (`check-bundle.mjs` vẫn chặn host rộng bắt buộc).

## Phương án đã loại
- **Cắt DOM-block ở content script (plan v1):** map highlight chính xác hơn, nhưng không lọc được boilerplate trên mọi trang; mỗi site
  một kiểu menu/widget → nhiễu embedding và lãng phí cap 50k. Hàm tiêm phải tự chứa → khó viết bộ lọc nội dung chính tốt.
- **Sidecar extraction service riêng:** cô lập tốt hơn nhưng thêm container, mạng nội bộ, healthcheck — quá nặng cho quy mô hiện tại.
  Process pool đã đủ cô lập lỗi/treo; nâng lên sidecar sau mà không đổi contract.
- **Re-chunk bằng `chunking.py`:** mất ranh giới khối tự nhiên của người dùng (mục danh sách, đoạn văn); `chunking.py` giữ cho index note.

## Hệ quả
- (+) Bỏ boilerplate trên mọi trang, ít token embed/verify hơn, 1 code path; tính năng không chết khi LLM thẩm định lỗi.
- (+) Không migration, không dữ liệu mới trên server; log chỉ metadata (số khối, ký tự, latency, mode).
- (−) Ảnh API lớn hơn (đo thực tế `docker compose build api`: ~426 MB so với ~333 MB trước đó, tức +~90 MB do trafilatura + lxml + phụ thuộc — plan ước 30–50 MB); lần quét đầu sau khi khởi động chậm hơn ~0,5–1 s (spawn process).
- (−) Text do Trafilatura chuẩn hoá có thể lệch DOM → highlight có thể trượt; thất bại → toast "Không tìm thấy đoạn trên trang".
- (−) Caddy phải nới `request_body` riêng cho `/api/v1/ai/page-match` (3 MB) — các route khác giữ 1 MB.
- (−) `match_ratio` khi số khối vượt ngưỡng điểm > 15 được **ngoại suy** theo tỉ lệ xác nhận trong nhóm đã thẩm định
  (nếu không, trang dài khớp gần hết không bao giờ đạt `full_page`).
