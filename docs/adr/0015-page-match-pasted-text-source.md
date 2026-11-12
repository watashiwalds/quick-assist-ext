# ADR-0015: AutoChunk — nội dung người dùng dán là nguồn hạng nhất song song HTML trang

- **Trạng thái:** Chấp nhận (12/11/2026) · Kế hoạch: `docs/plan/page-paste/` · Liên quan: ADR-0013 (AutoChunk/Trafilatura), ADR-0007 (background gateway), ADR-0010 (rate limit)

## Bối cảnh
AutoChunk (ADR-0013) chỉ quét **trang đang mở**: extension chụp HTML → backend trích nội dung chính bằng Trafilatura
→ embed/LLM thẩm định → trả các đoạn khớp. Người dùng thường có nhu cầu tương tự với tài liệu **ngoài trình duyệt**
(PDF, Word, chat, email): nội dung nằm trong clipboard, không có URL và không có DOM để chụp.

Hai cách tiếp cận đã cân nhắc:
- **Bọc text thành HTML** rồi đẩy vào trường `html` hiện có. Rẻ về code nhưng Trafilatura làm phẳng xuống dòng,
  mất ranh giới đoạn tự nhiên khi copy từ PDF/Word; đồng thời nhét dữ liệu không phải HTML vào contract `html`
  đi ngược convention phân lớp của repo.
- **Nguồn thống nhất cho mọi tính năng AI** (Tóm tắt/Hỏi AI cũng nhận text dán). Đúng hướng dài hạn nhưng là
  scope creep: thay đổi nhiều contract và UI cùng lúc, chưa có nhu cầu được xác nhận.

## Quyết định
1. **Mở rộng contract `POST /ai/page-match`**: thêm `text: str | None` song song `html: str | None`; schema bắt buộc
   **đúng một trong hai** (`model_validator`). `url`/`title` vẫn chỉ để log/metadata; nguồn dán gửi `url = null`.
2. **Service rẽ nhánh theo nguồn**, không đổi pipeline phía sau:
   - `html` → Trafilatura trong process pool (nguyên trạng ADR-0013).
   - `text` → `split_paragraphs()` thuần Python (dòng trống `\n\n`; không có dòng trống thì tách theo câu) →
     `build_blocks()` trực tiếp, **bỏ qua Trafilatura/process pool**.
   - Từ `blocks` trở đi dùng chung: embed 1 batch, cosine + ngưỡng, LLM thẩm định, `segments|full_page`,
     degrade `VERIFY_UNAVAILABLE`, 2 lease quota, rate limit 6/phút.
3. **Không thêm permission, không đọc clipboard tự động**: người dùng Ctrl+V thủ công vào textarea trong side panel.
   Giữ nguyên tắc quyền tối thiểu H01 và không cần `clipboardRead`.
4. **UX dùng chung luồng kết quả**: nút phụ "Dán nội dung…" trong tab "Tìm trong trang" → textarea → "Quét nội dung".
   Khi nguồn là dán: ẩn "Xem tất cả trên trang", nút "Xem trên trang" bị khoá kèm tooltip *"Nội dung dán không có
   trang gốc để xem"*, banner dài đổi thành "Nội dung rất dài", "Lưu cả trang" → "Lưu toàn bộ nội dung".
5. **Cap dùng chung `PAGE_MATCH_MAX_CHARS` = 50 000** ký tự nội dung; phần vượt bị cắt theo biên khối và trả
   `truncated = true` (banner đã có). Nội dung dán không bị 413 theo `PAGE_MATCH_MAX_HTML_BYTES` — giới hạn đó
   chỉ dành cho HTML không tin cậy.
6. **Lưu kết quả không đổi contract**: `POST /notes` đã nhận `url: string | null`; ghi chú từ nguồn dán có
   title = truy vấn, `url = null`. Không migration, không bảng mới.
7. **Nội dung dán vẫn là dữ liệu không tin cậy** khi đưa vào prompt thẩm định: giữ nguyên wrapper/giới hạn của
   `page_match/prompts.py`; log chỉ metadata (nguồn, số khối/ký tự, mode, latency), không log nội dung.

## Phương án đã loại
- **Bọc text trong HTML (hướng A):** mất ranh giới đoạn do Trafilatura chuẩn hoá; sai ngữ nghĩa trường `html`;
  vẫn phải gánh chi phí process pool cho dữ liệu đã là text sạch.
- **Nguồn thống nhất cho mọi tính năng AI (hướng C):** thay đổi contract của Tóm tắt/Hỏi AI và UI rộng hơn nhu cầu
  MVP; để lại làm hướng tương lai.
- **Đọc clipboard tự động:** thêm permission `clipboardRead`, ngược H01 và không cần thiết — Ctrl+V là thao tác
  người dùng chủ động.
- **Nâng cap riêng cho nguồn dán:** quota AI là ràng buộc thật; cap chung + banner truncate đủ cho MVP, chỉ tách
  khi có dữ liệu cho thấy cần.
- **Tab riêng cho tính năng dán:** thêm một điểm điều hướng mà không thêm khả năng mới; nút phụ trong tab hiện có
  giữ luồng kết quả/chọn đoạn/lưu ghi chú dùng chung.

## Hệ quả
- (+) Tái dùng gần như toàn bộ pipeline AutoChunk; rủi ro thay đổi tập trung ở schema + một nhánh service + UI.
- (+) Chất lượng đoạn từ PDF/Word tốt hơn đường bọc HTML (giữ đoạn theo dòng trống, fallback câu khi chỉ có `\n`).
- (+) Không thêm permission, không thêm container/sidecar, không migration, không lưu nội dung dán trên server.
- (−) Contract `html` trở thành optional — client cũ vẫn hợp lệ, nhưng tài liệu/OpenAPI phải nêu rõ "đúng một nguồn";
  request thiếu cả hai hoặc có cả hai trả 422 `VALIDATION_ERROR`.
- (−) Nguồn dán không highlight được trên trang; UI phải giải thích rõ thay vì để nút im lặng thất bại.
- (−) Text dán rất lớn vẫn đi qua bước tách đoạn trước khi cap; chi phí CPU tuyến tính theo kích thước input,
  chấp nhận được ở quy mô hiện tại (cap nội dung 50 000 ký tự giới hạn chi phí AI).
