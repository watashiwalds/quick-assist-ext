# Báo cáo nghiệm thu trước P5 — BYOK & dễ cài đặt (P0–P4)

> **Ngày:** 2026-11-15 · **Nhánh:** `son-test-dev` (22 commit chưa push) · **Phạm vi:** P0–P4
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` · **ADR:** `docs/adr/0016-per-user-ai-provider-byok.md`
> **Đường dẫn:** yêu cầu ban đầu là `docs/self-sustained/reports/…`; repo dùng `docs/self_sustained/reports/`
> → báo cáo đặt tại đây để khớp quy ước hiện có.

## 1. Kết luận

P0–P4 đã hoàn thành đúng kiến trúc đã chốt: resolver per-user, cache theo user, canonical 1536,
rebuild theo fingerprint, CRUD + test endpoint, card BYOK và local mode. Người dùng **không cấu hình**
không bị đổi hành vi: 202 passed + 137 skipped khi không có DB, ruff sạch.

Tuy nhiên **chưa đủ điều kiện coi là nghiệm thu xong**:

- 5 lỗi sản phẩm/UX: 4 cần sửa (SSRF allowlist, lưu model >1536, copy quota BYOK, save→rebuild
  không nguyên tử); 1 chấp nhận + ghi tài liệu (provider bị đóng khi đang stream).
- **14 test integration đỏ** trên PostgreSQL thật. Đây là lỗi bảo trì test (monkeypatch/URL cũ),
  không phải regression sản phẩm — nhưng báo cáo P3/P4 đang mô tả sai trạng thái xanh.
- **`alembic check` đỏ ở head**: migration 0003 tạo `embedding_fingerprint CHAR(64)` nhưng model
  khai `String(64)`; CI sẽ fail ở bước migration dù test đã xanh.
- Thiếu test BYOK stub cố định, thiếu UI test cho local mode/quota, thiếu tài liệu BYOK/local mode,
  thiếu 6 biến môi trường trong `.env.example`, và `infra/.env.prod.example` bị thiếu trên branch.
- CI đã có job integration + PostgreSQL, nhưng branch chưa push/PR nên CI chưa từng chạy P0–P4.

Báo cáo này chốt 9 quyết định của người dùng cho P5 (§6) và bàn giao hướng dẫn độc lập tại
`docs/self_sustained/byok-ease-P5-guide.md`.

## 2. Bằng chứng kiểm chứng

| Hạng mục | Lệnh / cách kiểm | Kết quả |
|---|---|---|
| API không DB | `apps/api/.venv/bin/pytest -q` | **202 passed, 137 skipped** (6,65s); ruff `All checks passed` |
| API có DB thật | `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test .venv/bin/pytest -q` | **14 failed, 325 passed** (93,5s) |
| API sau khi áp 14 fix dự kiến | sửa tạm working tree rồi chạy lại toàn bộ | **339 passed** (132s); đã `git checkout` hoàn nguyên |
| Extension | `npm test`, `npx tsc --noEmit` | **173 passed / 16 files**; tsc sạch |
| Bundle | `npm run check:bundle` | ✅ 11 tệp, quyền tối thiểu |
| Contract | `python scripts/export_openapi.py --check` + `npm run gen:api:file` | ✅ khớp, không diff |
| Migration | `alembic check` trên DB test | ❌ `CHAR(64)` vs `String(64)` ở `embedding_fingerprint` |
| SSRF | allowlist `https://api.openai.com`, gọi `validate_base_url` | chấp nhận `https://api.openai.com.evil.com/v1` và `https://api.openai.com@evil.com/v1` |
| SSE | `provider_cache.invalidate_user` giữa stream | tái hiện `httpx.ReadError` ở stream đang chạy |
| Stub BYOK tạm | stub OpenAI-compatible 768 chiều, chạy E2E | **1 passed**: summary/search/RAG/indexing + xoay key không rebuild; đã xoá, repo sạch |
| P3 rebuild | đổi `/ai/search` → `/search` trong test | **6 passed**; đã hoàn nguyên file |

> **Đính chính số liệu P3/P4:** “202 passed” trong P3/P4 là chạy **không có** `TEST_DATABASE_URL`
> (137 integration bị skip). Với DB thật, suite đỏ 14 test. P3 còn claim integration xanh, nhưng
> `test_full_rebuild_flow` gọi sai URL `/ai/search` (đúng là `/search`) nên chưa từng xanh trên DB.

## 3. Đánh giá theo 5 trục

### 3.1 Correctness

- **Đúng:** fingerprint `sha256(provider|base_url|embedding_model)`; đổi key/chat model không rebuild;
  zero-pad 768→1536 giữ cosine; guard fingerprint 2 lần trong indexing job; job stale bị bỏ (DONE,
  không DEAD); key rotation dùng provider mới ngay.
- **Sai/lệch:** lưu cấu hình >1536 vẫn thành công (chỉ `/test` từ chối) — trái D3 và tiêu chí #5;
  copy quota BYOK nói “không giới hạn” nhưng backend vẫn chặn — trái D6; save commit trước rebuild
  nên crash giữa chừng để lại config mới + chunk cũ, và lưu lại cùng config không tự sửa.
- **Test:** 14 test integration đỏ vì target cũ, không phản ánh sản phẩm; sau khi sửa đúng target
  toàn bộ 339 test xanh.

### 3.2 Readability

- Chú thích quyết định (giữ chunk cũ, vì sao không xoá) rất tốt; docstring `ProviderCache`,
  `CanonicalEmbeddingProvider`, `start_rebuild` giải thích đúng lý do.
- Còn chú thích lỗi thời: `validate_base_url` ghi “khớp prefix”, `config.py` ghi “khớp prefix”;
  ADR-0016 điểm 5 vẫn ghi “xoá note_chunks” — cần sửa cùng P5.
- UI `ProviderCard` dùng derived state + comment rõ semantics key (`null` giữ, `""` xoá); test UI
  đóng vai tài liệu hành vi.

### 3.3 Architecture

- **Đúng:** resolver là seam duy nhất cho API + worker; controller nối `AISettingsService` với
  `start_rebuild` để tránh import vòng; cache key chứa `user_id` + hash key; contract additive.
- **Nợ:** save và rebuild là 2 transaction rời; vòng đời provider bị đóng (qua task) khi invalidate;
  quota semantics bị chia giữa backend (chặn) và UI (hứa không chặn); chưa có cơ chế repair.
- `enqueue_many` đã batch 500 dòng/INSERT — phù hợp thư viện lớn; search vẫn trả chunk cũ trong
  rebuild (trade-off đã chấp nhận).

### 3.4 Security

- **Critical:** allowlist dùng `startswith` trên chuỗi URL → bypass host (`api.openai.com.evil.com`)
  và userinfo (`api.openai.com@evil.com`); không có cảnh báo khi allowlist rỗng ở `APP_ENV=prod`
  (trái §10 kế hoạch).
- **Tốt:** AES-GCM với AAD = `user_id`; response chỉ `has_key` + 4 ký tự cuối; cache tách user;
  không log key; prod check `JWT_SECRET`/CORS/dev-login; local mode log warning.
- **Tồn dư:** allowlist rỗng = cho phép mọi http(s), kể cả metadata IP; DNS rebinding vẫn có thể
  vượt allowlist host; local mode **không có xác thực**; xoay `JWT_SECRET` khi chưa đặt
  `AI_KEY_SECRET` làm key cũ không giải mã được (đã có mã lỗi `AI_KEY_UNREADABLE`).

### 3.5 Performance

- Cache LRU 64, khoá theo config + key; mỗi lời gọi AI có 1 query đọc row (chấp nhận được).
- Rebuild enqueue theo lô 500; mark toàn bộ note PROCESSING; search không bị chặn.
- `/test` tạo client mới rồi đóng, timeout 30s, rate limit 6/phút — hợp lý.
- Không thấy regression hiệu năng trong test; thư viện rất lớn sẽ rebuild lâu (đã có banner, không
  poll tiến độ thật — ngoài phạm vi P5).

## 4. Danh sách phát hiện

| ID | Mức | Vùng | Phát hiện | Bằng chứng |
|---|---|---|---|---|
| I1 | **Critical** | Security | `validate_base_url` so khớp `startswith` → bypass allowlist bằng host giả/userinfo; không cảnh báo khi allowlist rỗng ở prod | `ai_settings/service.py:114-123`; probe §2 |
| I2 | **Required** | Correctness | Lưu cấu hình embedding >1536 thành công; chỉ `/test` từ chối; UI không cảnh báo trước khi lưu cấu hình chưa test | `service.py:_validate/save`; `ProviderCard.onSave` |
| I3 | **Required** | UX/Correctness | SettingsView nói BYOK “không giới hạn bởi hạn mức server” và ẩn banner hết hạn mức, nhưng `QuotaService` vẫn chặn (đúng D6) | `SettingsView.tsx:90-96`; `quota_service.py:78` |
| I4 | Optional | Reliability | `provider_cache.invalidate_user`/evict schedule đóng provider (qua task) ngay cả khi đang có stream SSE dùng nó → stream nhận `httpx.ReadError`; không phải đóng đồng bộ trong request | tái hiện §2; `openai/__init__.py:_schedule_close` |
| I5 | **Required** | Reliability | Save commit trước `start_rebuild`; crash giữa chừng để lại config mới + chunk cũ; lưu lại cùng config không rebuild vì fingerprint không đổi | `ai_settings_controller.py:59-70`; `service.py:save` |
| I6 | **Required** | Verification | 14 test integration đỏ vì monkeypatch `get_ai_provider`, URL `/ai/search`, PUBLIC thiếu `/auth/config` | danh sách §5 |
| I7 | **Required** | Traceability | P3/P4 báo cáo xanh nhưng thực tế skip/đỏ; ADR-0016 điểm 5 còn ghi xoá `note_chunks` (P3 đã chốt giữ) | `reports/byok-ease-P3.md`, `P4.md`, `adr/0016:29` |
| I8 | **Required** | Ops | 2 file `.env.example` thiếu 6 biến mới; `infra/.env.prod.example` được runbook tham chiếu nhưng không có trên branch | grep env; `ls infra/`; `git show 51d0785` |
| I9 | **Required** | Docs | README/runbook/user-guide chưa có BYOK, `AUTH_MODE=local`, `AI_KEY_SECRET`, allowlist, rebuild repair | grep tài liệu |
| I10 | **Required** | Tests | Chưa có test BYOK stub cố định; chưa có UI test local mode/quota/BYOK >1536 | chỉ có stub tạm đã xoá; `tests/ui` |
| I11 | **Required** | Process | CI có job integration + Postgres nhưng branch chưa push/PR; `on.push` chỉ main/dev | `.github/workflows/ci.yml`; `git rev-list` 22 |
| I12 | **Required** | Verification | `alembic check` đỏ ở head: 0003 `CHAR(64)` vs model `String(64)`; CI fail dù test xanh | `alembic check` trên DB test §2 |
| F1 | FYI | Security | `AUTH_MODE=local` cho phép dev-login bất kể `APP_ENV` (đúng thiết kế) → phải bind localhost/proxy auth | `config.py:is_dev_login_allowed`; `main.py:36` |
| F2 | FYI | Security | `check-bundle` đã nới lỏng chuỗi `/auth/dev-login` cho local mode; server vẫn chặn khi không bật | P4 report |
| F3 | FYI | Docs | `.env.example` đặt `AI_TIMEOUT_SECONDS=30`, config mặc định 90 — tài liệu cần nói rõ | `config.py:60`; env |
| F4 | FYI | UX | Local mode ẩn Đăng xuất (tránh tự đăng nhập lại) nhưng cũng mất lối xoá cache chat trên máy; cân nhắc P6 | `SettingsView.tsx:150` |
| F5 | FYI | Performance | Rebuild đánh PROCESSING + enqueue toàn bộ note; thư viện lớn sẽ lâu, không có % tiến độ thật | `rebuild.py`; P4 report |

## 5. Chi tiết 14 test integration đỏ

| Nhóm | Test | Nguyên nhân | Fix P5 |
|---|---|---|---|
| Rebuild | `test_ai_settings_rebuild.py::test_full_rebuild_flow` | gọi `/ai/search`; route đúng là `/search` | đổi URL |
| Chat (3) | `test_prompt_wraps_notes…`, `test_ai_error_mid_stream…`, `test_ai_error_before_any_text…` | override `get_ai_provider`; dependency mới là `get_user_ai_provider` | override đúng hàm |
| Page-match (4) | `test_segments_verified…`, `test_verify_failure…[error,garbage]`, `test_embed_failure…` | cùng nguyên nhân override | override đúng hàm |
| Summary (2) | `test_ai_error_releases_quota`, `test_unexpected_error_releases_quota` | cùng nguyên nhân override | override đúng hàm |
| Indexing (3) | `test_transient_error…`, `test_retries_exhausted…`, `test_permanent_error…` | monkeypatch `indexing_job.get_ai_provider`; job dùng `AISettingsService.provider_for` | patch `provider_for` (async) |
| Security (1) | `test_every_private_endpoint_requires_token` | PUBLIC thiếu `/auth/config` | thêm vào PUBLIC |

Đã kiểm chứng: áp đúng 6 nhóm fix trên → **14/14 passed**, toàn bộ suite **339 passed**; sau đó
hoàn nguyên working tree. Hướng dẫn chi tiết trong P5 guide §3.

## 6. Quyết định của người dùng cho P5

| # | Vấn đề | Quyết định |
|---|---|---|
| D-P5.1 | Phạm vi P5 | **Sửa hết + test + docs** (5 lỗi sản phẩm, 14 test, stub BYOK, docs/env/ADR) |
| D-P5.2 | Integration & CI | **Sửa 14 test + thêm CI gate** (đưa branch vào trigger/PR, chạy Postgres thật) |
| D-P5.3 | SSRF allowlist | **Khớp host chặt + cảnh báo prod**: parse scheme/host/port/path, từ chối userinfo; warning khi allowlist rỗng ở prod |
| D-P5.4 | Model >1536 | **Chặn khi lưu + cảnh báo UI**: server từ chối khi biết `embedding_dim`; UI chặn nếu test báo >1536, cảnh báo nếu chưa test |
| D-P5.5 | Copy quota BYOK | **Sửa copy + hiện banner**: BYOK vẫn bị hạn mức (đúng D6), giữ nút “Đặt lại số liệu” |
| D-P5.6 | Provider đóng khi stream | **Chấp nhận + ghi tài liệu**: không sửa code, ghi rõ stream có thể bị ngắt khi lưu/xoá cấu hình |
| D-P5.7 | Save→rebuild | **Thêm cơ chế repair**: lưu `applied_fingerprint`, retry khi khởi động/lưu lại; test crash giả lập |
| D-P5.8 | ADR & báo cáo cũ | **Sửa ADR + đính chính P3/P4** |
| D-P5.9 | Docs & env | **Bổ sung đầy đủ**: README, runbook, user-guide, 2 `.env.example`, khôi phục `infra/.env.prod.example`, cảnh báo local mode |

## 7. Trạng thái tiêu chí nghiệm thu (§11 kế hoạch)

| # | Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | User chưa cấu hình: test cũ xanh, không đổi hành vi | **Chưa đạt** | 202 passed không DB; 14 integration đỏ (test cũ) — P5 sửa |
| 2 | BYOK dùng đúng key/base URL cho summary/chat RAG/search/page-match/indexing, xác nhận bằng stub | **Đạt một phần** | Stub tạm chứng minh summary/search/RAG/indexing + key rotation; page-match chưa; chưa commit |
| 3 | Key không có trong response/log/chrome.storage | **Đạt** | Test API + UI; response chỉ `has_key`/`key_hint` |
| 4 | Đổi embedding model: confirm đúng số note, chunk thay dần, keyword search chạy, job xong | **Đạt một phần** | Flow đúng sau khi sửa URL test; crash window I5; search trả chunk cũ (đã chấp nhận) |
| 5 | 768 chiều lưu + search; >1536 bị từ chối rõ | **Chưa đạt** | 768 đạt; lưu >1536 vẫn thành công |
| 6 | Đổi key/chat model không rebuild | **Đạt** | Unit fingerprint + P3 integration |
| 7 | `AUTH_MODE=local` không cần Google; `google` không đổi | **Đạt một phần** | Backend + AuthGate + auto login; thiếu UI test commit + docs |
| 8 | BYOK reset được usage; inherit vẫn bị chặn | **Đạt một phần** | Backend đúng D6; copy/banner UI sai |
| 9 | `gen:api` sạch; kiến trúc extension xanh | **Đạt** | OpenAPI `--check` khớp; architecture test xanh |

## 8. Rủi ro còn lại & điều kiện chuyển P5

- **P5 được phép bắt đầu** với 9 quyết định ở §6; không cần chờ thêm quyết định sản phẩm.
- **SSRF:** allowlist vẫn là tuỳ chọn, mặc định rỗng = cho phép mọi http(s). P5 chỉ thêm warning
  prod + khớp host chặt; DNS rebinding và metadata IP vẫn là tồn dư — ghi runbook/ADR.
- **>1536:** server chỉ chặn khi client gửi `embedding_dim` đã test; API caller tự gửi thiếu vẫn
  lưu được. Guard cuối vẫn là `CanonicalEmbeddingProvider` lúc embed — ghi rõ trong tài liệu.
- **SSE:** lưu/xoá cấu hình hoặc evict cache giữa stream sẽ ngắt stream; người dùng bấm lại. Đã chốt
  chấp nhận, không sửa trong P5.
- **Local mode:** không có xác thực; bắt buộc bind `127.0.0.1` hoặc sau proxy có auth. Không bật
  mặc định.
- **Khoá mã hoá:** đặt `AI_KEY_SECRET` riêng; nếu để trống, xoay `JWT_SECRET` làm key cũ không
  giải mã được → user nhập lại (mã `AI_KEY_UNREADABLE`).
- **CI:** job integration đã tồn tại; P5 phải push branch/PR (hoặc thêm `workflow_dispatch` +
  trigger nhánh) để gate thực sự chạy. Ngoài ra `alembic check` đang đỏ ở head (`CHAR(64)` vs
  `String(64)`); migration 0004 phải sửa kiểu cột cũ, không chỉ thêm cột mới.
- **Rebuild repair:** cần migration mới (`applied_fingerprint`), worker quét định kỳ; không được
  xoá dấu “đã áp” của cấu hình mới hơn.
- **Search trong rebuild:** trả chunk cũ (đúng quyết định P3) — không phải lỗi; ghi user-guide.

## 9. Bàn giao

Hướng dẫn triển khai P5 độc lập (không cần đọc P0–P4):
**`docs/self_sustained/byok-ease-P5-guide.md`** — gồm thứ tự công việc, code fix cụ thể, test,
migration, docs/env/ADR, CI, ma trận thủ công và Definition of Done.
