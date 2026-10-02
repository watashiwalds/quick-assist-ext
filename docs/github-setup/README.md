# Cấu hình GitHub (cần chuyển vào thư mục `.github/`)

Các file trong thư mục này là cấu hình GitHub. Hãy chuyển chúng vào đúng chỗ rồi commit:

```
docs/github-setup/CODEOWNERS                 → .github/CODEOWNERS
docs/github-setup/pull_request_template.md   → .github/pull_request_template.md
docs/github-setup/workflows/ci.yml           → .github/workflows/ci.yml
```

PowerShell (chạy ở thư mục gốc repo):
```powershell
New-Item -ItemType Directory -Force .github\workflows | Out-Null
Move-Item docs\github-setup\CODEOWNERS .github\
Move-Item docs\github-setup\pull_request_template.md .github\
Move-Item docs\github-setup\workflows\ci.yml .github\workflows\
Remove-Item -Recurse docs\github-setup
```

Sau đó: thay `@son-gh`, `@quang-gh`, `@vinh-gh`, `@duong-gh` trong CODEOWNERS bằng GitHub username thật, và bật
**Settings → Branches → Branch protection** cho `main` và `dev`: *Require a pull request*, *Require review from Code Owners*, *Require status checks (CI)*.
