# Nhật ký lỗi và nhận xét khi chạy thử QuickAssist

Tài liệu này chuyển từ `TESTING.docx` để lưu các vấn đề và nhận xét phát hiện trong kịch bản A4 của hướng dẫn chạy thử. Các mục dưới đây là ghi nhận của người kiểm thử, chưa mặc định là lỗi đã được tái lập hoặc đã phân loại mức độ ưu tiên.

## Kịch bản A4 Kịch bản dùng thử

| Bước | Nhóm | Ghi nhận | Trạng thái cần làm rõ |
|---|---|---|---|
| Phím tắt lưu nhanh | Phím tắt | `Alt+Shift+N` bị trùng với chức năng ghép trang của Chrome. | Xác nhận trên môi trường Chrome đang dùng; cân nhắc đổi suggested shortcut hoặc hướng dẫn người dùng đổi phím. |
| 8 | Tìm kiếm | Chưa rõ giao diện chỉ hiển thị tối đa 5 kết quả hay hệ thống chỉ tìm được 5 kết quả. Khi tìm `huấn luyện`, kết quả có cả nội dung truyện, cảm giác độ liên quan chưa tốt. | Làm rõ giới hạn `top_k` của UI/API và bổ sung ca đánh giá chất lượng relevance. |
| 9 | Tìm kiếm | Tìm một nội dung hoàn toàn khác nhưng vẫn nhận được kết quả. | Kiểm tra ngưỡng relevance hoặc cách UI diễn giải kết quả khi không có kết quả đủ liên quan. |
| 10 | Tóm tắt ghi chú | Kết quả tóm tắt chưa đạt kỳ vọng; cảm giác chủ yếu là rút ngắn câu văn. | So sánh với tiêu chí summary mong muốn và kiểm tra prompt/model đang dùng. |
| 11 | Tóm tắt vùng chọn | Cảm giác bản tóm tắt chỉ rút gọn đoạn văn, chưa thay đổi hoặc tổng hợp thông tin đáng kể. | Đánh giá lại chất lượng summary với dữ liệu thật; phân biệt hành vi của AI mock và AI thật. |
| 13 | Offline và cache | Khi quay lại extension, dữ liệu cache không còn và giao diện yêu cầu đăng nhập Google. | Chỉ đánh giá sau khi dev login thành công trước khi dừng API; kiểm tra refresh token, cache local và luồng offline. |
| 14 | Khôi phục sau offline | Vẫn gặp xung đột phím tắt với chức năng ghép trang của Chrome. | Liên quan cùng vấn đề phím tắt lưu nhanh ở trên. |
| A5.4 | Tóm tắt bằng Gemini | Khi chọn **Tóm tắt bằng AI**, extension báo: “Không kết nối được máy chủ. Ghi chú sẽ được gửi lại khi có mạng.” | Chưa xác định nguyên nhân. API cần được kiểm tra qua health/log và đối chiếu CORS hoặc request từ extension. Mã lỗi/request ID: `e0286ed561a248b48b8682bbaa60cf0a`. |

## Ghi chú khi tái kiểm tra

- Với bước 13, chỉ dừng service `api`; không dừng Docker Desktop, `db`, `worker` hoặc reload extension.
- Cần đăng nhập thử thành công và có ít nhất một ghi chú đã lưu trước khi kiểm tra cache offline.
- `Alt+Shift+N` là phím tắt được manifest đề xuất. Chrome hoặc cấu hình phím tắt của máy có thể đang gán tổ hợp này cho chức năng khác; kiểm tra và đổi tại `chrome://extensions/shortcuts` khi tái hiện xung đột.
- Search hiện trả tối đa số lượng do `top_k` quy định; kết quả không rỗng không tự động chứng minh chúng đủ liên quan với truy vấn.
- AI mock được dùng trong demo/test offline; chất lượng tóm tắt của nó không phản ánh chất lượng khi cấu hình Gemini hoặc OpenAI thật.
- Thông báo network hiện dùng chung cho luồng lưu note và tóm tắt. Với tóm tắt, yêu cầu không được đưa vào outbox để tự gửi lại; cần xử lý kết nối API/CORS trước khi thử lại.

## Kết quả chạy tự động (2026-10-10)

- B4 backend: **180 passed trong 24.73 giây** với Python 3.12 và database riêng `quickassist_test`.
- Trên Python 3.14, 71 integration/eval test ban đầu bị chặn bởi `UnicodeDecodeError` khi Alembic đọc `alembic.ini` bằng mã hóa Windows `cp1252`. Đã thay chú thích UTF-8 trong file cấu hình bằng ASCII để migration chạy được trên Windows.
- Python 3.14 còn làm suite treo ở test Gemini streaming; đã dùng Python 3.12 cho B4.
- Smoke test: 10/11 bước đạt. Health, đăng nhập dev, tạo/index/tìm/xoá note và quota đều đạt. Bước tóm tắt trả HTTP 502 sau khi Gemini AI Studio trả HTTP 500 ba lần; request ID `e436ba09e7be4565a65fd8c196431b6f`. Một lượt trước đó Gemini đã tóm tắt thành công trong khoảng 26 giây, nên lỗi này có tính tạm thời từ upstream Gemini, không phải Docker hay API key bị sai.

## Đã xử lý từ lần rà soát source hiện tại

- Tóm tắt Gemini: extension từng tự hủy request sau 15 giây, trong khi Gemini có thể mất hơn 50 giây. Timeout riêng cho tóm tắt đã tăng lên 120 giây; backend chờ AI mặc định 90 giây thay vì 30 giây.
- Thông báo `NETWORK_ERROR` không còn nói sai rằng mọi lỗi đều sẽ “gửi lại khi có mạng”. Chỉ ghi chú nhanh mới có outbox để tự gửi lại; tóm tắt/search cần người dùng thử lại.
- Search giờ cho chọn và hiển thị rõ giới hạn tối đa 5, 10 hoặc 20 kết quả. Điều này làm rõ ghi nhận ở bước 8; chưa tự động chứng minh mọi kết quả đều liên quan.
- Test Windows: `alembic.ini` đã dùng chú thích ASCII để Alembic không còn đọc sai UTF-8 bằng `cp1252`.

## Còn cần đánh giá sản phẩm/AI

- Chất lượng relevance của search với các truy vấn như `huấn luyện`, đặc biệt khi dùng dữ liệu thật/Gemini, cần bộ dữ liệu đánh giá riêng. Không đặt ngưỡng lọc score tùy tiện vì điểm RRF không phải xác suất liên quan.
- Chất lượng tóm tắt là hành vi model/prompt: cần so sánh đầu ra Gemini thật với tiêu chí chấp nhận trước khi thay đổi prompt hoặc model.
- Xung đột phím tắt phụ thuộc cấu hình Chrome/máy. Người dùng có thể đổi phím tại `chrome://extensions/shortcuts`; chưa đổi mặc định một cách đoán mò.
