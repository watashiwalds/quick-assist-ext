# P09 — Thiết lập GitHub (việc cần quyền admin repo)

> Code đã sẵn sàng (CI 3 job `api`, `extension`, `e2e`; `.github/CODEOWNERS`). Các bước dưới cần **chủ repo** (`watashiwalds`) làm trên GitHub — không làm được qua mã nguồn.

## 1. Điền GitHub username vào `.github/CODEOWNERS`
| Placeholder | Thành viên | Username (điền) |
|---|---|---|
| `@son-gh` | Lê Đăng Sơn | ? |
| `@quang-gh` | Trịnh Mạnh Quang | `@Wangamrt`? (người commit nháp P02 — cần xác nhận) |
| `@vinh-gh` | Mai Đức Vinh | ? |
| `@duong-gh` | Trần Thùy Dương | ? |

Thay hàng loạt: `sed -i 's/@son-gh/@<username>/g' .github/CODEOWNERS` (tương tự cho 3 người còn lại). Mỗi người phải có quyền **Write** trên repo thì CODEOWNERS mới có hiệu lực.

## 2. Bảo vệ nhánh `main` và `dev`
Settings → Branches → **Add branch ruleset** (hoặc Branch protection rule) cho `main` và `dev`:
- [x] Require a pull request before merging — 1 approval; **Require review from Code Owners**
- [x] Require status checks to pass: `api`, `extension`, `e2e`
- [x] Require branches to be up to date before merging
- [x] Block force pushes; không cho xoá nhánh
- [ ] (tuỳ chọn) Require linear history

## 3. Kiểm tra
Mở 1 PR thử sửa `apps/api/src/quickassist/business/notes/` từ `business/semantic_search/` (vi phạm L2) → CI `api` phải **đỏ** ở `test_layers.py`; PR thay đổi `docs/api/` phải yêu cầu Quang + Sơn duyệt.
