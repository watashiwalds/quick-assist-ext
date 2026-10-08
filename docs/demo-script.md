# H08 — Kịch bản thuyết trình & demo (10–15 phút)

> Chuẩn bị: môi trường demo (runbook) + extension bản phát hành đã cài, đăng nhập sẵn 1 tài khoản có ~10 ghi chú mẫu (`tests/eval/dataset_vi.json`), 1 tab bài báo tiếng Việt, 1 tab tài liệu kỹ thuật. Kết nối dự phòng: điện thoại phát Wi-Fi. Video quay sẵn toàn bộ demo (phương án B).

## 1. Checklist trước giờ demo (T − 30 phút)
- [ ] `python apps/api/scripts/smoke_test.py --base https://<domain>` với token demo → 11/11 ✅
- [ ] Đăng nhập/đăng xuất Google thật 1 lần
- [ ] Hạn mức tài khoản demo > 50 000 token; tài khoản thứ 2 đã hết quota (để demo thông báo)
- [ ] Tắt thông báo hệ điều hành, phóng to chữ trình duyệt 125%
- [ ] Mở sẵn: slide, tab bài báo, tab tài liệu, side panel QuickAssist

## 2. Dòng thời gian
| Phút | Người | Nội dung | Thao tác demo |
|---|---|---|---|
| 0:00–1:30 | Sơn | Vấn đề: chép-dán ghi chú mất thời gian, khó tìm lại khi quên từ khoá | slide |
| 1:30–3:00 | Sơn | Giải pháp + kiến trúc phân tầng (SDS Hình 1), monolith API + worker, PostgreSQL/pgvector | slide kiến trúc |
| 3:00–5:00 | Dương | **Lưu nhanh**: bôi đen → chuột phải → toast 5s; lưu đoạn khác bằng **Alt+Shift+N**; **Hoàn tác** bằng Alt+Shift+Z; lưu vào thư mục qua menu con | tab bài báo |
| 5:00–6:00 | Dương | **Thư viện**: nhãn *Đang xử lý → Sẵn sàng*, lọc thư mục, sửa, xoá nhiều | side panel |
| 6:00–8:00 | Vinh | **Tìm kiếm**: câu hỏi tự nhiên, **gõ không dấu**, mở nguồn; số liệu Recall@5 0.978, không dấu 1.0 | side panel + slide eval |
| 8:00–9:30 | Vinh | **Tóm tắt**: ghi chú đã lưu (xem trước → Lưu); vùng chọn → tab Tóm tắt; trang có prompt injection không làm AI "nghe lời" | tab tài liệu |
| 9:30–10:30 | Quang | **Độ tin cậy**: tắt Wi-Fi → lưu ghi chú → bật lại → ghi chú tự gửi, không trùng; hết quota → vẫn lưu, thông báo rõ | máy demo |
| 10:30–11:30 | Quang | **Bảo mật & riêng tư**: OAuth PKCE, IDOR test mọi endpoint, quyền tối thiểu; **Xoá tài khoản 2 bước** | Cài đặt (tài khoản phụ) |
| 11:30–13:00 | Dương | Kiểm thử: 168 + 80 + 28 E2E, axe WCAG AA, lỗi P0 tìm thấy nhờ E2E (Ctrl+Alt) | slide |
| 13:00–15:00 | Cả nhóm | Hạn chế, hướng phát triển (chat RAG, gắn thẻ), hỏi đáp | slide |

## 3. Kịch bản usability test (H05, 3–5 sinh viên, ~10 phút/người)
Nhiệm vụ (không hướng dẫn trước, đo thời gian + số lần sai thao tác):
1. Lưu đoạn thứ hai của bài báo vào QuickAssist.
2. Huỷ một ghi chú vừa lưu nhầm trong 5 giây.
3. Tìm lại ghi chú nói về "cách hầm xương" mà không mở thư viện.
4. Tóm tắt ghi chú dài nhất và lưu bản tóm tắt.
5. Chuyển 2 ghi chú vào thư mục mới "Ôn thi".
Sau đó: bảng SUS 10 câu; ghi lỗi vào GitHub Issues `[usability]`.

## 4. Phương án dự phòng
| Sự cố | Xử lý |
|---|---|
| Mất mạng phòng | chuyển hotspot; vẫn demo được thư viện (cache) + outbox |
| OpenAI chậm/lỗi | demo trạng thái *Lỗi xử lý AI* → *Thử lại AI*; chiếu video phần tóm tắt |
| Đăng nhập Google lỗi | dùng trình duyệt đã đăng nhập sẵn (profile demo) |
| Máy chủ sập | chạy `docker compose up` trên laptop (AI mock) |
