# ============================================================================
#  QuickAssist — sắp xếp lại repo theo kiến trúc phân tầng (chạy 1 lần)
#  Chạy tại thư mục gốc repo (PowerShell):
#      powershell -ExecutionPolicy Bypass -File scripts\restructure.ps1
#  An toàn khi chạy lại: bước nào đã làm rồi sẽ được bỏ qua.
# ============================================================================
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Remove-IfExists($p) {
    if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force; Write-Host "  - xoá   $p" }
}
function Move-IfExists($src, $dstDir) {
    if (Test-Path -LiteralPath $src) {
        New-Item -ItemType Directory -Force $dstDir | Out-Null
        Move-Item -LiteralPath $src -Destination $dstDir -Force
        Write-Host "  > chuyển $src -> $dstDir"
    }
}

Write-Host "1) Xoá cấu trúc backend CŨ (chia theo modules/) — đã thay bằng các tầng SDS"
$api = "apps\api\src\quickassist"
Remove-IfExists "$api\core"
Remove-IfExists "$api\modules"
Remove-IfExists "$api\providers"
Remove-IfExists "$api\registry.py"
Remove-IfExists "$api\health.py"
Remove-IfExists "apps\api\tests\unit\test_chunking.py"
Remove-IfExists "apps\api\tests\unit\test_security_and_providers.py"
Remove-IfExists "apps\api\tests\integration\test_notes_flow.py"
Remove-IfExists "apps\api\tests\architecture\test_module_boundaries.py"
Get-ChildItem -Path apps -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

Write-Host "2) Đưa tài liệu gốc vào docs\specs và kế hoạch vào docs\plan"
Move-IfExists "SDS_Nhomx.pdf" "docs\specs"
Move-IfExists "QuickAssist_SDS_TheoMau_TrinhBayGiongMau.docx" "docs\specs"
Move-IfExists "1. SDS - Tự động hóa Xử lý Email Hỗ trợ Khách hàng bằng AI.pdf" "docs\specs"
Move-IfExists "Kịch bản chức năng QuickAssist_1.xlsx" "docs\specs"
Move-IfExists "Nhóm 1 - Báo cáo ý tưởng đề tài.docx" "docs\specs"
Move-IfExists "System Design Trade_Offs.docx" "docs\specs"
Move-IfExists "QuickAssist_KeHoach_PhanCong_GoogleOAuth_CoTen.xlsx" "docs\plan"
Move-IfExists "QuickAssist_KeHoach_PhanCong_v2.xlsx" "docs\plan"

Write-Host "3) Đưa cấu hình GitHub vào .github"
if (Test-Path "docs\github-setup") {
    New-Item -ItemType Directory -Force ".github\workflows" | Out-Null
    Move-Item -LiteralPath "docs\github-setup\CODEOWNERS" ".github\" -Force
    Move-Item -LiteralPath "docs\github-setup\pull_request_template.md" ".github\" -Force
    Move-Item -LiteralPath "docs\github-setup\workflows\ci.yml" ".github\workflows\" -Force
    Remove-IfExists "docs\github-setup"
}

Write-Host ""
Write-Host "Xong. Kiểm tra:  git status   rồi chạy test:  cd apps\api; pytest -q"
