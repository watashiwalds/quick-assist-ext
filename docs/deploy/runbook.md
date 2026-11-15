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

## 5.5 BYOK & local mode (P5, ADR-0016)

**Mã hoá key BYOK:** đặt `AI_KEY_SECRET` (≥32 ký tự ngẫu nhiên) **trước khi** user nhập key.
Xoay khoá này → key cũ không giải mã được (API trả `AI_KEY_UNREADABLE`), user phải nhập lại.
Để trống → derive HKDF từ `JWT_SECRET`: xoay `JWT_SECRET` khi rỗng cũng gây hiệu ứng tương tự —
đặt `AI_KEY_SECRET` riêng để xoay JWT an toàn.

**Allowlist base_url:** `AI_BASE_URL_ALLOWLIST` là CSV các prefix, so khớp **scheme + host +
port + path** theo biên segment (từ chối userinfo `https://host@evil.com`, sai port/scheme,
`host.evil.com`). Rỗng = cho phép mọi http(s) + **warning SSRF trong log prod** — nên đặt ở prod.
Tồn dư đã ghi nhận: DNS rebinding (host khớp nhưng resolve về IP nội bộ) chưa chặn; redirect
không phải đường bypass (httpx không follow mặc định).

**Local mode:** `AUTH_MODE=local` **bỏ xác thực** — chỉ bind `127.0.0.1` hoặc đặt sau proxy có
auth, không mở Internet; `APP_ENV=prod` không tự bật local. Logout bị ẩn trên extension
(dev-login tự chạy lại ngay).

**Quota BYOK:** lời gọi AI của user BYOK vẫn bị RESERVE→COMMIT và chặn như user thường (D6);
user BYOK được bấm "Đặt lại số liệu" (reset usage); banner hết hạn mức hiện cho cả BYOK.

**Rebuild repair:** worker quét `applied_fingerprint != embedding_fingerprint` lúc khởi động và
mỗi 5 phút — tự enqueue lại rebuild bị đứt (crash giữa save và rebuild). Nếu nghi kẹt, kiểm tra:

```sql
SELECT user_id, mode, embedding_fingerprint, applied_fingerprint
FROM user_ai_settings
WHERE embedding_fingerprint IS DISTINCT FROM applied_fingerprint;
```

Re-save cấu hình hoặc chờ worker; job stale tự bỏ nhờ fingerprint guard.

**Stream bị ngắt:** lưu/xoá cấu hình AI (hoặc evict cache) giữa lúc chat có thể làm stream dừng
(`httpx.ReadError`) — người dùng gửi lại câu hỏi. Hành vi đã chấp nhận ở P5.

**Mã lỗi thường gặp:**

| Mã | Nguyên nhân | Xử lý |
|---|---|---|
| `AI_CONFIG_INVALID` | base_url sai scheme/host/port (allowlist reject), model > 1536 chiều kèm `embedding_dim`, timeout ngoài [5,600] | user sửa cấu hình; xem message |
| `AI_KEY_UNREADABLE` | `AI_KEY_SECRET`/`JWT_SECRET` đã xoay | lỗi cấu hình (không phải user) — user nhập lại key |
| `AI_UNAVAILABLE` | endpoint AI không phản hồi/lỗi | kiểm tra endpoint của user hoặc server provider |
| `QUOTA_EXCEEDED` | hết hạn mức (cả BYOK) | user bấm "Đặt lại số liệu" (BYOK) hoặc chờ reset |
| `RESET_NOT_ALLOWED` | user server-mode bấm reset khi không được phép | chỉ BYOK/demo được reset |

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
