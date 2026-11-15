# Báo cáo P0 — BYOK & dễ cài đặt: nền móng (ADR, config, mã hoá key, model + migration)

> **Ngày:** 2026-11-14 · **Phase:** P0/5 · **Commit:** `3a87936`
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` §7 (P0) · **ADR:** `docs/adr/0016-per-user-ai-provider-byok.md`

## Đã làm

| Hạng mục | File | Ghi chú |
|---|---|---|
| ADR 0016 | `docs/adr/0016-per-user-ai-provider-byok.md` | Nội dung theo §13 của kế hoạch, format theo ADR-0012 (Bối cảnh / Quyết định / Phương án loại / Hệ quả) |
| Config mới | `apps/api/src/quickassist/infrastructure/config.py` | 7 trường mới + `is_dev_login_allowed` hỗ trợ `AUTH_MODE=local` + validator CSV cho allowlist |
| Mã hoá key | `apps/api/src/quickassist/infrastructure/ai_keys.py` | AES-GCM: `nonce(12) ‖ ciphertext ‖ tag`, AAD = `user_id.bytes`; HKDF-SHA256 (salt `quickassist`, info `ai-keys-v1`) từ `AI_KEY_SECRET` → fallback `JWT_SECRET` |
| Model | `apps/api/src/quickassist/data/models/user_ai_settings.py` (+ đăng ký `data/models/__init__.py`) | PK = user_id, 2 CHECK constraint đặt tên khớp migration qua naming convention |
| Migration | `apps/api/migrations/versions/20261114_0003_user_ai_settings.py` | revision `0003` ← `0002`; chỉ thêm bảng, rollback = drop table |
| Dependency | `apps/api/pyproject.toml` | `cryptography>=42` (đã có sẵn 50.0.2 trong venv qua `pyjwt[crypto]`) |
| Test tối thiểu | `apps/api/tests/unit/infrastructure/test_ai_keys.py` | 7 test: roundtrip, nonce khác nhau, AAD-binding (InvalidTag), derive ổn định, fallback JWT, config defaults, dev-login ở local mode |

## Verify

- ✅ `pytest tests/unit tests/architecture` → **164 passed** (trước đó 156, +7 test mới, +1 architecture)
- ✅ `ruff check src tests migrations` → sạch
- ✅ `alembic history` → chuỗi `0001 → 0002 → 0003 (head)` nạp đúng
- ✅ DDL compile từ model khớp nguyên văn SQL migration (kiểu cột, PK, FK CASCADE, tên CHECK)
- ⚠️ **Chưa chạy migration trên Postgres thật** — môi trường này không có Docker/Postgres; sẽ tự verify khi có `TEST_DATABASE_URL` (integration test conftest đã sẵn cơ chế `_migrated`)

## Quyết định nhỏ trong phase

- Tên CHECK constraint trong model đặt `name="mode"` / `name="byok"` (không kèm prefix bảng) để naming convention `ck_%(table_name)s_%(constraint_name)s` sinh ra đúng tên `ck_user_ai_settings_mode` / `ck_user_ai_settings_byok` như SQL trong kế hoạch.
- `.env.example` **chưa sửa** — theo xác nhận của user, dời về P5.
- Test viết kèm phase (chỉ phần chứng minh `ai_keys` + config hoạt động), test tổng hợp dồn về P5 — theo xác nhận của user.

## Rủi ro / việc mở

- Không có việc nào ngoài kế hoạch. Không đụng file ngoài scope P0.

## Tiếp theo (P1)

Resolver + cache provider per-user, canonical dimension 1536, sửa 2 adapter, `AIProviderDep`, guard fingerprint trong indexing job.
