# ADR-0019: DEV_UNLIMITED — bỏ chặn quota/rate limit trong môi trường dev

- **Trạng thái:** Chấp nhận (21/11/2026) · Liên quan: ADR-0010 (rate limit), ADR-0016 (BYOK)

## Bối cảnh

Dev/demo cần chạy các luồng AI dài (index toàn bộ ghi chú, chat, quét trang) mà không bị
`402 QUOTA_EXCEEDED` hay `429 RATE_LIMITED` giữa chừng. Cơ chế hiện có chỉ cho **đặt lại**
quota thủ công; BYOK vẫn bị chặn bởi hạn mức server (ADR-0016). Việc đặt lại làm mất số liệu
đã dùng, trong khi yêu cầu là **vẫn đếm** để quan sát chi phí.

## Quyết định

Thêm biến `DEV_UNLIMITED` (mặc định `false`), chỉ dùng ở dev/test. Khi bật:

1. `QuotaService.reserve()` vẫn ghi `quota_ledger` và cộng `used_tokens`/`reserved_tokens`,
   nhưng **không kiểm tra** `used + reserved + estimate <= limit` → không bao giờ ném
   `QuotaExceeded` vì hạn mức.
2. `GET /me/quota` trả thêm `limit_enforced: false`; extension hiển thị trạng thái dev và
   **không** hiện banner “Đã hết hạn mức”.
3. Dependency `rate_limit()` bỏ qua kiểm tra tần suất (mọi nhóm endpoint).
4. `APP_ENV=prod` **từ chối khởi động** nếu `DEV_UNLIMITED=true` (API và worker).
5. `infra/.env.example` bật `true` cho dev; `.env.prod.example` và mặc định code là `false`.

`limit_enforced` là field additive, có default `true` để client cũ vẫn đọc được response.

## Phương án đã loại

| Phương án | Lý do loại |
|---|---|
| Tự động khi `APP_ENV=dev` | Không kiểm soát được; lỡ chạy dev config ở nơi công khai là vô hạn |
| Chỉ khi `AUTH_MODE=local` | Trộn khái niệm auth với billing; không dùng được cho dev OAuth |
| Auto top-up mỗi lần chạm ngưỡng | Vẫn giữ logic chặn nhưng “limit” mất ý nghĩa, khó đọc lịch sử |
| Cờ theo từng user | Cần migration + UI quản trị; nặng hơn nhu cầu dev |
| Bỏ chặn quota toàn cục | Đổi hành vi mọi môi trường, phá contract 402 và test |

## Hệ quả

- (+) Dev/demo không bị khoá AI; số token vẫn được ghi để đối chiếu chi phí.
- (+) Prod an toàn: bật nhầm → fail-fast, không âm thầm mở chi phí.
- (+) Rate limit được bỏ cùng lúc nên không phải cấu hình từng ngưỡng về 0.
- (−) Dev không còn kiểm tra được luồng 402/429; phải đặt `DEV_UNLIMITED=false` khi cần test.
- (−) Nếu dev dùng key thật và API lộ ra ngoài, chi phí không bị chặn — chỉ dùng ở máy/dev nội bộ.
- (−) UI phải xử lý thêm trạng thái `limit_enforced=false` (đã cập nhật Settings + Popup).
