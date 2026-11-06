# H01 / H02 — Checklist bảo mật (extension + backend)

> Owner: Lê Đăng Sơn (H01), Trịnh Mạnh Quang (H02) · Rà soát 09/10/2026 · ✅ = có kiểm tra tự động trong CI

## Extension (H01)
| # | Hạng mục | Hiện trạng | Kiểm tra |
|---|---|---|---|
| 1 | Quyền tối thiểu | `contextMenus, storage, identity, scripting, activeTab, alarms, sidePanel` + host **chỉ origin API**. Không `<all_urls>`, không `tabs/history/cookies/webRequest` | ✅ `scripts/check-bundle.mjs` |
| 2 | Không content script thường trực | chỉ tiêm hàm tự chứa khi người dùng thao tác (activeTab) | ✅ check-bundle + test kiến trúc |
| 3 | CSP | `script-src 'self'; object-src 'self'` (không eval, không script ngoài) | ✅ check-bundle (CSP + `eval/new Function`) |
| 4 | Không secret trong bundle | chỉ `VITE_GOOGLE_CLIENT_ID` (công khai theo thiết kế PKCE); không `client_secret`, khoá OpenAI, private key | ✅ check-bundle quét mẫu `sk-`, `GOCSPX-`, `PRIVATE KEY`, `client_secret` |
| 5 | Nơi lưu token | access token → `chrome.storage.session` (mất khi đóng trình duyệt); refresh token → `chrome.storage.local`; chỉ background đọc; không bao giờ log | ✅ test kiến trúc (UI không import storage) |
| 6 | Không còn mã kiểm thử ở bản phát hành | dev-login, hook `__qaE2E`, quyền `127.0.0.1` chỉ có khi `VITE_E2E=true`; bị loại bỏ khi build thường | ✅ check-bundle |
| 7 | Nội dung trang là dữ liệu không tin cậy | toast tạo DOM bằng `textContent`, Shadow DOM `closed`; UI React không dùng `dangerouslySetInnerHTML`; link nguồn `rel="noreferrer noopener"` | ✅ `tests/injected.test.ts` (không innerHTML) |
| 8 | Chỉ nhận RPC từ chính extension | `sender.id === chrome.runtime.id` | review |
| 9 | Xoá dữ liệu cục bộ khi đăng xuất / xoá tài khoản | IndexedDB (notes, outbox, failed, meta) + prefs + hồ sơ | ✅ E2E `sum-a08` |
| 10 | Giới hạn dữ liệu gửi đi | chỉ gửi khi người dùng chủ động; cắt 20 000 ký tự (note), 30 000 (tóm tắt) | ✅ unit |

## Backend (H02)
| # | Hạng mục | Hiện trạng | Kiểm tra |
|---|---|---|---|
| 1 | Xác thực mọi endpoint riêng tư | JWT HS256 15', `typ=access`, `iss`; user_id chỉ lấy từ token | ✅ `test_security::test_every_private_endpoint_requires_token` (tự quét OpenAPI) |
| 2 | Chống IDOR | mọi query lọc `user_id`; tài nguyên người khác → 404 | ✅ `test_no_idor_on_any_route_with_id` (mọi route có id) + search/summary/bulk-delete |
| 3 | Rate limit theo user | search 30/ph, AI 10/ph, ghi 120/ph → 429 `RATE_LIMITED` + `Retry-After` | ✅ `test_rate_limit_returns_429_with_retry_after` |
| 4 | CORS | chỉ `chrome-extension://<ID>`; prod từ chối khởi động nếu `*` hoặc origin khác | ✅ `test_cors_only_allows_configured_extension`, `test_prod_config_guard` |
| 5 | HTTPS | Caddy (Let's Encrypt) + HSTS; API chỉ lộ `/api/*`; DB không mở cổng | `infra/docker-compose.prod.yml`, `Caddyfile` |
| 6 | Header bảo mật | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP `default-src 'none'`, `Cache-Control: no-store` | ✅ `test_security_headers_and_request_id` |
| 7 | Không lộ lỗi nội bộ | lỗi không bắt → 500 `INTERNAL_ERROR` + request_id, không stacktrace; 422 không phản hồi lại giá trị đầu vào | ✅ `test_account::test_failure_mid_transaction_rolls_back`, `test_auth_google::test_exchange_validates_pkce_shape` |
| 8 | Cấu hình prod an toàn | từ chối khởi động nếu JWT_SECRET yếu (< 32) / mặc định, ENABLE_DEV_LOGIN bật, CORS sai | ✅ `test_prod_config_guard` |
| 9 | Log không chứa bí mật | che theo tên khoá (đệ quy) + theo mẫu (Bearer, JWT, `sk-…`) kể cả trong message/exception | ✅ `test_logging.py` |
| 10 | Container | user không phải root, filesystem read-only, `no-new-privileges` | `apps/api/Dockerfile`, compose prod |
| 11 | OAuth | PKCE + state (client) + nonce, iss/aud/exp/email_verified, redirect_uri whitelist; refresh xoay vòng, tái sử dụng → thu hồi mọi phiên | ✅ `test_google_oidc.py`, `test_auth_google.py` |
| 12 | Prompt injection | dữ liệu bọc `<document>`, vô hiệu hoá thẻ giả, system prompt cấm làm theo | ✅ unit · 🔶 kiểm với OpenAI (SUM-04) |

## Rủi ro còn lại (chấp nhận cho MVP)
- Rate limit trong bộ nhớ từng tiến trình: chạy N instance API → giới hạn thực tế ×N (ADR-0010).
- Access token còn hiệu lực tối đa 15' sau khi thu hồi phiên (ADR-0005).
- `VITE_GOOGLE_CLIENT_ID` công khai trong bundle — đúng thiết kế (client công khai + PKCE, secret ở server).
