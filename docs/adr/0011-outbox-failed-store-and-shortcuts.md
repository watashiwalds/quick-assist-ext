# ADR-0011: Ghi chú gửi lỗi vào store "failed" (không xoá) & đổi phím tắt sang Alt+Shift

- **Trạng thái:** Chấp nhận (09/10/2026) · Task: N06, N02, P05

## Bối cảnh
1. Outbox (ADR-0008) xoá mục khi gặp lỗi không thể tự thử lại (413, 422, hết phiên, quá số lần thử) → **mất ghi chú âm thầm**, vi phạm ưu tiên chất lượng #2 "không mất ghi chú" (SDS §4.4).
2. Manifest khai báo `Ctrl+Alt+N`; Chrome **cấm** tổ hợp Ctrl+Alt (trùng AltGr) → extension không nạp được (phát hiện bằng E2E).

## Quyết định
1. Thêm object store `failed` (IndexedDB v2). Lỗi không tự khắc phục → chuyển mục từ `outbox` sang `failed` trong **một transaction**; UI hiện "N ghi chú chưa gửi được" với **Gửi lại** (về outbox, đếm lại lần thử, cùng Idempotency-Key) / **Bỏ** (xác nhận). Thư mục đích bị xoá → gửi lại vào Inbox. Hết phiên → giữ trong outbox, gửi sau khi đăng nhập lại.
2. Phím tắt: **Alt+Shift+N** lưu nhanh, **Alt+Shift+Z** hoàn tác (người dùng đổi ở `chrome://extensions/shortcuts`). SDS cần cập nhật (xem `docs/specs/sds-v1.2-changes.md`).

## Phương án đã loại
| Phương án | Lý do loại |
|---|---|
| Thử lại vô hạn | lỗi 413/422 không bao giờ tự hết → lặp vô ích, tốn pin/mạng |
| Thông báo rồi xoá | người dùng có thể không đọc kịp → mất dữ liệu |
| `Ctrl+Shift+N` | trùng phím mở cửa sổ ẩn danh của Chrome |

## Hệ quả
- (+) Không ghi chú nào bị mất mà người dùng không đồng ý; thao tác rõ ràng.
- (−) Thêm 1 store, 3 RPC (`outbox/list|retry|discard`), thay đổi phím tắt so với SDS/kịch bản.
