# Nhận code P0 (nhánh `p0-all`)

Tệp `quickassist-p0-all.bundle` chứa nhánh `p0-all` (34 commit, mỗi commit ghi mã task), tạo từ `origin/quang` (= base + nháp P02).

```bash
cd quick-assist-ext
git status                      # nên sạch trước khi chuyển nhánh
git fetch quickassist-p0-all.bundle p0-all:p0-all
git switch p0-all
```
Đẩy lên để nhóm review (theo CONTRIBUTING: PR vào dev):
```bash
git push -u origin p0-all
```
Lưu ý: thư mục hiện tại đang ở nhánh `dev` có thư mục cũ `apps/api/src/quickassist/{core,modules,providers}` — nhánh `base`/`p0-all` đã xoá chúng.

Chạy kiểm tra: xem `README.md`, `apps/extension/e2e/README.md`, `docs/qa/test-plan.md`.
