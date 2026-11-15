# Báo cáo P5 — BYOK hardening, test & tài liệu

> **Ngày:** 2026-11-15 · **Phase:** P5/5 (cuối) · **Base:** `son-test-dev` tại `6e4f09a`
> **Kế hoạch:** `docs/self_sustained/byok-ease-P5-guide.md` (§3–§11) · **Guide:** triển khai theo
> đúng thứ tự commit §13, mỗi slice 1 commit + test + verify.

## Kết quả tổng (Definition of Done)

| Hạng mục | Kết quả |
|---|---|
| API `ruff check src tests migrations scripts` | ✅ sạch |
| API `pytest -q` **có** PostgreSQL 16 + pgvector (`TEST_DATABASE_URL`) | ✅ **348 passed** (339 baseline sau S1 + 9 test mới của P5; 0 failed, 0 skip ngoài lý do môi trường) |
| API `pytest -q` không DB | ✅ 205 passed, 143 skipped (integration skip vì thiếu DB — đúng kỳ vọng) |
| `alembic upgrade head → check → downgrade base → upgrade` | ✅ sạch; **`alembic check` giờ xanh** (0004 sửa lệch CHAR(64)/String(64)) |
| `export_openapi.py --check` | ✅ khớp; diff OpenAPI thuần additive (`embedding_dim`) |
| Extension `npm test -- --run` | ✅ **183 passed** (173 baseline + 10 test mới) |
| `npx tsc --noEmit` / `npm run build` / `npm run check:bundle` | ✅ sạch / OK / đạt |
| Working tree | ✅ sạch, chỉ các file dự kiến |

## Đã làm (9 slice = 9 commit)

### S1 — Sửa 14 test integration (`67a3357`)
- chat/page-match/summary: override `get_user_ai_provider` (presentation.api.deps) thay vì
  `get_ai_provider` — **tất cả** occurrence kể cả test đang pass.
- indexing_job: helper `_patch_ai` patch `AISettingsService.provider_for` (async) thay vì
  `monkeypatch.setattr(indexing_job, "get_ai_provider", ...)` (attribute không còn → AttributeError).
- `test_ai_settings_rebuild`: `/ai/search` → `/search`. `test_security`: thêm `/auth/config` vào PUBLIC.
- Kết quả: **14 đỏ → xanh, 339 passed**. Không nới lỏng assertion nào.

### S2 — SSRF allowlist (`931b6c6`)
- `_parse_http_url` chuẩn hoá (scheme, host lowercase, port (mặc định 443/80), path rstrip "/"),
  chặn userinfo/query/fragment/backslash/whitespace/port lỗi; `_allowlist_match` so khớp
  scheme+host+port + path **theo biên segment**.
- Chặn đủ 6 case bypass: `api.openai.com.evil.com`, userinfo `api.openai.com@evil.com`,
  sai port `:8443`, sai scheme `http://`, `/v1evil` (biên segment), `/v2` (sai path).
- `Settings._valid_allowlist`: entry hỏng → fail-fast khi load (test với `file:///etc/passwd`,
  userinfo, query → `ValidationError`).
- `main._check_config`: **warning** (không raise) khi prod + allowlist rỗng.
- Tồn dư (đã ghi ADR-0016 + runbook): DNS rebinding chưa chặn; redirect không phải bypass
  (httpx không follow mặc định); path allowlist chỉ là ràng buộc cấu hình, host/port mới là ranh giới.

### S3 — Chặn model embedding >1536 khi lưu (`8599f53`)
- `/test` trả thêm `embedding_dim` (top-level, kể cả khi >1536/ok=false).
- `AISettingsIn.embedding_dim` (advisory, `ge=1 le=100_000`): server từ chối >1536
  (`AI_CONFIG_INVALID`); không gửi vẫn lưu được — guard cuối là `CanonicalEmbeddingProvider`.
- ProviderCard: `testedFor` = signature (provider, base_url, embedding_model); >1536 → banner đỏ
  + **disable Lưu** + toast; chưa test/đổi form sau test → banner cảnh báo nhưng vẫn cho lưu;
  gửi `embedding_dim` chỉ khi test khớp form (`testInput` không gửi — `AISTestIn extra=forbid`);
  reset sau save. Regen `openapi.json` + `schema.d.ts` (additive).
- Test: API (4096→400, 768→200, không gửi→200), unit `_validate`, 3 test UI mới.

### S4 — Copy quota BYOK đúng D6 (`7645461`)
- Bỏ copy sai "không giới hạn bởi hạn mức server" → "lời gọi AI **vẫn tính vào** hạn mức của
  server… bấm 'Đặt lại số liệu' bất cứ lúc nào".
- Banner "Đã hết hạn mức" hiện cho **cả BYOK** (kèm gợi ý reset). Giữ nút reset + nhãn
  "Đã dùng (key của bạn)". Test: 3 case (byok hết mức / server hết mức / byok còn mức).

### S5 — `applied_fingerprint` + migration 0004 + worker repair (`b78ac62`)
- Migration 0004: thêm cột `applied_fingerprint VARCHAR(64)` + backfill cho `mode='byok'`
  (inherit để NULL — không rebuild toàn bộ user cũ); sửa luôn lệch kiểu
  `embedding_fingerprint` CHAR(64)→VARCHAR(64) → `alembic check` xanh.
- Save/delete: đọc row cũ **trước** upsert; `rebuild_required` dựa trên `applied_fingerprint`
  (row None/byok chưa theo dõi fp → theo mode; còn lại so applied ≠ new fp). Không rebuild →
  set `applied_fingerprint = new_fp` cùng upsert. Inherit save/delete giờ **ghi**
  `embedding_fingerprint = server_fp`. Rename `SaveResult.fingerprint_changed` → `rebuild_required`.
- `start_rebuild`: guard `fingerprint_is_current` (save cũ không đè save mới) +
  `mark_applied` **trước commit** (cùng transaction mark + enqueue).
- Worker: `_repair_once()` lúc khởi động + mỗi 300s trong `housekeeping`, bọc try/except.
- **⚠️ Lệch so với guide (có chủ đích):** guide gợi ý `rebuild.py` import trực tiếp
  `UserAISettingsRepository`, nhưng test kiến trúc của repo **L4** (service chỉ được dùng repo
  thuộc quyền sở hữu) và **L5** (business không viết SQL trực tiếp) chặn cả hai. Giải pháp: query
  mismatch + mark_applied/set_inherit/fingerprint_is_current nằm ở `UserAISettingsRepository`
  (data_access), `rebuild.py` gọi qua **public API `AISettingsService`** — đúng intent của guide
  (không phụ thuộc vòng, không SQL trong business) và pass đủ L4/L5. Test kiến trúc xanh.
- Test: 4 integration (`test_rebuild_repair.py`): crash giả lập → repair enqueue + applied cập
  nhật; re-save cùng config sau crash → `rebuild_required=True`; `start_rebuild(fp cũ)` → notes=0,
  không mark PROCESSING, không enqueue; inherit repair dùng server fp + save inherit lần nữa → False.
  3 unit đổi tên/mở rộng (`test_rebuild_required_semantics`, `…_applied_stale`, `test_delete_…`).

### S6 — BYOK stub end-to-end (`cb85395`)
- `test_byok_stub.py`: `ThreadingHTTPServer` thật trên `127.0.0.1:0` (HTTP/1.0, SSE stream,
  usage trả đủ) — **không monkeypatch internals**, đi qua đúng httpx + adapter.
- Chứng minh: indexing/rebuild dùng đúng `Bearer sk-test-1` + base_url của user; body
  `/embeddings` **không chứa `dimensions`**; vector 768 được pad → `vector_dims = 1536`;
  search/summary (`Tóm tắt từ stub.`)/RAG SSE (sources→delta→done)/page-match chạy qua stub;
  **xoay key** → `rebuild: null`, note vẫn READY, request mới dùng `Bearer sk-test-2`;
  `GET /me/ai-settings` không chứa `sk-test-` (chỉ `has_key` + `key_hint`).

### S7 — UI test local mode & quota (`9446052`)
- `auth-gate.test.tsx`: local mode (chưa đăng nhập) → không nút Google, có "Kết nối lại server"
  → bấm gọi `auth/status` (background tự dev-login); google mode → nút Google → `auth/login`;
  SettingsView ẩn "Đăng xuất" khi local, hiện khi google.
- (Quota BYOK: 3 test ở S4; >1536/untested/dim: 3 test ở S3.)

### S8 — Docs, env, ADR, đính chính (`1f77d7d`)
- `.env.example` ×2 + **khôi phục `infra/.env.prod.example`** (từ `51d0785`) + 6 biến P5 kèm
  comment tiếng Việt; note cạnh `AI_TIMEOUT_SECONDS` ("config mặc định 90s; file mẫu 30s cho dev").
  `docker compose -f infra/docker-compose.prod.yml config` hợp lệ (verify với giá trị test).
- README: mục 4 BYOK, mục 5 self-host `AUTH_MODE=local` (cảnh báo không xác thực), mục 6 bảng
  6 biến mới + link runbook/user-guide.
- Runbook §5.5 "BYOK & local mode": mã hoá key/xoay `AI_KEY_SECRET`, allowlist, local mode,
  quota D6, rebuild repair (+ SQL kiểm tra), stream ngắt, bảng 5 mã lỗi.
- User-guide §9.1: card Nhà cung cấp AI, key nằm server, BYOK vẫn tính hạn mức + reset, đổi
  model embedding → rebuild N note, >1536 bị chặn/768 pad, local mode tin cậy, lưu giữa stream.
- ADR-0016: sửa điểm 5 (KHÔNG xoá chunk hàng loạt; `applied_fingerprint` + repair), thêm điểm 8
  hardening P5, cập nhật Hệ quả (rebuild lâu/crash được repair/allowlist rỗng còn tồn dư).
- Đính chính P3/P4 (đúng khung guide §10.7).

### S9 — CI & cổng cuối (`c0a9ab6`)
- `workflow_dispatch:` để chạy tay; job `api` thêm gate `pytest -q -m integration` (fail sớm nếu
  ai bỏ `TEST_DATABASE_URL`). Ưu tiên tiếp theo: **mở PR `son-test-dev` → `dev`** để CI chạy đủ
  3 job và bật required checks (việc repo-owner).

## Ma trận thủ công §12

| # | Case | Kết quả |
|---|---|---|
| 1 | OpenAI key thật | ⏳ **Chờ thao tác tay** (cần key thật, tốn phí) — luồng đã chứng minh bằng stub S6 |
| 2 | Gemini key thật | ⏳ Chờ thao tác tay — contract test S6 + unit dimension đã che |
| 3 | Ollama `nomic-embed-text` (768) | ⏳ Chờ thao tay — pad 768→1536 đã assert trong S6 (`vector_dims=1536`) |
| 4 | llama.cpp không key | ⏳ Chờ thao tay — luồng "lưu không key" có unit test (`api_key=""`→xoá) |
| 5 | Key sai → test lỗi 401 rõ; lưu vẫn được + cảnh báo | ✅ Tự động: unit `AITestOut` error path + UI "test lỗi → banner nhưng Lưu vẫn chạy" |
| 6 | Model 4096 chiều | ✅ Tự động: `/test` trả `embedding_dim=4096` + UI chặn Lưu + PUT 400 |
| 7 | Đổi embedding model → confirm N note, keyword search chạy, READY | ✅ Tự động: `test_full_rebuild_flow` + S6 |
| 8 | Đổi key giữa rebuild → job cũ bỏ | ✅ Tự động: fingerprint guard (indexing_job) + `start_rebuild` stale |
| 9 | `AUTH_MODE=local` | ✅ Tự động: AuthGate/SettingsView (S7) + API `/auth/config`; **cần 1 lần chạy tay trên máy bind localhost trước deploy** |
| 10 | `AUTH_MODE=google` luồng cũ | ✅ Tự động: e2e hiện có + S7 |
| 11 | Allowlist chặn | ✅ Tự động: 9 case bypass + fail-fast entry hỏng + warning prod (log) |
| 12 | Quota BYOK | ✅ Tự động: 3 test UI (S4) + integration reset byok (P2) |
| 13 | Lưu cấu hình giữa stream | ⚠️ Đã chấp nhận (runbook ghi rõ); test đơn giản hoá chưa làm |
| 14 | Crash save→rebuild | ✅ Tự động: 4 test `test_rebuild_repair.py` |

## Tồn dư / khuyến nghị

1. Ma trận #1–#4: chạy tay với key thật trước khi phát hành (ghi kết quả bổ sung vào báo cáo này).
2. `AI_BASE_URL_ALLOWLIST` rỗng ở prod chỉ warning — nên đặt allowlist khi triển khai thật.
3. DNS rebinding + đóng cửa sổ hẹp "job A ghi chunk cũ sau khi B xong" (cần điều kiện `index_rev`
   trong `replace_for_note`) — ngoài phạm vi P5, đã ghi ADR-0016.
4. PR `son-test-dev` → `dev` + required checks `api`/`extension`/`e2e` (repo-owner).
