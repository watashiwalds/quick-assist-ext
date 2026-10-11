# Chạy toàn bộ QuickAssist trên máy để tự dùng thử: DB + API + worker (Docker) và extension bản kiểm thử.
# Cách chạy: bấm đúp chay-thu.bat ở thư mục gốc repo (hoặc: powershell -ExecutionPolicy Bypass -File scripts\chay-thu.ps1)
# Tuỳ chọn: đặt khoá Gemini vào infra\gemini.key (1 dòng, đã gitignore) → tự dùng AI thật nếu khoá chạy được.
$ErrorActionPreference = 'Continue'  # lệnh docker/npm ghi tiến trình ra stderr — tự kiểm tra mã thoát
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$compose = @('compose', '-f', 'infra/docker-compose.yml')
function Step($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Done($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !!  $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  XX  $t" -ForegroundColor Red; Read-Host "`nNhấn Enter để đóng"; exit 1 }
function SetEnv($key, $value) {
  $lines = Get-Content infra\.env -Encoding UTF8
  if ($lines -match "^$key=") { $lines = $lines -replace "^$key=.*", "$key=$value" } else { $lines += "$key=$value" }
  [IO.File]::WriteAllLines((Join-Path $root 'infra\.env'), [string[]]$lines, (New-Object Text.UTF8Encoding $false))  # không BOM
}
function GetEnv($key) {
  $m = Get-Content infra\.env -Encoding UTF8 | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
  if ($m) { return ($m -split '=', 2)[1].Trim() } else { return '' }
}

Step '1/5 Kiểm tra Docker, Node'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'Chưa cài Docker Desktop: https://www.docker.com/products/docker-desktop/' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail 'Chưa cài Node.js 20+: https://nodejs.org/' }
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  docker info *> $null
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
  if ($i -eq 0) {
    Warn 'Docker chưa chạy — đang mở Docker Desktop, chờ tối đa 2 phút...'
    $dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) { Start-Process $dd }
  }
  Start-Sleep 2
}
if (-not $ok) { Fail 'Docker Desktop chưa sẵn sàng. Mở Docker Desktop rồi chạy lại.' }
Done 'Docker, Node sẵn sàng'

Step '2/5 Cấu hình infra\.env'
if (-not (Test-Path infra\.env)) { Copy-Item infra\.env.example infra\.env; Done 'Tạo infra\.env từ .env.example' }
$keyFile = 'infra\gemini.key'
# Có infra\gemini.key → luôn thử Gemini (khoá trong file là ý muốn của bạn; lỗi thì bước 3 tự quay về mock)
if (Test-Path $keyFile) {
  $k = (Get-Content $keyFile -Raw).Trim()
  if ($k) {
    if ((GetEnv 'GEMINI_API_KEY') -ne $k) { SetEnv 'GEMINI_API_KEY' $k; Done 'Cập nhật khoá Gemini từ infra\gemini.key' }
    SetEnv 'AI_PROVIDER' 'gemini'
  }
}
Done ("AI_PROVIDER=" + (GetEnv 'AI_PROVIDER'))

Step '3/5 Dựng backend (PostgreSQL + migrate + API + worker)'
docker @compose up -d --build
if ($LASTEXITCODE -ne 0) { Fail 'docker compose up lỗi (xem log ở trên). Cổng 5432/8000 có đang bị chiếm?' }
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { $r = Invoke-RestMethod http://localhost:8000/api/v1/health/ready -TimeoutSec 3; if ($r.status -eq 'ok') { $ready = $true; break } } catch {}
  Start-Sleep 2
}
if (-not $ready) { docker @compose logs --tail 40 api; Fail 'API không lên sau 2 phút (log ở trên).' }
Done 'API: http://localhost:8000/docs'

if ((GetEnv 'AI_PROVIDER') -eq 'gemini') {
  Write-Host '  ..  Kiểm tra khoá Gemini (gọi thử embedding + tóm tắt)...'
  $out = docker @compose exec -T api python scripts/check_ai.py --try-both 2>&1 | Out-String
  Write-Host $out
  if ($LASTEXITCODE -eq 0) {
    if ($out -match 'GEMINI_BASE_URL=(\S+)') { SetEnv 'GEMINI_BASE_URL' $Matches[1]; docker @compose up -d api worker | Out-Null; Done "Dùng endpoint $($Matches[1])" }
    if ($out -match 'GEMINI_CHAT_MODEL=(\S+)') { SetEnv 'GEMINI_CHAT_MODEL' $Matches[1]; docker @compose up -d api worker | Out-Null; Done "Dùng model $($Matches[1])" }
    Done 'Gemini dùng được — tóm tắt/tìm kiếm bằng AI thật'
  } else {
    SetEnv 'AI_PROVIDER' 'mock'
    docker @compose up -d api worker | Out-Null
    Warn 'Khoá Gemini chưa dùng được → tạm chuyển AI_PROVIDER=mock (AI giả lập). Xem lỗi ở trên.'
  }
}

Step '4/5 Build extension bản kiểm thử'
Push-Location apps\extension
if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE -ne 0) { Pop-Location; Fail 'npm ci lỗi' } }
npm run build:e2e
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail 'Build extension lỗi' }
Pop-Location
$dist = Join-Path $root 'apps\extension\dist-e2e'
Done "Extension: $dist"

Step '5/5 Nạp extension vào Chrome (bạn làm 1 lần)'
Set-Clipboard $dist
Write-Host @"
  1. Mở Chrome, gõ vào thanh địa chỉ:  chrome://extensions
  2. Bật "Developer mode" (góc phải trên) -> bấm "Load unpacked"
  3. Dán đường dẫn (đã copy sẵn vào clipboard) rồi chọn thư mục:
       $dist
     (lần sau chỉ cần bấm nút tải lại ↻ của QuickAssist)
  4. Bấm biểu tượng QuickAssist -> "Mở thư viện ghi chú" -> "Đăng nhập thử (bản kiểm thử)"
  5. Dùng thử theo bảng kịch bản: docs\HUONG-DAN-CHAY-VA-TEST.md (mục A4)

  Xem log backend:  docker compose -f infra/docker-compose.yml logs -f api worker
  Tắt backend:      docker compose -f infra/docker-compose.yml down
"@
Start-Process explorer.exe $dist
Read-Host "`nXong. Nhấn Enter để đóng cửa sổ (backend vẫn chạy nền)"
