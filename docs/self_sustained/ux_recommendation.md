Chung:
- Các chức năng liên quan đến tìm kiếm và sử dụng nội dung ghi chú thực hiện tìm kiếm top-k nguồn (5 nguồn), sau đó là top-n ghi chú trong nguồn (>= 50% tin cậy / 0.03 điểm trùng khớp), bao gồm chức năng tìm kiếm trong Thư viện, quá trình RAG trong Hỏi AI
- Dùng chung các tài nguyên giao diện nếu trùng nhau (trong CSS, component của TypeScript,...)

Thư viện:
- Gom nhóm các ghi chú chung nguồn, tránh pha loãng danh sách hiển thị
- Cho phép thay đổi thư mục của nhiều ghi chú / nhóm ghi chú cùng lúc
- Ưu tiên hiển thị nội dung tóm tắt của ghi chú / nhóm ghi chú trước nội dung gốc

Tìm trong trang:
- Thay ngưỡng cứng 50.000 ký tự bằng cảnh báo trước khi quét
- Cho phép lựa chọn thứ tự sắp xếp của các đoạn đề xuất theo 2 cách: Thứ tự trong văn bản gốc / Giảm dần độ tin cậy
- Đặt ngưỡng tin cậy tối thiểu để đoạn được đề xuất là >= 50% (hoặc tương đương nếu không có đánh giá của LLM)

Hỏi AI:
- Sửa lỗi các phiên trò chuyện cập nhật thời gian khi chỉ xem mà không có thao tác thực tế khác (gửi câu hỏi)
- Thay đổi câu hỏi gợi ý bằng các câu hỏi mang tính tổng quan
- Đồng bộ màu của thanh bên với các màn hình khác (thay màu xám thành màu trắng)
