# ADR-0010: Giới hạn tần suất trong bộ nhớ tiến trình API

- **Trạng thái:** Chấp nhận (09/10/2026) · Task: H02, R03

## Bối cảnh
Cần chặn một người dùng spam `/search`, `/ai/summaries` (tốn tiền OpenAI) hoặc ghi liên tục. Quota theo token chặn *chi phí* nhưng không chặn *tốc độ*. Tải demo: 1 instance API (SDS §4.5).

## Quyết định
Cửa sổ trượt 60 giây theo `(nhóm endpoint, user_id)` trong bộ nhớ tiến trình (`infrastructure/rate_limit.py`), gắn qua dependency `rate_limit()` ở controller. Vượt → **429 `RATE_LIMITED` + `Retry-After`** (tách khỏi 402 `QUOTA_EXCEEDED` — quyết định P02 #4). Ngưỡng cấu hình qua env, `0` = tắt.

## Phương án đã loại
| Phương án | Lý do loại |
|---|---|
| Redis | thêm hạ tầng chỉ để đếm, trái ADR-0002 (một kho dữ liệu) |
| Bảng PostgreSQL | thêm 1 lượt ghi DB cho mỗi request đọc; chưa cần |
| Chỉ dựa vào quota | không chặn được spam request rẻ/lỗi, không bảo vệ worker/DB |

## Hệ quả
- (+) Không thêm hạ tầng, < 1 µs mỗi kiểm tra, có giới hạn bộ nhớ (`max_keys`).
- (−) Chạy N instance → giới hạn thực tế N × ngưỡng; khởi động lại → đếm lại từ 0. Khi scale ngang: thay implementation bằng Redis giữ nguyên chữ ký `check()`.
