# ADR-0005: Google OAuth Code + PKCE, server đổi code, app session riêng

**Bối cảnh.** SDS §5.1.1 yêu cầu Google OAuth + PKCE; không lưu mật khẩu; extension là public client không giữ được secret.

**Quyết định.**
1. Extension: `chrome.identity.launchWebAuthFlow` tới Google với `code_challenge (S256)`, `state`, `nonce`, scope `openid email profile`. Redirect URI `https://<id>.chromiumapp.org/`.
2. Extension gửi `{code, code_verifier, redirect_uri, nonce}` → `POST /auth/google/exchange`.
3. Server (giữ `client_secret`) đổi code, verify `id_token` qua JWKS: chữ ký, `iss`, `aud`, `exp`, `nonce`, `email_verified`; kiểm tra `redirect_uri` thuộc whitelist.
4. Server phát **app session riêng**: access JWT 15' (stateless) + refresh token ngẫu nhiên (DB chỉ lưu SHA-256), **xoay vòng mỗi lần refresh**; dùng lại token cũ → thu hồi mọi phiên (phát hiện đánh cắp).
5. Extension: access token trong `chrome.storage.session`, refresh trong `chrome.storage.local`; refresh kiểu single-flight.

**Phương án đã loại.** `chrome.identity.getAuthToken` (chỉ Chrome có đăng nhập, trả access token Google — server phải gọi userinfo mỗi lần, không có nonce); dùng thẳng Google token làm session (phụ thuộc Google cho mọi request, khó thu hồi theo ứng dụng).

**Hệ quả.** (+) API stateless, scale ngang; thu hồi được phiên; extension không có secret. (−) Access token còn hiệu lực tối đa 15' sau khi xoá tài khoản/thu hồi (chấp nhận; FK cascade khiến mọi ghi mới thất bại). (+) Có `POST /auth/dev-login` CHỈ khi `APP_ENV=dev|test` để làm việc khi chưa cấu hình Google.
