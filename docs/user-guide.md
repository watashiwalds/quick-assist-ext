# Hướng dẫn sử dụng QuickAssist

QuickAssist là tiện ích Chrome giúp bạn **lưu nhanh** đoạn văn bản đang đọc, **tóm tắt bằng AI** và **tìm lại theo ý nghĩa** (không cần nhớ đúng từ khoá).

## 1. Cài đặt
1. Tải tệp `quickassist-<phiên bản>.zip` từ nhóm, giải nén.
2. Chrome → gõ `chrome://extensions` → bật **Developer mode** (góc phải) → **Load unpacked** → chọn thư mục vừa giải nén.
3. Ghim biểu tượng QuickAssist lên thanh công cụ (biểu tượng mảnh ghép → ghim).

Yêu cầu: Chrome/Edge/Brave bản 116 trở lên, có tài khoản Google.

## 2. Đăng nhập
Bấm biểu tượng QuickAssist → **Đăng nhập bằng Google** → chọn tài khoản. QuickAssist không thấy mật khẩu Google của bạn.

## 3. Lưu nhanh một đoạn văn bản
1. Bôi đen đoạn văn bản trên trang web.
2. **Chuột phải → QuickAssist → Ghi chú văn bản này**, hoặc nhấn **Alt+Shift+N**.
3. Góc phải dưới hiện thông báo đếm ngược **5 giây**. Lỡ tay? Bấm **Hoàn tác** hoặc **Alt+Shift+Z**.

Ghi chú lưu kèm tiêu đề trang, đường dẫn và thời gian. Mất mạng cũng không sao: ghi chú được giữ trên máy và tự gửi khi có mạng.

**Lưu thẳng vào một thư mục:** chuột phải → *QuickAssist → Ghi chú vào thư mục → (tên thư mục)*. Đổi thư mục mặc định của phím tắt trong **Cài đặt**.

> Không lưu được trên các trang đặc biệt của trình duyệt (`chrome://…`, Cửa hàng Chrome). Đoạn dài hơn 20 000 ký tự được cắt bớt và có thông báo.

## 4. Thư viện ghi chú
Bấm biểu tượng → **Mở thư viện ghi chú** (mở bảng bên phải).
- **Lọc** theo thư mục hoặc gõ từ khoá vào ô "Lọc nhanh".
- Nhãn trạng thái: *Đang xử lý* (AI đang lập chỉ mục, vài giây) → *Sẵn sàng tìm kiếm*. *Bỏ qua (hết quota)* / *Lỗi xử lý AI*: ghi chú vẫn được lưu, bấm **Thử lại AI** khi có hạn mức.
- **Sửa**: đổi tiêu đề, nội dung, thư mục. Nếu ghi chú vừa được sửa ở máy khác, bạn chọn *Xem bản mới nhất* hoặc *Ghi đè bằng bản của tôi*.
- **Xoá**: nút Xoá trên từng ghi chú, hoặc **Chọn** → tích nhiều ghi chú → **Xoá (n)**.
- **Thư mục**: nút *Thư mục* để tạo, đổi tên, xoá (ghi chú trong thư mục bị xoá sẽ về **Inbox**).
- Dải đỏ "*n ghi chú chưa gửi được*": bấm **Xem** → **Gửi lại** hoặc **Bỏ ghi chú này**.

## 5. Tìm kiếm theo ý nghĩa
Tab **Tìm kiếm** → gõ câu hỏi tự nhiên, **có thể gõ không dấu** ("cong thuc nau pho") → **Tìm**. Kết quả là 5 đoạn liên quan nhất kèm tên ghi chú; bấm **Mở ghi chú** hoặc **Mở trang nguồn ↗**. Có thể giới hạn trong một thư mục.

## 6. Tóm tắt bằng AI
- **Ghi chú đã lưu:** bấm **Tóm tắt bằng AI** trên thẻ ghi chú → xem trước → **Lưu tóm tắt** hoặc **Huỷ**.
- **Đoạn đang đọc:** bôi đen → chuột phải → **Tóm tắt đoạn văn bản này** → bảng bên phải mở tab *Tóm tắt* → **Lưu thành ghi chú** (lưu cả đoạn văn và bản tóm tắt), **Sao chép** hoặc **Huỷ**.
Bản tóm tắt chỉ được lưu khi bạn bấm Lưu.

## 7. Cài đặt, hạn mức AI, xoá tài khoản
Tab **Cài đặt**: xem hạn mức AI đã dùng/còn lại, chọn thư mục mặc định khi lưu nhanh, **Đăng xuất** (xoá bộ nhớ đệm trên máy). **Xoá tài khoản** xoá vĩnh viễn mọi ghi chú, thư mục, chỉ mục và lịch sử hạn mức — cần xác nhận 2 bước và gõ "XOÁ".

## 8. Câu hỏi thường gặp
| Hỏi | Đáp |
|---|---|
| Phím tắt không chạy? | Có thể trùng phím với ứng dụng khác — đổi tại `chrome://extensions/shortcuts`. |
| Ghi chú mới không tìm thấy? | Đợi nhãn chuyển *Sẵn sàng tìm kiếm* (vài giây). Nhãn *Bỏ qua (hết quota)* → xem Cài đặt. |
| "Bạn thao tác quá nhanh"? | Giới hạn 30 lần tìm/phút, 10 lần tóm tắt/phút — đợi số giây được báo. |
| Báo lỗi cho nhóm? | Gửi kèm **Mã lỗi** hiện dưới thông báo lỗi để nhóm tra log. |
| QuickAssist có đọc lịch sử duyệt web? | **Không.** Chỉ đọc đoạn bạn chủ động bôi đen và lưu/tóm tắt. |
