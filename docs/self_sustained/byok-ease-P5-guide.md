# P5 — Hướng dẫn triển khai: BYOK hardening, test & tài liệu

> **Tính độc lập:** tài liệu này đủ để làm P5 mà không cần đọc báo cáo P0–P4. Chỉ cần branch
> `son-test-dev` tại commit `6e4f09a` (hoặc mới hơn) và môi trường chạy được API + extension.
> **Ước lượng:** 1,5–2 ngày (kế hoạch ghi 1 ngày; cộng thêm migration + test stub + docs).
> **Quy ước đường dẫn:** repo dùng `docs/self_sustained/` (gạch dưới), không phải `self-sustained`.

## 0. Definition of Done

- [ ] API: `ruff` sạch; `pytest` xanh khi có `TEST_DATABASE_URL` (PostgreSQL 16 + pgvector):
      **339 baseline** sau khi sửa 14 test + toàn bộ test mới của P5; không còn test integration nào
      bị skip ngoài lý do môi trường.
- [ ] Extension: `npm test` xanh (173 + test mới); `npx tsc --noEmit` sạch; `npm run build` OK;
      `npm run check:bundle` đạt.
- [ ] 14 test integration cũ được sửa đúng target (không nới lỏng assertion).
- [ ] Có test BYOK stub cố định, chứng minh summary/search/RAG/page-match/indexing dùng đúng
      key/base URL; xoay key không rebuild; response không lộ key.
- [ ] SSRF: allowlist khớp scheme+host+port+path; từ chối userinfo; có warning prod khi allowlist rỗng;
      test các case bypass.
- [ ] Lưu model >1536 bị chặn khi biết số chiều; UI chặn/cảnh báo; `/test` vẫn là lớp xác nhận.
- [ ] Copy quota BYOK đúng D6 (vẫn bị hạn mức, reset được); banner hết hạn mức hiện cho cả BYOK.
- [ ] `applied_fingerprint` + migration 0004 + worker repair; test crash giả lập và re-save cùng config.
- [ ] Migration 0004 chạy được `upgrade → check → downgrade base → upgrade`; sửa luôn lệch
      `CHAR(64)`/`String(64)` của `embedding_fingerprint`.
- [ ] Docs: README, runbook, user-guide; 2 `.env.example`; khôi phục `infra/.env.prod.example`;
      ADR-0016 sửa điểm 5; đính chính P3/P4.
- [ ] OpenAPI + `schema.d.ts` regen, không diff ngoài phần additive.
- [ ] CI xanh trên PR/nhánh (job `api` có Postgres thật + job `extension` + `e2e`).
- [ ] Ma trận thủ công §12 được chạy và ghi kết quả vào báo cáo P5.

## 1. Bối cảnh tối thiểu

### 1.1 Luồng hiện tại

```
Extension Settings (ProviderCard)
  │ RPC ai/config/get|set|test|reset
  ▼
Background  ──►  API /me/ai-settings (JWT)
                    │
                    ├─ user_ai_settings (key mã hoá AES-GCM, AAD = user_id)
                    ├─ AISettingsService.provider_for(user_id)
                    │     ├─ mode=inherit → provider toàn cục (get_ai_provider)
                    │     └─ mode=byok   → build_provider(cfg) + ProviderCache LRU 64
                    └─ fingerprint đổi → start_rebuild (mark PROCESSING + enqueue job)
                                              │
                                              ▼
                                   worker index_note → embed → note_chunks (vector 1536)
```

- **`mode=inherit`** là mặc định; không có row cũng tương đương. Deployment cũ không đổi hành vi.
- **Fingerprint** = `sha256(provider | base_url | embedding_model)`. Đổi **key** hoặc **chat model**
  không đổi fingerprint → không rebuild. Đổi provider/base_url/embedding model → rebuild.
- **Canonical 1536:** model trả <1536 chiều → zero-pad (cosine không đổi); >1536 → từ chối.
- **Quota (D6):** BYOK **vẫn** bị RESERVE→COMMIT và chặn như user thường; chỉ được phép
  “Đặt lại số liệu” (reset usage) vì tự trả tiền.
- **`AUTH_MODE=local`:** self-host một người, không cần Google OAuth. Đây là **không có xác thực**;
  chỉ dùng khi bind `127.0.0.1` hoặc sau proxy có auth.

### 1.2 Khái niệm P5 thêm

- **`applied_fingerprint`:** fingerprint của cấu hình đã được **bàn giao cho pipeline rebuild**
  (mark PROCESSING + enqueue trong cùng transaction). Khác với `embedding_fingerprint` (cấu hình
  hiện tại). Lệch nhau = lần save trước chưa kịp enqueue (crash) → worker repair enqueue lại.
  Cột này **không** theo dõi từng chunk; job lỗi giữa chừng do retry/stale của job đảm nhiệm.
- **`embedding_dim` trên PUT:** số chiều native client biết được từ `/test`; server dùng để từ chối
  sớm model >1536. Đây là **advisory**, không phải nguồn tin bảo mật; guard cuối vẫn là
  `CanonicalEmbeddingProvider`.

### 1.3 Bản đồ file

| Vùng | File chính |
|---|---|
| Resolver/cache | `apps/api/src/quickassist/infrastructure/openai/__init__.py`, `dimensions.py` |
| CRUD/validate | `apps/api/src/quickassist/business/ai_settings/service.py` |
| Controller | `apps/api/src/quickassist/presentation/api/v1/controllers/ai_settings_controller.py` |
| Schema | `apps/api/src/quickassist/presentation/schemas/ai_settings.py` |
| Rebuild | `apps/api/src/quickassist/business/semantic_search/rebuild.py`, `indexing_job.py` |
| Model/repo | `apps/api/src/quickassist/data/models/user_ai_settings.py`, `data_access/repositories/user_ai_settings_repository.py` |
| Worker | `apps/api/src/quickassist/worker.py` |
| UI | `apps/extension/src/ui/features/account/ProviderCard.tsx`, `SettingsView.tsx`, `AuthGate.tsx` |
| Test | `apps/api/tests/integration/...`, `apps/extension/tests/ui/...` |
| CI | `.github/workflows/ci.yml` |
| Docs | `README.md`, `docs/deploy/runbook.md`, `docs/user-guide.md`, `docs/adr/0016-per-user-ai-provider-byok.md` |

## 2. Chuẩn bị môi trường

```bash
# API
cd apps/api
.venv/bin/pip install -e ".[dev]"          # nếu chưa có venv: python3.11 -m venv .venv
.venv/bin/ruff check src tests migrations scripts
.venv/bin/pytest -q                        # không DB: 202 passed, 137 skipped

# PostgreSQL + pgvector cho integration (ví dụ)
docker run -d --name qa-test-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=quickassist_test \
  pgvector/pgvector:pg16

export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test
.venv/bin/pytest -q                        # baseline hiện tại: 14 failed, 325 passed

# Extension
cd ../extension
npm ci
npm test -- --run
npx tsc --noEmit
npm run build
npm run check:bundle
```

> Máy này không có `python` trong PATH; dùng `.venv/bin/python` cho mọi script API.
> Test DB dùng `tests/conftest.py::_migrated`: downgrade base → upgrade head mỗi session, nên
> **đừng trỏ `TEST_DATABASE_URL` vào DB có dữ liệu thật**.

## 3. S1 — Sửa 14 test integration (làm trước tiên)

### 3.1 Vì sao đỏ

P1 đổi dependency `AIProviderDep` từ `get_ai_provider` sang `get_user_ai_provider`; indexing job
chuyển sang `AISettingsService.provider_for`. Test cũ vẫn override/monkeypatch `get_ai_provider`
nên AI giả không được dùng → gọi mock thật/không đúng kỳ vọng. Ngoài ra P3 gọi sai URL
`/ai/search` (route đúng `/search`), và `/auth/config` là endpoint public mới chưa có trong
danh sách `PUBLIC` của test security.

### 3.2 Sửa theo nhóm

**a) Chat / page-match / summary — override đúng dependency**

Trong `tests/integration/api/test_chat.py`, `test_page_match.py`, `test_summary.py`:

```python
# Trước
from quickassist.infrastructure.openai import get_ai_provider
app.dependency_overrides[get_ai_provider] = lambda: ai

# Sau
from quickassist.presentation.api.deps import get_user_ai_provider
app.dependency_overrides[get_user_ai_provider] = lambda: ai
```

Thay **tất cả** occurrence, kể cả test đang pass (chúng chỉ pass vì không gọi LLM; giữ override cũ
là để lại bẫy cho người sau). Không cần truyền `user_id`/`session` trong lambda — FastAPI dùng
signature của override.

**b) Indexing — patch `provider_for` (async)**

`tests/integration/business/test_indexing_job.py` hiện có:

```python
monkeypatch.setattr(indexing_job, "get_ai_provider", lambda: ai)  # attribute không còn
```

Thêm helper và thay 3 chỗ:

```python
def _patch_ai(monkeypatch, ai):  # type: ignore[no-untyped-def]
    async def provider_for(self, user_id):  # type: ignore[no-untyped-def]
        return ai
    monkeypatch.setattr(indexing_job.AISettingsService, "provider_for", provider_for)
```

Dùng `_patch_ai(monkeypatch, ai)` và `_patch_ai(monkeypatch, FlakyAI(fail_times=99))`.

**c) Rebuild — URL đúng**

`tests/integration/api/test_ai_settings_rebuild.py:77`:

```python
r = await client.post("/search", json={"query": "phở Hà Nội"}, headers=h)
```

**d) Security — `/auth/config` là public**

`tests/integration/api/test_security.py`:

```python
PUBLIC = {"/health/live", "/health/ready", "/auth/google/exchange", "/auth/refresh",
          "/auth/logout", "/auth/dev-login", "/auth/config"}
```

### 3.3 Kiểm chứng

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
  .venv/bin/pytest -q
# Kỳ vọng: 339 passed
```

Đã thử nghiệm đúng 6 nhóm fix này trước khi viết guide: **14/14 test đỏ chuyển xanh, toàn bộ
339 passed**; working tree sau đó được hoàn nguyên.

### 3.4 Bẫy

- Đừng “sửa” bằng cách thêm `get_ai_provider` trở lại dependency — sẽ che lỗi thật.
- `monkeypatch.setattr(indexing_job, "get_ai_provider", ...)` sẽ raise `AttributeError` vì module
  không còn import tên đó; patch class method như trên.
- Không đổi assertion/status code để test xanh.

## 4. S2 — SSRF allowlist

### 4.1 Hiện trạng

`validate_base_url` (business/ai_settings/service.py) đang:

```python
u = urlparse(base_url)
if u.scheme not in ("http", "https") or not u.netloc: ...
if allowlist and not any(base_url.rstrip("/").startswith(a.rstrip("/")) for a in allowlist): ...
```

Với `AI_BASE_URL_ALLOWLIST=https://api.openai.com`, các URL sau đều **được chấp nhận**:

- `https://api.openai.com.evil.com/v1` — host thật là `api.openai.com.evil.com`.
- `https://api.openai.com@evil.com/v1` — userinfo `api.openai.com`, host thật `evil.com`.
- `https://api.openai.com:8443/v1` — sai port.

Ngoài ra `APP_ENV=prod` + allowlist rỗng không có cảnh báo (kế hoạch §10 yêu cầu).

### 4.2 Thiết kế

Chuẩn hoá URL thành bộ `(scheme, host, port, path)`:

- Chỉ `http`/`https`; host không rỗng.
- Từ chối `username`/`password` (userinfo), query, fragment, backslash, whitespace/control.
- Port: dùng port tường minh, nếu không có → 443 cho https, 80 cho http.
- Host lowercase.
- Path bỏ `/` cuối; so khớp **theo biên segment**:
  - entry path rỗng → mọi path trên host đó.
  - ngược lại: `path == entry_path` hoặc `path.startswith(entry_path + "/")`.
- Entry allowlist cũng được parse cùng quy tắc; entry sai → fail-fast khi load config
  (validator của `Settings`), không âm thầm bỏ qua.

### 4.3 Code gợi ý

Trong `business/ai_settings/service.py`:

```python
def _parse_http_url(value: str, *, field: str = "base_url") -> tuple[str, str, int, str]:
    value = value.strip()
    if not value or "\\" in value or any(ch.isspace() for ch in value):
        raise _invalid(f"{field} không hợp lệ")
    u = urlparse(value)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise _invalid(f"{field} phải là URL http/https hợp lệ")
    if u.username is not None or u.password is not None:
        raise _invalid(f"{field} không được chứa thông tin đăng nhập")
    if u.query or u.fragment:
        raise _invalid(f"{field} không được chứa query/fragment")
    try:
        port = u.port
    except ValueError as e:
        raise _invalid(f"{field} có port không hợp lệ") from e
    default_port = 443 if u.scheme == "https" else 80
    return u.scheme, u.hostname.lower(), port or default_port, u.path.rstrip("/")


def _allowlist_match(base: tuple[str, str, int, str], entry: str) -> bool:
    try:
        a = _parse_http_url(entry, field="AI_BASE_URL_ALLOWLIST")
    except AppError:
        return False  # validator Settings đã chặn entry hỏng khi khởi động
    if base[:3] != a[:3]:
        return False
    a_path = a[3]
    return not a_path or base[3] == a_path or base[3].startswith(a_path + "/")


def validate_base_url(base_url: str | None) -> str:
    if not base_url or not base_url.strip():
        raise _invalid("base_url không được để trống")
    parsed = _parse_http_url(base_url)
    allowlist = get_settings().ai_base_url_allowlist
    if allowlist and not any(_allowlist_match(parsed, e) for e in allowlist):
        raise _invalid("base_url không nằm trong danh sách được phép (AI_BASE_URL_ALLOWLIST)")
    return base_url.strip()
```

Trong `infrastructure/config.py`, thêm `from urllib.parse import urlparse` và validate entry khi load
(fail-fast):

```python
@field_validator("ai_base_url_allowlist")
@classmethod
def _valid_allowlist(cls, v: list[str]) -> list[str]:
    for entry in v:
        if not entry or "\\" in entry or any(ch.isspace() for ch in entry):
            raise ValueError(f"AI_BASE_URL_ALLOWLIST entry không hợp lệ: {entry}")
        u = urlparse(entry)
        if (u.scheme not in ("http", "https") or not u.hostname
                or u.username is not None or u.password is not None
                or u.query or u.fragment):
            raise ValueError(f"AI_BASE_URL_ALLOWLIST entry không hợp lệ: {entry}")
        try:
            u.port  # noqa: B018 — ép urlparse kiểm tra port
        except ValueError as e:
            raise ValueError(f"AI_BASE_URL_ALLOWLIST entry có port không hợp lệ: {entry}") from e
    return v
```

Trong `main.py::_check_config`, thêm warning (không raise):

```python
if s.app_env == "prod" and not s.ai_base_url_allowlist:
    log.warning(
        "AI_BASE_URL_ALLOWLIST rỗng: user có thể trỏ base_url tới địa chỉ nội bộ (SSRF). "
        "Đặt allowlist hoặc chỉ cho phép base_url tin cậy — xem runbook.",
    )
```

Cập nhật comment `config.py` từ “khớp prefix” → “khớp scheme+host+port+path prefix”.

### 4.4 Test

Mở rộng `tests/unit/business/test_ai_settings_crud.py::test_validate_base_url_scheme_and_allowlist`:

| Allowlist | Base URL | Kỳ vọng |
|---|---|---|
| `https://api.openai.com` | `https://api.openai.com/v1` | ✅ |
| `https://api.openai.com` | `https://API.OPENAI.COM/v1` | ✅ (host lowercase) |
| `https://api.openai.com` | `https://api.openai.com.evil.com/v1` | ❌ |
| `https://api.openai.com` | `https://api.openai.com@evil.com/v1` | ❌ (userinfo) |
| `https://api.openai.com` | `https://api.openai.com:8443/v1` | ❌ (port) |
| `https://api.openai.com` | `http://api.openai.com/v1` | ❌ (scheme) |
| `https://api.openai.com/v1` | `https://api.openai.com/v1/x` | ✅ (path con) |
| `https://api.openai.com/v1` | `https://api.openai.com/v1evil` | ❌ (biên segment) |
| `https://api.openai.com/v1` | `https://api.openai.com/v2` | ❌ |

Thêm test riêng cho `Settings` load entry hỏng (`AI_BASE_URL_ALLOWLIST=file:///etc/passwd`) → raise
`ValidationError`.

### 4.5 Tồn dư (ghi ADR/runbook)

- Allowlist rỗng vẫn cho phép mọi http(s), kể cả `169.254.169.254` / `localhost`. Đây là lựa chọn
  cho self-host; prod chỉ warning, không chặn.
- DNS rebinding: host khớp allowlist nhưng resolve về IP nội bộ vẫn có thể xảy ra. Muốn chặn triệt
  để cần resolve + kiểm tra IP (ngoài phạm vi P5).
- `httpx.AsyncClient` mặc định **không** follow redirect, nên redirect SSRF không phải đường bypass
  hiện tại; nếu sau này bật `follow_redirects` phải kiểm tra lại.
- Không chuẩn hoá percent-encoding/dot-segment trong path; phần path của allowlist chỉ là ràng buộc
  cấu hình, không phải sandbox. Host/port mới là ranh giới SSRF.

## 5. S3 — Chặn model embedding >1536 khi lưu

### 5.1 Hiện trạng

- `/test` đo số chiều native và trả `ok=false` nếu >1536, nhưng `AITestResult` không chứa
  `embedding_dim` khi lỗi.
- `PUT /me/ai-settings` không biết số chiều nên lưu thành công; chỉ khi index mới lỗi.
- UI không cảnh báo khi lưu cấu hình chưa test.

### 5.2 Thiết kế

1. `/test` trả thêm `embedding_dim` (kể cả khi >1536).
2. UI lưu `testedFor` = signature `(provider, base_url, embedding_model)` của lần test.
3. Khi Lưu, nếu `testedFor` khớp form hiện tại và `embedding_dim > 1536` → **chặn** (banner đỏ,
   disable Lưu); nếu chưa test / test lỗi / form đã đổi → hiện banner cảnh báo nhưng vẫn cho lưu.
4. PUT gửi kèm `embedding_dim` khi biết; server từ chối nếu >1536.

> Đây là guard theo hướng “biết thì chặn”. API caller cố tình bỏ `embedding_dim` vẫn lưu được;
> `CanonicalEmbeddingProvider` vẫn là guard cuối lúc embed. Ghi rõ trong tài liệu.

### 5.3 Thay đổi code

**Schema** (`presentation/schemas/ai_settings.py`):

```python
class AISettingsIn(ApiModel):
    ...
    embedding_dim: int | None = Field(default=None, ge=1, le=100_000)


class AISTestOut(ApiModel):
    ok: bool
    embedding_dim: int | None = None   # số chiều native đo được (kể cả khi >1536)
    ...
```

**Business** (`business/ai_settings/service.py`):

```python
@dataclass(frozen=True)
class AITestResult:
    ok: bool
    embedding_dim: int | None = None
    ...

@dataclass(frozen=True)
class AISettingsInput:
    ...
    embedding_dim: int | None = None


def _validate(data: AISettingsInput) -> None:
    ...
    if data.embedding_dim is not None and data.embedding_dim > CANONICAL_DIM:
        raise _invalid(
            f"Model embedding trả {data.embedding_dim} chiều, vượt giới hạn "
            f"{CANONICAL_DIM} chiều được lưu trữ. Hãy chọn model ≤ 1536 chiều."
        )
```

Trong `test_connection`, khi `dim > CANONICAL_DIM` trả `AITestResult(..., embedding_dim=dim)`;
khi thành công cũng set `embedding_dim=dim`. Controller map `embedding_dim=r.embedding_dim`.

**UI** (`ProviderCard.tsx`):

```tsx
const [testedFor, setTestedFor] = useState<string | null>(null)
const signature = () => JSON.stringify([
  form.provider, form.base_url.trim(), form.embedding_model.trim(),
])
const tested = test != null && testedFor === signature()
const nativeDim = tested ? (test.embedding_dim ?? test.embedding?.dim) : undefined
const tooLarge = nativeDim != null && nativeDim > 1536

const onTest = () => void testAct.run(() =>
  rpc('ai/config/test', testInput()).then((r) => {
    setTest(r)
    setTestedFor(signature())
  }))
```

- `buildInput()` thêm `embedding_dim: nativeDim && nativeDim > 0 ? nativeDim : undefined` (chỉ khi
  `tested`; tránh gửi 0 làm schema `ge=1` trả 422).
- `testInput()` bỏ `embedding_dim` (vì `AISTestIn` có `extra="forbid"` → 422 nếu gửi thừa).
- `onSave()`: nếu `tooLarge` → toast lỗi + `return`; nếu `!tested` → hiện banner cảnh báo
  “Cấu hình chưa được kiểm tra…” (không cần dialog); sau đó mới xét dialog rebuild như cũ.
- Banner đỏ khi `tooLarge`: “Model trả N chiều > 1536 — không thể lưu. Chọn model khác hoặc sửa
  endpoint.”
- `afterSave()` thêm `setTestedFor(null)`.

### 5.4 Test

- API integration (`tests/integration/api/test_ai_settings.py`): PUT với `embedding_dim=4096` →
  400 `AI_CONFIG_INVALID`; PUT `embedding_dim=768` → 200.
- Unit: `_validate` từ chối 4096, cho phép 768/None.
- UI (`tests/ui/provider-card.test.tsx`):
  - test trả `embedding_dim: 4096`, bấm Lưu → `ai/config/set` **không** được gọi; banner lỗi hiện.
  - sửa model sau khi test → banner “chưa kiểm tra”; Lưu vẫn gọi set nhưng **không** gửi
    `embedding_dim` cũ.
  - test 768 → Lưu gửi `embedding_dim: 768`.
- Regen contract: `python scripts/export_openapi.py`, `npm run gen:api:file`.

### 5.5 Bẫy

- `ApiModel` có `extra="forbid"`; đừng gửi `embedding_dim` vào `/test`.
- `AITestOut.embedding` có thể `None` khi lỗi embedding; dùng `embedding_dim` top-level.
- Không block theo `test.ok` đơn thuần: test có thể fail ở chat nhưng embedding vẫn hợp lệ.
- UI phải reset `test`/`testedFor` sau khi lưu hoặc đổi preset.

## 6. S4 — Copy quota BYOK

### 6.1 Hiện trạng

`apps/extension/src/ui/features/account/SettingsView.tsx`:

```tsx
{byok && (
  <small className="muted">
    Bạn đang dùng key AI riêng (BYOK): lời gọi AI tính vào số liệu này để bạn theo dõi,
    không giới hạn bởi hạn mức server.
  </small>
)}
{quota.data.remaining_tokens === 0 && !byok && (
  <Banner tone="warn">Đã hết hạn mức: ...</Banner>
)}
```

Backend `QuotaService.reserve` vẫn chặn BYOK; `reset_usage` cho phép BYOK reset (đúng D6).

### 6.2 Sửa

```tsx
{byok && (
  <small className="muted">
    Bạn đang dùng key AI riêng (BYOK): lời gọi AI vẫn tính vào hạn mức của server.
    Bạn có thể bấm “Đặt lại số liệu” bất cứ lúc nào để tiếp tục.
  </small>
)}
{quota.data.remaining_tokens === 0 && (
  <Banner tone="warn">
    Đã hết hạn mức: ghi chú mới vẫn được lưu nhưng chưa tìm kiếm ngữ nghĩa/tóm tắt được.
    {byok ? ' Bấm “Đặt lại số liệu” để tiếp tục.' : ''}
  </Banner>
)}
```

Giữ nguyên nút “Đặt lại số liệu” cho BYOK và nhãn “Đã dùng (key của bạn)”.

### 6.3 Test

Trong `apps/extension/tests/ui/ui.test.tsx` (mock `quota/get`):

- `billing_mode: 'byok'`, `used=limit`, `remaining=0` → thấy banner “Đã hết hạn mức”, thấy nút
  “Đặt lại số liệu”, **không** thấy chuỗi “không giới hạn”.
- `billing_mode: 'server'`, remaining 0 → banner hiện như cũ.
- BYOK remaining > 0 → không có banner, vẫn có nút reset.

## 7. S5 — Repair save→rebuild (migration `applied_fingerprint`)

### 7.1 Vấn đề

`ai_settings_controller.put`:

```python
saved = await AISettingsService(session).save(...)   # commit #1 (config mới)
if saved.fingerprint_changed:
    await start_rebuild(...)                          # commit #2 (mark + enqueue)
```

Crash giữa 2 commit → config mới, chunk cũ. Lưu lại cùng config: `old_fp == new_fp` →
`fingerprint_changed=False` → không bao giờ sửa. Cần trạng thái bền vững “cấu hình nào đã được
bàn giao cho rebuild” và một tiến trình repair.

### 7.2 Thiết kế `applied_fingerprint`

- Thêm cột `applied_fingerprint VARCHAR(64) NULL` vào `user_ai_settings` (khớp `String(64)` của
  model; dùng `CHAR(64)` sẽ làm `alembic check` báo lệch kiểu).
- `embedding_fingerprint` = fingerprint cấu hình **hiện tại** (đã có).
- `applied_fingerprint` = fingerprint đã **được enqueue để rebuild** (không phải trạng thái từng
  chunk). Lệch nhau → lần save trước chưa kịp enqueue. `start_rebuild` cập nhật
  `applied_fingerprint` **trong cùng transaction** với mark + enqueue (điều kiện
  `embedding_fingerprint = :fp` để không đè cấu hình mới hơn).
- Worker quét định kỳ + lúc khởi động, gọi `start_rebuild` cho các row lệch.
- Row `inherit` cũ được backfill NULL; chỉ vào diện repair sau khi save/delete ghi
  `embedding_fingerprint` (tránh rebuild toàn bộ user ngay khi deploy).

#### Migration 0004

`apps/api/migrations/versions/20261115_0004_ai_settings_applied_fingerprint.py`:

```python
revision = "0004"
down_revision = "0003"

def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_ai_settings
        ALTER COLUMN embedding_fingerprint TYPE VARCHAR(64),
        ADD COLUMN applied_fingerprint VARCHAR(64)
    """)
    # Backfill cho BYOK: giả định chunk hiện tại đúng cấu hình đang lưu.
    # Inherit để NULL — không thể biết fingerprint server trong SQL.
    op.execute("""
        UPDATE user_ai_settings
        SET applied_fingerprint = embedding_fingerprint
        WHERE mode = 'byok' AND embedding_fingerprint IS NOT NULL
    """)

def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_ai_settings
        DROP COLUMN IF EXISTS applied_fingerprint,
        ALTER COLUMN embedding_fingerprint TYPE CHAR(64)
    """)
```

> Vì sao đổi `embedding_fingerprint` sang `VARCHAR(64)`: migration 0003 tạo `CHAR(64)` nhưng model
> dùng `String(64)`; `alembic check` ở head hiện đỏ (đã kiểm chứng trên DB test). 0004 sửa luôn để
> CI không fail sau khi thêm cột. Nếu không muốn đổi kiểu cột cũ, thay vào đó đổi model thành
> `CHAR(64)` — nhưng phải chọn một hướng và chạy `alembic check`.

#### Model/repo

- `UserAISettings.applied_fingerprint: Mapped[str | None] = mapped_column(String(64))`.
- Thêm `"applied_fingerprint"` vào `_UPDATABLE`.
- Repo method có điều kiện:

```python
async def mark_applied(self, user_id: uuid.UUID, fingerprint: str) -> None:
    await self.s.execute(
        update(UserAISettings)
        .where(UserAISettings.user_id == user_id,
               UserAISettings.embedding_fingerprint == fingerprint)
        .values(applied_fingerprint=fingerprint)
    )

async def set_inherit_fingerprint(self, user_id: uuid.UUID, fingerprint: str) -> None:
    """Đồng bộ fingerprint server hiện tại cho row inherit trước khi repair enqueue."""
    await self.s.execute(
        update(UserAISettings)
        .where(UserAISettings.user_id == user_id,
               UserAISettings.mode == "inherit")
        .values(embedding_fingerprint=fingerprint)
    )
```

#### Save/delete

Đọc `row` **trước** khi upsert (cần trạng thái cũ để quyết định rebuild):

- BYOK: `new_fp = embedding_fingerprint(provider, base_url, embedding_model)`; ghi
  `embedding_fingerprint = new_fp`; **không** đụng `applied_fingerprint`.
- Inherit: `new_fp = server_embedding_fingerprint()`; nếu row đã có, ghi
  `embedding_fingerprint = new_fp` (code hiện tại không ghi — thêm vào). Row chưa có thì không tạo.
- `rebuild_required`:
  - `row is None`: inherit → `False` (không có gì để rebuild); byok → `True` (chunk cũ theo cấu
    hình server).
  - `row.embedding_fingerprint is None`: inherit → `False` (row cũ chưa từng theo dõi fingerprint;
    chunk vốn theo server); byok → `True`.
  - Ngược lại: `row.applied_fingerprint != new_fp` (NULL cũng tính là khác → `True`).
- Nếu `rebuild_required == False`: set `applied_fingerprint = new_fp` trong cùng lần upsert để
  đánh dấu đồng bộ (tránh repair enqueue oan). Trường hợp inherit + row `None` thì không có row để set.
- Đổi tên `SaveResult.fingerprint_changed` → `rebuild_required` (rõ nghĩa); controller đổi
  `if saved.rebuild_required:`. Kéo theo sửa
  `tests/unit/business/test_ai_settings_crud.py::test_fingerprint_changed_semantics` và
  `::test_delete_fingerprint_changed_only_when_was_byok` (đổi tên + assertion), nếu không sẽ đỏ
  ngay ở unit test.

#### `start_rebuild`

Thêm guard chống request save cũ ghi đè save mới, rồi mới mark + enqueue:

```python
async def start_rebuild(session, user_id, *, fingerprint):
    repo = UserAISettingsRepository(session)
    if not await repo.fingerprint_is_current(user_id, fingerprint):
        log.info("rebuild_skipped_stale", extra={"user_id": str(user_id)})
        return RebuildPlan(notes=0, fingerprint=fingerprint)
    note_ids = await mark_user_notes_processing(session, user_id)
    # ... enqueue_many như cũ ...
    await repo.mark_applied(user_id, fingerprint)   # trước session.commit()
    await session.commit()
    return RebuildPlan(notes=len(note_ids), fingerprint=fingerprint)
```

Repo thêm:

```python
async def fingerprint_is_current(self, user_id: uuid.UUID, fingerprint: str) -> bool:
    row = await self.get(user_id)
    return row is not None and row.embedding_fingerprint == fingerprint
```

Lý do: nếu save B đã commit trước khi `start_rebuild(A)` kịp chạy, không được mark note
PROCESSING/enqueue job A nữa — job A sẽ tự bỏ vì fingerprint lệch, nhưng note có thể kẹt
PROCESSING sau khi job B đã xong. Với `mode=inherit`, save/delete đã ghi
`embedding_fingerprint = server_fp` nên guard dùng chung một điều kiện.

`start_rebuild` cần `UserAISettingsRepository` để `mark_applied`; import trực tiếp repository
(`data_access.repositories.user_ai_settings_repository`). `repair_pending_rebuilds` cần thêm
`server_embedding_fingerprint` từ `business.ai_settings` — chiều phụ thuộc này đã tồn tại ở
`indexing_job`, và `ai_settings.service` không import `semantic_search` nên không tạo vòng.

#### Worker repair

Thêm hàm trong `business/semantic_search/rebuild.py`:

```python
async def repair_pending_rebuilds(session: AsyncSession) -> int:
    rows = (await session.execute(
        select(UserAISettings).where(
            or_(
                and_(UserAISettings.mode == "byok",
                     UserAISettings.embedding_fingerprint.is_not(None),
                     UserAISettings.applied_fingerprint.is_(None)),
                and_(UserAISettings.embedding_fingerprint.is_not(None),
                     UserAISettings.applied_fingerprint.is_not(None),
                     UserAISettings.applied_fingerprint != UserAISettings.embedding_fingerprint),
            )
        )
    )).scalars().all()
    repo = UserAISettingsRepository(session)
    repaired = 0
    for row in rows:
        if row.mode == "inherit":
            fp = server_embedding_fingerprint()
            if not fp:
                continue
            # Cập nhật embedding_fingerprint = server fp hiện tại để mark_applied khớp;
            # update + enqueue + mark cùng transaction trong start_rebuild.
            await repo.set_inherit_fingerprint(row.user_id, fp)
        else:
            fp = row.embedding_fingerprint
        if fp:
            await start_rebuild(session, row.user_id, fingerprint=fp)
            repaired += 1
    return repaired
```

Gọi trong `worker.py`:

```python
async def _repair_once() -> None:
    from quickassist.business.semantic_search.rebuild import repair_pending_rebuilds
    from quickassist.data.database import get_sessionmaker

    async with get_sessionmaker()() as session:
        repaired = await repair_pending_rebuilds(session)
    if repaired:
        get_logger(__name__).info("rebuild_repaired", extra={"users": repaired})
```

- Đầu `main()` (sau `load_job_handlers()`), gọi một lần trong `try/except` để lỗi repair không
  làm sập worker.
- Trong `housekeeping()` mỗi 300s (cùng chỗ `release_stale`), cũng bọc `try/except`.

Với `mode=inherit`, `embedding_fingerprint` phải được cập nhật khi save/delete (mục trên), nếu
không repair không biết fingerprint server hiện tại.

### 7.3 Test

- **Crash giả lập:** gọi `save()` (commit config) nhưng **không** gọi `start_rebuild`; gọi
  `repair_pending_rebuilds()` → job được enqueue, note PROCESSING; drain → READY;
  `applied_fingerprint == embedding_fingerprint`.
- **Re-save cùng config:** sau crash, gọi `save()` cùng config → `rebuild_required=True` (vì
  `applied` cũ), job enqueue.
- **Không đè cấu hình mới:** save config A; save config B; gọi `start_rebuild(A)` → guard trả
  `notes=0`, không mark note PROCESSING, không enqueue job A; note vẫn READY theo B.
- **Inherit:** BYOK → delete về inherit → `rebuild_required=True`; sau rebuild applied = server fp;
  save inherit lần nữa → `False`.
- **Migration:** `alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head`
  trên test DB (giống CI).

### 7.4 Bẫy

- Không được `UPDATE applied_fingerprint` vô điều kiện: cấu hình mới hơn có thể đã được lưu.
- `applied_fingerprint` chỉ nghĩa “đã enqueue”, **không** phải “mọi chunk đã rebuild xong”. Đừng
  dùng nó để ẩn cảnh báo rebuild; job retry/stale chịu trách nhiệm hoàn tất từng note.
- `start_rebuild` hiện commit bên trong; đặt `mark_applied` **trước** commit đó, cùng transaction.
- Backfill chỉ cho `mode='byok'`; inherit để NULL để tránh rebuild toàn bộ user cũ.
- Backfill BYOK giả định các row hiện có đang đồng bộ. Nếu từng crash giữa save và rebuild trước
  P5, dấu sẽ sai; khi nghi ngờ, đặt `applied_fingerprint = NULL` cho user đó rồi để repair xử lý.
- `alembic check` ở head hiện đỏ vì 0003 dùng `CHAR(64)` còn model dùng `String(64)`; 0004 đổi cột
  cũ sang `VARCHAR(64)` và thêm cột mới cùng kiểu. Chạy `alembic check` sau migration.
- Job A đã qua check fingerprint lần 2 trước khi B commit vẫn có thể ghi chunk cũ sau khi B xong
  (cửa sổ rất hẹp). Muốn đóng hoàn toàn phải thêm điều kiện `index_rev` vào `replace_for_note`/
  `set_index_status` — ngoài phạm vi P5, ghi nhận làm tồn dư.
- Repair chạy đồng thời ở nhiều worker: `dedupe_key` của job + `mark_processing_for_user` idempotent;
  vẫn nên dùng `SELECT ... FOR UPDATE` hoặc chấp nhận dedupe (đã đủ cho quy mô hiện tại).

## 8. S6 — Test BYOK stub cố định

### 8.1 Mục tiêu

Chứng minh tiêu chí #2 bằng stub, không chỉ bằng mắt: summary, search, chat RAG, page-match,
indexing đều dùng đúng `base_url` + `Authorization` của user; vector 768 được pad 1536; xoay key
không rebuild; response không lộ key.

### 8.2 Stub server

Tạo `apps/api/tests/integration/api/test_byok_stub.py`. Dùng `ThreadingHTTPServer` thật trên
`127.0.0.1:0` — không monkeypatch internals, đi qua đúng `httpx` + adapter.

```python
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

DIM = 768


def _vec(text: str) -> list[float]:
    v = [0.0] * DIM
    for token in text.lower().split():
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIM
        v[idx] += 1.0
    norm = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norm for x in v]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"   # đóng connection sau mỗi response → SSE không bị treo

    def log_message(self, *args):  # im lặng
        pass

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        self.server.seen.append({  # type: ignore[attr-defined]
            "path": self.path,
            "auth": self.headers.get("authorization"),
            "body": body,
        })
        if self.path.endswith("/embeddings"):
            self._json({
                "data": [{"index": i, "embedding": _vec(t)} for i, t in enumerate(body["input"])],
                "model": body["model"],
                "usage": {"prompt_tokens": sum(len(t) for t in body["input"]) // 4},
            })
        elif self.path.endswith("/chat/completions"):
            if body.get("stream"):
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                for part in ("Đây ", "là ", "câu trả lời."):
                    self.wfile.write(
                        f"data: {json.dumps({'choices': [{'delta': {'content': part}}]})}\n\n".encode()
                    )
                self.wfile.write((
                    "data: " + json.dumps({
                        "choices": [],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }) + "\n\n"
                ).encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self._json({
                    "choices": [{"message": {"content": "Tóm tắt từ stub."}}],
                    "model": body["model"],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                })
        else:
            self.send_error(404)

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def stub():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.seen = []  # type: ignore[attr-defined]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv, f"http://127.0.0.1:{srv.server_port}/v1"
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)
```

### 8.3 Kịch bản test

Một test end-to-end (hoặc tách 2–3 test dùng chung fixture):

1. `h = await login(client)`; tạo note “Phở bò Hà Nội…”.
2. `await drain()` → note READY bằng mock server (baseline).
3. `PUT /me/ai-settings`:
   ```python
   {"mode": "byok", "provider": "openai", "base_url": base_url,
    "api_key": "sk-test-1", "chat_model": "stub-chat",
    "embedding_model": "stub-embed", "timeout_seconds": 30}
   ```
   Assert `rebuild == {"required": True, "notes": 1}`; note PROCESSING; chunk cũ còn.
4. `await drain()`; assert note READY; assert stub đã nhận `/embeddings` với
   `Authorization: Bearer sk-test-1`; assert **không** có `"dimensions"` trong body; query
   `SELECT vector_dims(embedding) ...` = 1536.
5. `POST /search` → items; stub nhận embedding cho query.
6. `POST /ai/summaries` → “Tóm tắt từ stub.”; stub nhận `/chat/completions`.
7. `POST /ai/chat` → SSE có `sources`, `delta`, `done`; stub nhận stream.
8. `POST /ai/page-match` với `text` → items; stub nhận embed + chat.
9. **Xoay key:** PUT cùng config, `api_key="sk-test-2"` → `rebuild is None`; search lại; request
   cuối của stub có `Bearer sk-test-2`; note vẫn READY (không rebuild).
10. `GET /me/ai-settings` → JSON không chứa `sk-test-`; chỉ `has_key` + `key_hint`.
11. (Tuỳ chọn) `DELETE /me/ai-settings` → inherit; search dùng mock, stub không nhận thêm request.

### 8.4 Bẫy

- SSE: `http.server` mặc định HTTP/1.0 đóng connection; nếu dùng HTTP/1.1 phải set
  `Content-Length`/chunked, nếu không `httpx` treo.
- `ProviderCache` giữ provider theo key; xoay key phải tạo request mới — đó chính là điều test
  chứng minh.
- Rate limit: mỗi endpoint gọi 1 lần để không chạm 6/phút (page-match) hoặc 10/phút (AI).
- Quota mặc định 200k; stub usage nhỏ. Nếu test chạy lại nhiều lần, dùng user mới
  (`login(client, "byok-...@test.local")`) để tránh tíchluỹ.
- Assert `dimensions` vắng mặt: `assert "dimensions" not in body`.
- Stub phải trả `usage`; nếu thiếu, quota có thể 0 và một số assert token fail.
- Vector bag-of-words phải cùng chiều cho mọi input; nếu text rỗng, trả vector 0 — tránh chia 0.

### 8.5 Playwright (tuỳ chọn, không bắt buộc DoD)

Kế hoạch §9 ghi E2E Playwright là tuỳ chọn. Nếu làm: dựng stub trong fixture, mở Settings, nhập
base_url/key, bấm Kiểm tra → Lưu → tóm tắt một note; assert stub nhận đúng request và response API
không có key. Không chặn P5 nếu phần này chưa kịp.

## 9. S7 — UI test local mode & quota

Thêm/cập nhật trong `apps/extension/tests/ui/`:

- **AuthGate local mode:**
  - `sessionInfo` trả `authMode='local'`, chưa đăng nhập → không có nút Google; có nút
    “Kết nối lại server”; bấm → gọi `auth/status` (background tự dev-login).
  - `authMode='google'` → nút Google như cũ.
- **SettingsView:**
  - local mode → ẩn “Đăng xuất”; google mode → hiện.
  - BYOK quota copy/banner/reset (mục §6.3).
- **ProviderCard:**
  - >1536 block; untested warning; `embedding_dim` gửi đúng; đổi form sau test → không gửi dim cũ.
- **Không lưu key:** test hiện có đã chốt key không vào storage/log; giữ nguyên và mở rộng nếu cần.

## 10. S8 — Docs, env, ADR, đính chính

### 10.1 `.env.example` ×2

Thêm vào `apps/api/.env.example` và `infra/.env.example` (đúng section, kèm comment tiếng Việt):

```dotenv
# ===== App session =====
# google = OAuth như cũ · local = self-host một người, KHÔNG có xác thực (bind localhost/proxy auth)
AUTH_MODE=google
# Chỉ dùng khi AUTH_MODE=local; email cố định cho dev-login tự động
LOCAL_AUTH_EMAIL=local@quickassist.local

# ===== AI =====
# Khoá mã hoá key BYOK; rỗng → derive HKDF từ JWT_SECRET.
# Đặt riêng để xoay JWT_SECRET không làm mất key đã lưu. Đổi khoá này = user phải nhập lại key.
AI_KEY_SECRET=
# CSV các prefix được phép cho base_url (scheme+host+port+path). Rỗng = cho phép mọi http(s).
# Ví dụ: https://api.openai.com,https://generativelanguage.googleapis.com
AI_BASE_URL_ALLOWLIST=
# Ngân sách token ước tính mỗi request embedding (batch theo token + số mục)
AI_EMBED_BATCH_TOKENS=16000

# ===== Rate limit =====
RATE_LIMIT_AI_SETTINGS_TEST_PER_MINUTE=6
```

Ghi chú thêm cạnh `AI_TIMEOUT_SECONDS`: “config mặc định 90s; file mẫu đặt 30s cho dev”.

### 10.2 `infra/.env.prod.example`

File đang thiếu trên branch nhưng runbook tham chiếu. Khôi phục từ commit `51d0785`:

```bash
git show 51d0785:infra/.env.prod.example > infra/.env.prod.example
```

Sau đó thêm các biến P5 (giá trị prod gợi ý):

```dotenv
AUTH_MODE=google
LOCAL_AUTH_EMAIL=local@quickassist.local
AI_KEY_SECRET=            # BẮT BUỘC đặt riêng; ≥32 ký tự ngẫu nhiên
AI_BASE_URL_ALLOWLIST=    # nên đặt; rỗng → warning SSRF trong log
AI_EMBED_BATCH_TOKENS=16000
RATE_LIMIT_AI_SETTINGS_TEST_PER_MINUTE=6
```

Kiểm tra `docker compose -f infra/docker-compose.prod.yml config` hợp lệ (không cần secret thật).

### 10.3 README

Thêm mục sau “Chạy nhanh”:

- **Tự cung cấp khoá AI (BYOK):** mở Settings → “Nhà cung cấp AI”; preset OpenAI/Gemini/Ollama/
  LM Studio/llama.cpp; Kiểm tra kết nối; Lưu; giải thích rebuild khi đổi model embedding; key lưu
  mã hoá server-side, không nằm trong extension.
- **Self-host một người:** `AUTH_MODE=local`, `LOCAL_AUTH_EMAIL`; cảnh báo **không có xác thực**,
  bind `127.0.0.1` hoặc proxy auth; `AUTH_MODE=google` giữ nguyên luồng cũ.
- Bảng biến môi trường mới (6 biến) + link runbook/user-guide.

### 10.4 Runbook

Thêm mục “BYOK & local mode” (sau §5 vận hành hằng ngày):

- **Mã hoá key:** đặt `AI_KEY_SECRET` trước khi user nhập key; xoay khoá → key cũ không giải mã
  được (`AI_KEY_UNREADABLE`), user nhập lại. Nếu để trống, `JWT_SECRET` là nguồn derive — xoay
  `JWT_SECRET` cũng gây hiệu ứng này.
- **Allowlist:** CSV prefix; khớp scheme+host+port+path; rỗng = cho phép mọi http(s) + warning prod;
  DNS rebinding/metadata IP là tồn dư; khuyến nghị đặt allowlist ở prod.
- **Local mode:** `AUTH_MODE=local` bỏ xác thực; chỉ bind localhost hoặc sau proxy có auth; không
  mở Internet; logout bị ẩn (tự dev-login lại).
- **Quota BYOK:** vẫn chặn như user thường; user BYOK được “Đặt lại số liệu”; banner hết hạn mức
  hiện cho cả BYOK.
- **Rebuild repair:** worker quét `applied_fingerprint != embedding_fingerprint` mỗi 5 phút; nếu
  kẹt, kiểm tra SQL:
  ```sql
  SELECT user_id, mode, embedding_fingerprint, applied_fingerprint
  FROM user_ai_settings
  WHERE embedding_fingerprint IS DISTINCT FROM applied_fingerprint;
  ```
  Re-save cấu hình hoặc chờ worker; job stale tự bỏ.
- **Stream bị ngắt:** lưu/xoá cấu hình AI hoặc evict cache giữa lúc chat có thể làm stream dừng
  (`httpx.ReadError`); người dùng gửi lại. Đây là hành vi đã chấp nhận ở P5.
- **Troubleshooting:** bảng mã lỗi `AI_CONFIG_INVALID`, `AI_KEY_UNREADABLE`, `AI_UNAVAILABLE`,
  `QUOTA_EXCEEDED`, `RESET_NOT_ALLOWED`, allowlist reject.

### 10.5 User guide

Mở rộng §9 “Cài đặt, hạn mức AI”:

- Card “Nhà cung cấp AI”: preset, base_url, key (Hiện/Ẩn/Xoá), model chat/embedding, timeout,
  Kiểm tra kết nối, Lưu, “Dùng cấu hình server”.
- Key lưu mã hoá trên server; extension không lưu key; server proxy mọi lời gọi.
- BYOK vẫn tính hạn mức; nút “Đặt lại số liệu”; banner khi hết.
- Đổi model embedding → dựng lại chỉ mục N ghi chú; tìm từ khoá vẫn chạy; search ngữ nghĩa có thể
  trả kết quả cũ trong lúc dựng.
- Model >1536 chiều bị chặn; 768 chiều được pad.
- Local mode: không cần Google; máy phải tin cậy; không mở Internet.
- Lưu cấu hình giữa lúc chat có thể ngắt câu trả lời đang viết.

### 10.6 ADR-0016

Sửa điểm 5:

```text
5. **Rebuild khi fingerprint embedding đổi**: KHÔNG xoá note_chunks hàng loạt (nhánh từ khoá
   cũng đọc bảng này). Đánh dấu note PROCESSING + index_rev+1, enqueue job kèm fingerprint mới;
   job cũ fingerprint lệch tự bỏ; chunk từng note được replace_for_note khi job tới lượt.
   Search vẫn trả chunk cũ trong lúc rebuild. `applied_fingerprint` ghi nhận cấu hình đã áp;
   lệch → worker repair.
```

Thêm mục P5:

```text
8. **Hardening P5**: allowlist khớp scheme+host+port+path (từ chối userinfo; warning prod khi
   rỗng); PUT từ chối `embedding_dim > 1536` khi client biết; `applied_fingerprint` + repair
   chống crash giữa save và rebuild.
```

Cập nhật “Hệ quả”: rebuild lâu, search trả chunk cũ; crash được repair; allowlist rỗng vẫn là
tồn dư SSRF.

### 10.7 Đính chính P3/P4

Thêm cuối mỗi báo cáo:

```markdown
## Đính chính (2026-11-15)

- “202 passed, 137 skipped” là chạy **không có** `TEST_DATABASE_URL`; integration bị skip.
- Với PostgreSQL thật: 14 test đỏ do target monkeypatch/URL cũ (không phải regression sản phẩm).
- `test_full_rebuild_flow` gọi `/ai/search` (đúng là `/search`) nên chưa từng xanh trên DB.
- P5 sửa các mục trên; xem `docs/self_sustained/reports/byok-ease-PRE_P5.md` và báo cáo P5.
```

## 11. S9 — CI & cổng cuối

### 11.1 CI hiện có

`.github/workflows/ci.yml` đã có:

- Job `api`: service `pgvector/pgvector:pg16`, `TEST_DATABASE_URL`, `pytest -q` (gồm integration),
  `alembic upgrade/check/downgrade/upgrade`, `export_openapi.py --check`.
- Job `extension`: `npm test`, `npm run build`, `check:bundle`.
- Job `e2e`: API + worker + Postgres + Playwright.

Vấn đề: `on.push.branches` chỉ `[main, dev]`; branch `son-test-dev` chưa push/PR → CI chưa chạy.

### 11.2 Việc cần làm

- Thêm `workflow_dispatch:` để chạy tay:
  ```yaml
  on:
    pull_request:
    push:
      branches: [main, dev]
    workflow_dispatch:
  ```
- Ưu tiên mở PR `son-test-dev` → `dev` để chạy đủ 3 job; nếu cần chạy trên push, thêm nhánh tạm
  vào `push.branches` (hoặc dùng `workflow_dispatch`).
- Bật required checks `api`, `extension`, `e2e` trong branch protection.
- Không cần thêm job mới: `pytest -q` đã chạy integration khi có `TEST_DATABASE_URL`.
- Nếu muốn chắc chắn không skip integration, thêm bước:
  ```bash
  pytest -q -m integration
  ```
  (job `api` đã có DB; bước này chỉ để fail sớm nếu ai đó bỏ biến).

### 11.3 Cổng cuối (chạy trước khi báo xong)

```bash
cd apps/api
.venv/bin/ruff check src tests migrations scripts
.venv/bin/pytest -q                                   # 202 passed, 137 skipped (không DB)
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
  .venv/bin/pytest -q                                 # 339 baseline + test P5, tất cả passed
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
  .venv/bin/alembic upgrade head && \
  .venv/bin/alembic check && \
  .venv/bin/alembic downgrade base && \
  .venv/bin/alembic upgrade head
.venv/bin/python scripts/export_openapi.py --check

cd ../extension
npm test -- --run
npx tsc --noEmit
npm run build
npm run check:bundle
```

```bash
git status --short          # chỉ các file dự kiến
git diff --stat             # không có file sinh tự động ngoài openapi/schema
```

## 12. Ma trận thủ công trước khi merge

| # | Case | Kỳ vọng | Ghi chú |
|---|---|---|---|
| 1 | OpenAI key thật | Test OK; summary/RAG/search chạy; đổi key không rebuild | tốn phí |
| 2 | Gemini key thật | Test OK; embedding 1536 | |
| 3 | Ollama `nomic-embed-text` (768) | Test báo 768 + pad; search đúng thứ tự | |
| 4 | llama.cpp không key | Test OK; lưu không key | |
| 5 | Key sai | Test lỗi 401 rõ; lưu vẫn được + cảnh báo | |
| 6 | Model 4096 chiều | Test từ chối; UI chặn lưu; API PUT kèm dim bị 400 | |
| 7 | Đổi embedding model | Confirm đúng N note; keyword search chạy; banner; xong READY | |
| 8 | Đổi key giữa rebuild | Job cũ bỏ; không trộn vector | |
| 9 | `AUTH_MODE=local` | Không cần Google; ẩn logout; reconnect chạy | bind localhost |
| 10 | `AUTH_MODE=google` | Luồng cũ không đổi | |
| 11 | Allowlist chặn | evil host/userinfo/port/scheme bị 400; prod log warning khi rỗng | |
| 12 | Quota BYOK | Hết hạn mức → banner; “Đặt lại số liệu” reset; vẫn chặn khi hết | |
| 13 | Lưu cấu hình giữa stream | Stream dừng; gửi lại được | đã chấp nhận |
| 14 | Crash save→rebuild | Repair worker hoặc re-save cùng config rebuild; không mất dữ liệu | dùng SQL set applied cũ |

Ghi kết quả (Pass/Fail + log) vào báo cáo P5.

## 13. Thứ tự commit đề xuất

1. `test(api): sửa 14 test integration theo dependency/provider_for mới` (S1).
2. `fix(api): allowlist base_url khớp host chặt + warning prod` (S2).
3. `fix(api+ext): chặn embedding >1536 khi lưu + cảnh báo UI` (S3).
4. `fix(ext): copy quota BYOK đúng D6 + banner hết hạn mức` (S4).
5. `fix(api): applied_fingerprint + migration 0004 + worker repair` (S5).
6. `test(api): BYOK stub end-to-end (summary/search/RAG/page-match/indexing)` (S6).
7. `test(ext): local mode, quota BYOK, >1536` (S7).
8. `docs: BYOK/local mode, env, ADR, đính chính P3/P4` (S8).
9. `ci: workflow_dispatch + gate; docs: báo cáo P5` (S9).

Mỗi commit chạy tối thiểu: test liên quan + `ruff`/`tsc`; commit 5 chạy thêm `alembic check`.

## 14. Câu hỏi mở / bẫy chung

- **Không** dùng `alembic downgrade base` trên DB dev có dữ liệu; chỉ dùng DB test.
- `Settings` được `lru_cache`; test đổi env phải `get_settings.cache_clear()`.
- `AISTestIn`/`AISettingsIn` có `extra="forbid"`; thêm field phải regen `schema.d.ts`.
- `provider_cache` là process-local; API và worker có cache riêng — không có cache chéo process.
- Key rotation: `provider_cache.invalidate_user` là bắt buộc sau save/delete; nếu quên, request
  tiếp theo vẫn dùng key cũ đến khi LRU evict.
- `AI_KEY_UNREADABLE` là lỗi cấu hình, không phải lỗi user; hướng dẫn user nhập lại key.
- Local mode không có auth: đừng đặt sau Caddy public mà không có auth; kiểm tra `APP_ENV=prod`
  không tự bật local.
- Rebuild repair chạy trong worker; nếu deployment không chạy worker, job không bao giờ xong.
- Search trong rebuild trả chunk cũ — đừng “sửa” bằng cách xoá chunk hàng loạt (mất keyword search).
- Nếu thêm `embedding_dim` vào response, cập nhật `apps/extension/src/shared/api/schema.d.ts` và
  test mock; đừng sửa tay file generated.

## 15. Liên kết

- Kế hoạch gốc: `docs/self_sustained/byok-and-easeofsetting.md` (§7 P5, §9 test, §10 rủi ro, §11
  tiêu chí).
- ADR: `docs/adr/0016-per-user-ai-provider-byok.md`.
- Báo cáo nghiệm thu trước P5: `docs/self_sustained/reports/byok-ease-PRE_P5.md`.
- Báo cáo P3/P4 (đã đính chính): `docs/self_sustained/reports/byok-ease-P3.md`, `P4.md`.
