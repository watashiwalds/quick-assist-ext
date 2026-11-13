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
Tìm kiếm đã gộp vào **thanh tìm kiếm của tab Thư viện**: gõ từ khoá để lọc nhanh danh sách; nhấn **Enter** để **tìm sâu bằng AI** — câu hỏi tự nhiên, **có thể gõ không dấu** ("cong thuc nau pho"). Kết quả là các đoạn liên quan nhất kèm tên ghi chú (mặc định tối đa 5, chọn được 10/20 ở ô cạnh thanh); bấm **Mở ghi chú** (mở ngay trong khung đọc) hoặc **Mở trang nguồn ↗**. Có thể giới hạn trong một thư mục.

> Vẫn muốn tab riêng? Bật **Cài đặt → "Hiện tab Tìm kiếm trên thanh tab"**.

## 6. Tóm tắt bằng AI
- **Ghi chú đã lưu:** bấm **Tóm tắt bằng AI** trên thẻ ghi chú → xem trước → **Lưu tóm tắt** hoặc **Huỷ**.
- **Đoạn đang đọc:** bôi đen → chuột phải → **Tóm tắt đoạn văn bản này** → bảng bên phải mở tab *Tóm tắt* → **Lưu thành ghi chú** (lưu cả đoạn văn và bản tóm tắt), **Sao chép** hoặc **Huỷ**.
Bản tóm tắt chỉ được lưu khi bạn bấm Lưu.

## 7. Hỏi AI về ghi chú
Tab **Hỏi AI** trả lời câu hỏi dựa trên chính những ghi chú bạn đã lưu:
1. Chọn thư mục muốn hỏi (hoặc **Tất cả thư mục**), gõ câu hỏi rồi **Gửi**.
2. Câu trả lời hiện dần và ghi rõ nguồn `[1]`, `[2]`… — bấm số để mở ghi chú nguồn; **Chi tiết nguồn** hiện đoạn trích và liên kết trang gốc. Bấm **Dừng** nếu muốn dừng giữa chừng (phần đã trả lời được giữ lại, gắn nhãn *Đã dừng*).
3. **Lịch sử theo phiên:** câu hỏi và câu trả lời được lưu **trên máy này**, nên đóng side panel rồi mở lại vẫn còn. Cột **Hội thoại** bên trái liệt kê các phiên gần đây (tên là câu hỏi đầu tiên, có ô tìm và số lượt); bấm một phiên để mở lại, **Mới** để bắt đầu phiên khác. Ở panel hẹp, cột này thu thành drawer — mở bằng nút ở góc trái tiêu đề hội thoại. Đổi tên hoặc xoá phiên ngay trên tiêu đề; **Quản lý** ở cuối cột hiện dung lượng đã dùng và cho xoá từng phiên hoặc tất cả (gõ "XOÁ"). Tối đa 20 phiên gần nhất — phiên cũ nhất tự bị xoá.
4. Lịch sử chat **không gửi lên máy chủ** và bị xoá khi bạn **Đăng xuất** hoặc **Xoá tài khoản**. Đóng panel giữa lúc AI đang trả lời thì câu trả lời dừng lại, phần đã hiện vẫn được giữ (đánh dấu *Đã dừng*).

> Mỗi câu hỏi dùng hạn mức AI. AI chỉ trả lời dựa trên ghi chú của bạn, không đọc lịch sử duyệt web.

## 8. Tìm trong trang (AutoChunk)
Tab **Tìm trong trang** giúp gom các đoạn liên quan thay vì bôi đen từng đoạn:
1. Mô tả điều cần tìm (ví dụ "nghị quyết liên quan đến đất đai") rồi bấm **Quét trang**.
2. AI tìm trên trang đang mở, trả danh sách đoạn khớp để bạn tích chọn. Bấm **Xem trên trang** để cuộn tới và tô sáng đoạn đó.
3. Chọn thư mục rồi bấm **Lưu N đoạn thành ghi chú** — ghi chú có tiêu đề là truy vấn của bạn.

**Không có trang web?** Bấm **Dán nội dung…**, dán văn bản từ PDF, Word, chat, email… rồi bấm **Quét nội dung**. Có thể dán dài; khoảng 50 000 ký tự đầu được quét và bạn sẽ thấy thông báo nếu nội dung bị cắt. Nội dung dán không có trang gốc nên nút **Xem trên trang** bị khoá, và ghi chú được lưu **không kèm đường dẫn**.

## 9. Cài đặt, hạn mức AI, xoá tài khoản
Tab **Cài đặt**: xem hạn mức AI đã dùng/còn lại, chọn thư mục mặc định khi lưu nhanh, **Đăng xuất** (xoá bộ nhớ đệm và lịch sử chat trên máy). **Xoá tài khoản** xoá vĩnh viễn mọi ghi chú, thư mục, chỉ mục và lịch sử hạn mức — cần xác nhận 2 bước và gõ "XOÁ".

## 10. Câu hỏi thường gặp
| Hỏi | Đáp |
|---|---|
| Phím tắt không chạy? | Có thể trùng phím với ứng dụng khác — đổi tại `chrome://extensions/shortcuts`. |
| Ghi chú mới không tìm thấy? | Đợi nhãn chuyển *Sẵn sàng tìm kiếm* (vài giây). Nhãn *Bỏ qua (hết quota)* → xem Cài đặt. |
| Đóng side panel có mất hội thoại Hỏi AI không? | Không — lịch sử lưu trên máy theo phiên. Câu trả lời đang viết dở sẽ dừng và giữ phần đã hiện; mở lại chọn phiên cũ ở cột **Hội thoại**. |
| "Bạn thao tác quá nhanh"? | Giới hạn 30 lần tìm/phút, 10 lần tóm tắt/phút, 6 lần quét trang/phút — đợi số giây được báo. |
| Báo lỗi cho nhóm? | Gửi kèm **Mã lỗi** hiện dưới thông báo lỗi để nhóm tra log. |
| QuickAssist có đọc lịch sử duyệt web? | **Không.** Chỉ đọc đoạn bạn chủ động bôi đen và lưu/tóm tắt. |
