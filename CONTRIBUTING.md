# Quy trình làm việc nhóm

## Nhánh
- `main`: bản demo được; chỉ merge từ `dev` ở mốc tuần (Mốc MVP-1, MVP-2, Release).
- `dev`: tích hợp hằng ngày; **cấm push trực tiếp** — mọi thay đổi qua PR.
- Nhánh tính năng: `<mã-task>-<mô-tả-ngắn>`, ví dụ `N03-create-note-api`, `R04-search-ui`. Tạo từ `dev`, merge về `dev`.

## Commit
`<mã-task>: <động từ> <nội dung>` — ví dụ `N03: thêm idempotency cho POST /notes`.

## Pull request
- 1 PR = 1 task (hoặc 1 phần task) — dưới ~400 dòng thay đổi để review được.
- Cần ≥ 1 duyệt; PR chạm thư mục của người khác cần owner thư mục đó duyệt (xem `.github/CODEOWNERS`).
- CI phải xanh: lint, test (gồm **test kiến trúc**), `alembic check`, build extension.
- Điền checklist trong mô tả PR.

## "Phần nào ra phần đấy" — tóm tắt luật
| Bạn làm | Bạn được sửa | Muốn dùng phần khác |
|---|---|---|
| Service backend `X` | `business/X/**`, controller + schema của X, repository + model mà X sở hữu, migration cho bảng của X | Import `quickassist.business.Y` (public API); thiếu hàm → nhờ owner Y thêm |
| Hạ tầng backend | `infrastructure/`, `data/database.py`, `main.py`, `worker.py`, `infra/` | — |
| Extension core | `background/`, `content/`, `shared/` | — |
| UI | `ui/**` | Thêm RPC: sửa `shared/messaging/protocol.ts` (cần owner core duyệt) |

## Migration (tránh xung đột Alembic)
- Đặt message bắt đầu bằng tên module: `alembic revision --autogenerate -m "notes: add tags"`.
- Trước khi merge: `git pull origin dev`; nếu `alembic heads` ra 2 head → sửa `down_revision` của migration MỚI của bạn trỏ vào head kia.
- Không sửa migration đã merge vào `dev`; tạo migration mới.

## Definition of Done
Có test cho nhánh chính và nhánh lỗi · CI xanh · không log token/nội dung · ownership kiểm tra ở server · tài liệu/contract cập nhật · demo được trên dữ liệu mẫu.
