# ADR-0012: Chat RAG — lịch sử hội thoại do client gửi kèm, server không lưu nội dung chat

- **Trạng thái:** Chấp nhận (10/10/2026) · Task: X01, X02 · Liên quan: ADR-0009 (SSE), SDS §5.1.6

## Bối cảnh
SDS §5.1.6 yêu cầu trả lời dựa trên ghi chú, giữ ngữ cảnh **5 cặp hỏi–đáp gần nhất**, có nút Dừng và trích dẫn nguồn.
Khung ban đầu (`business/rag`) dự kiến thêm bảng `chat_sessions` / `chat_messages` để server tự lưu lịch sử.

## Quyết định
1. **Lịch sử do client gửi kèm** mỗi câu hỏi (`history`, tối đa 20 lượt; server tự cắt còn 5 cặp gần nhất, mỗi lượt ≤ 2 000 ký tự).
   Lịch sử chỉ nằm trong bộ nhớ side panel — đóng panel hoặc bấm "Cuộc trò chuyện mới" là hết. Server **không lưu** nội dung chat.
2. Lượt `assistant` do client gửi không cần tin cậy hơn lượt người dùng: nó chỉ ảnh hưởng hội thoại của chính người đó.
   Ghi chú (dữ liệu không tin cậy từ web) vẫn được bọc `<notes>` và vô hiệu hoá thẻ giả như tóm tắt.
3. Không có đoạn ghi chú liên quan → trả câu trả lời cố định, **không gọi LLM** (tránh bịa, không tốn quota).
4. Hạn mức: embed câu hỏi tính `rag_retrieve`; lượt trả lời giữ chỗ `chat` (prompt + 800 token) rồi chốt theo usage thật.
   Bị Dừng / lỗi giữa chừng → chốt phần đã sinh (ước lượng nếu provider chưa báo usage); chưa sinh chữ nào → hoàn giữ chỗ.

## Phương án đã loại
- **Lưu lịch sử trên server** (bảng mới): thêm migration, phải xoá theo tài khoản (A08) và theo chính sách lưu trữ 1 năm (RET-01),
  thêm dữ liệu cá nhân phải bảo vệ — trong khi người dùng chưa cần xem lại hội thoại cũ trên máy khác.

## Hệ quả
- (+) Không thêm bảng/migration, không phát sinh dữ liệu cá nhân mới trên server; API không trạng thái, dễ test.
- (−) Không xem lại được hội thoại cũ sau khi đóng panel / trên máy khác. Nếu cần, thêm sau bằng bảng riêng mà không đổi contract SSE.
- (−) Mỗi câu hỏi gửi lại lịch sử (≤ 20 lượt, ≤ 2 000 ký tự/lượt) — chấp nhận được.
