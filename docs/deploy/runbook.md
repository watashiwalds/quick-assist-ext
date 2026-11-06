# H04 / H07 — Runbook triển khai & vận hành QuickAssist

> Owner: Trịnh Mạnh Quang (phối hợp Mai Đức Vinh) · Mục tiêu nghiệm thu: triển khai mới từ tài liệu này trong **< 30 phút**.
> Kiến trúc vật lý: SDS v1.1 §4.2 — Caddy (HTTPS) → API (FastAPI) + Worker → PostgreSQL 16 + pgvector, cùng 1 Docker image.

## 0. Chuẩn bị (một lần)
| Cần có | Ghi chú |
|---|---|
| VPS Ubuntu 22.04+, 2 vCPU / 2 GB RAM / 20 GB SSD | đủ cho tải demo (SDS §4.5) |
| Tên miền trỏ bản ghi **A** về IP VPS | ví dụ `api.quickassist.example.com` |
| Mở cổng 80, 443 (đóng 5432) | `ufw allow 80,443/tcp && ufw enable` |
| Docker Engine + Compose plugin | `curl -fsSL https://get.docker.com \| sh` |
| Google OAuth client (Web application) | redirect URI `https://<EXTENSION_ID>.chromiumapp.org/` |
| OpenAI API key | đặt hạn mức chi tiêu tháng trên dashboard OpenAI |

## 1. Lần đầu triển khai (~15 phút)
```bash
git clone https://github.com/watashiwalds/quick-assist-ext.git && cd quick-assist-ext
git checkout <tag RC, ví dụ v1.0.0-rc1>
cp infra/.env.prod.example infra/.env.prod && chmod 600 infra/.env.prod
# Điền DOMAIN, ACME_EMAIL, POSTGRES_PASSWORD, JWT_SECRET (≥32 ký tự), GOOGLE_*, OPENAI_API_KEY,
# CORS_ORIGINS + OAUTH_ALLOWED_REDIRECT_URIS theo Extension ID cố định.
python3 -c "import secrets;print(secrets.token_urlsafe(48))"   # dùng cho JWT_SECRET / POSTGRES_PASSWORD
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps    # tất cả "healthy"/"running"
```
Thứ tự khởi động do compose đảm bảo: `db` (healthy) → `migrate` (alembic upgrade head) → `api` (healthy) → `caddy`, `worker`, `backup`.

App **từ chối khởi động** ở `APP_ENV=prod` nếu: JWT_SECRET yếu/mặc định, ENABLE_DEV_LOGIN bật, CORS không phải `chrome-extension://…` (H02).

## 2. Kiểm tra sau triển khai (H07, < 1 phút)
```bash
cd apps/api && pip install httpx
python scripts/smoke_test.py --base https://$DOMAIN                       # phần công khai
SMOKE_ACCESS_TOKEN=<token> python scripts/smoke_test.py --base https://$DOMAIN   # đủ luồng
```
Lấy `<token>`: đăng nhập extension → DevTools của service worker → `chrome.storage.session.get('qa.access')`. Kết quả mong đợi: tất cả ✅ (lưu < 2 s, tìm < 3 s, worker READY).

Sau đó chạy checklist demo trong [`../demo-script.md`](../demo-script.md) §1.

## 3. Cập nhật phiên bản
```bash
git fetch --tags && git checkout <tag mới>
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
python apps/api/scripts/smoke_test.py --base https://$DOMAIN
```
Migration chạy tự động bằng service `migrate` trước khi API mới nhận request. Migration phải tương thích ngược 1 phiên bản (thêm cột nullable trước, xoá cột ở bản sau).

## 4. Quay lui (rollback)
1. `git checkout <tag cũ>` rồi `up -d --build` như §3.
2. Nếu bản mới có migration phá vỡ: `docker compose ... run --rm migrate alembic downgrade <revision cũ>` **trước** khi chạy image cũ (CI đảm bảo mọi migration có downgrade).
3. Mất dữ liệu → khôi phục backup (§6).

## 5. Vận hành hằng ngày
| Việc | Lệnh / nơi xem |
|---|---|
| Log JSON (có `request_id`) | `docker compose ... logs -f api worker` — tra lỗi người dùng báo bằng "Mã lỗi" hiển thị trên extension |
| Hàng đợi bị kẹt | `docker compose ... exec db psql -U $POSTGRES_USER -c "select status,count(*) from jobs group by 1"` |
| Job DEAD | `select id,kind,last_error from jobs where status='DEAD' order by updated_at desc limit 20;` → sửa nguyên nhân → `update jobs set status='QUEUED',attempts=0,run_after=now() where id=…` |
| Quota giữ chỗ bị treo | worker tự hoàn mỗi 5 phút (`quota_stale_released` trong log) |
| Scale worker | `docker compose ... up -d --scale worker=3` (an toàn nhờ `SKIP LOCKED`) |
| Hết hạn mức OpenAI / 429 | log `AI_PROVIDER_ERROR`; ghi chú chuyển FAILED → người dùng bấm "Thử lại AI" sau khi xử lý |
| Xoay vòng JWT_SECRET | đổi trong `.env.prod` → `up -d` → mọi người dùng đăng nhập lại (chấp nhận được) |

## 6. Sao lưu & khôi phục
Service `backup` chạy `infra/backup.sh` mỗi 24 giờ → `infra/backups/quickassist_<UTC>.dump`, giữ `BACKUP_KEEP_DAYS` (14) ngày. **Sao chép thư mục này ra ngoài VPS** (ví dụ `rclone` lên Google Drive của nhóm) — backup nằm cùng máy không chống được mất máy.

Khôi phục (đã diễn tập trên môi trường dev):
```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod stop api worker
docker compose ... exec -T db pg_restore --clean --if-exists --no-owner -U $POSTGRES_USER -d $POSTGRES_DB < infra/backups/quickassist_<ts>.dump
docker compose ... start api worker && python apps/api/scripts/smoke_test.py --base https://$DOMAIN
```

## 7. Sự cố thường gặp
| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Extension báo "Không kết nối được máy chủ" | CORS sai Extension ID / Caddy chưa có chứng chỉ | kiểm `CORS_ORIGINS`; `docker compose logs caddy` |
| Đăng nhập Google lỗi `OAUTH_REDIRECT_INVALID` | redirect URI chưa khai báo | thêm `https://<ID>.chromiumapp.org/` vào Google Console **và** `OAUTH_ALLOWED_REDIRECT_URIS` |
| Ghi chú kẹt PROCESSING | worker không chạy | `docker compose ... ps worker`, xem log |
| `/health/ready` 500 | DB chưa sẵn sàng / sai mật khẩu | `docker compose ... logs db migrate` |

## 8. Trạng thái thực hiện (08/10/2026)
- [x] Compose prod + Caddy HTTPS + backup + `.env.prod.example` (`docker compose config` hợp lệ).
- [x] Image chạy user không phải root, filesystem read-only, `no-new-privileges`.
- [x] Smoke test 11 bước — **đạt 11/11** trên môi trường dev (API + worker + PostgreSQL/pgvector chạy thật, AI mock).
- [ ] Thuê VPS + tên miền, chạy §1 trên cloud và smoke test với OpenAI thật — **cần tài khoản/chi phí của nhóm**.
