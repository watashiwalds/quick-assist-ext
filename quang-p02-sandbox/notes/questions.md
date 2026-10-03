# P02 — Quyết định và điểm cần nhóm duyệt

## Quyết định đã đối chiếu

1. Endpoint tạo note chính thức là `POST /api/v1/notes`. Không dùng
   `/notes/quick` hoặc `/notes/ragged`; đây là các tên cũ mâu thuẫn trong SDS/kịch bản.
2. Body tạo note chỉ có `content` bắt buộc; `folder_id`, `source_url` và
   `source_title` là tùy chọn. Server lấy `user_id` từ app access token, không tin
   `user_id` trong JSON. Tài nguyên không thuộc user trả 404 ở endpoint đọc/sửa/xóa.
3. OAuth dùng Authorization Code + PKCE. Exchange nhận `code`, `code_verifier`,
   `redirect_uri`, `state`, `nonce`; backend kiểm tra state/nonce/issuer/audience/
   expiry/email_verified rồi cấp access token ngắn hạn và refresh token xoay vòng.
4. Mọi lỗi dùng `error.code`, `error.message`, `error.details`, `error.request_id`
   và response header `X-Request-ID`. JSON chuẩn hoá là `snake_case`; các tên
   `codeVerifier`, `redirectUri`, `requestId` trong SDS cũ không phải field wire format.
5. `POST /notes` bắt buộc `Idempotency-Key` UUID. Cùng user + key + payload phải
   trả kết quả cũ, không tạo note trùng; key dùng lại với payload khác trả 409.
6. Retry tự động chỉ áp dụng cho lỗi mạng/5xx, có exponential backoff + jitter, tối
   đa 5 lần. Không retry 401/409/422; 401 refresh một lần rồi yêu cầu đăng nhập lại.
   Với 429 (quota hoặc rate limit), UI hiển thị lý do và không retry vô hạn.

## Cần người phụ trách backend và extension duyệt

- Xác nhận giới hạn `content` là 50,000 ký tự và cửa sổ lưu idempotency key tối thiểu
  24 giờ trước khi đưa vào implementation.
- Xác nhận refresh token được trả qua JSON như draft hay cookie an toàn; điều này ảnh
  hưởng trực tiếp API client extension và cơ chế logout.
- Xác nhận 429 tiếp tục gộp quota/rate limit hay tách code chi tiết (ví dụ
  `QUOTA_EXCEEDED` và `RATE_LIMITED`) cùng `Retry-After`.
- Sau khi cả owner backend và extension duyệt, chuyển contract này thành nguồn OpenAPI
  dùng chung theo quy trình của nhóm; chưa sửa source backend/extension trong P02.
