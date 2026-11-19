# Báo cáo triển khai P3 — Tìm trong trang: cảnh báo phạm vi, batch + SSE, confidence ≥ 50%, sort

> Nguồn: `docs/self_sustained/ux_improvement_plan.md` §5.3, §11 checklist Phase 3  
> Ngày: 17/11/2026 · Nhánh: `son-test-dev`  
> Trạng thái: **Hoàn tất phần code** — 2 commit, unit/UI/typecheck/build extension + unit/architecture API xanh; integration/e2e **cần PostgreSQL + Docker** để chạy (xem §3.2).

## 1. Phạm vi đã làm

| # | Hạng mục | Commit | File chính |
|---|---|---|---|
| 1 | Backend: `scan_all`, batch embed 32 block + timeout/lô, SSE tiến độ, confidence 0..1 + fallback cosine | `b9d0b95` | `config.py`, `extractor.py`, `page_match_service.py`, `prompts.py`, `page_match_controller.py`, `schemas/page_match.py`, `mock_client.py`, `openapi.json`, `schema.d.ts`, `.env.example` |
| 2 | Extension: đo độ dài trước khi quét, dialog 50k/toàn bộ, stream + huỷ, tiến độ lô, badge confidence, sort toggle | `28f926f` | `content/injected.ts`, `background/page-match.ts`, `handlers.ts`, `protocol.ts`, `endpoints.ts`, `config.ts`, `PageFinderView.tsx`, `styles.css` |

Hai endpoint dùng **chung một service**: `POST /ai/page-match` (JSON cũ) và `POST /ai/page-match/stream` (SSE mới). Extension chuyển hẳn sang stream; client cũ vẫn gọi JSON bình thường.

## 2. Thay đổi chi tiết

### 2.1. Backend (`b9d0b95`)

- **Cấu hình mới** (`infra/.env.example`):
  - `PAGE_MATCH_EMBED_BATCH_BLOCKS=32` — số block mỗi lô embed.
  - `PAGE_MATCH_EMBED_TIMEOUT_SECONDS=30` — timeout **tính riêng từng lô**.
  - `PAGE_MATCH_MIN_CONFIDENCE=0.5` — ngưỡng giữ đoạn sau thẩm định LLM.
  - `PAGE_MATCH_FALLBACK_MIN_SIMILARITY=0.5` — ngưỡng cosine khi LLM lỗi.
- **Extractor**: `max_chars: int | None`; `scan_all=True` truyền `None` → **không cắt cuối trang**. HTML vẫn bị chặn bởi `PAGE_MATCH_MAX_HTML_BYTES = 2 MB` ở cả hai endpoint.
- **Batch + quota** (`PageMatchService.stream`):
  1. Embed **query một lần**, rồi embed từng lô block tuần tự, mỗi lô một `asyncio.wait_for` 30s.
  2. **Một quota lease** cho toàn bộ embed; cộng dồn `usage.total` của query + các lô, **commit một lần** khi xong. Lease là context manager nên lỗi/huỷ giữa chừng tự `release` phần giữ chỗ.
  3. Lease thứ hai (riêng) cho LLM thẩm định như trước; lỗi ở bước này → fallback chứ không làm hỏng cả lần quét.
- **SSE** (`POST /ai/page-match/stream`):
  - Event `progress` với `phase = extract | batch | verify`; `batch` kèm `index`/`total`.
  - Event `done` chứa toàn bộ `PageMatchOut`; event `error` chứa `{code, message, status}`.
  - `validate_request()` chạy **trước khi mở stream** → truy vấn sai/HTML quá lớn/nội dung dán rỗng vẫn trả JSON 413/422 đúng chuẩn. Lỗi phát sinh sau khi mở stream mới thành event `error`.
  - Generator được `aclose()` trong `finally` khi client đóng kết nối → nhả quota lease ngay, không chờ `release_stale`.
- **Confidence**:
  - Prompt yêu cầu `confidence: 0..1` cho từng block.
  - `parse_verdicts` trả `dict[id, float]`; chấp nhận legacy `relevant` (`true → 1.0`, `false → 0.0`); clamp 0..1; bỏ id lạ/giá trị không phải số.
  - `PageMatchItemOut.confidence`; lọc `confidence >= 0.5`; `verified=true` khi LLM đã đánh giá.
  - Fallback khi LLM lỗi/timeout/JSON hỏng: giữ candidate có `cosine >= 0.5`, `confidence = cosine`, `verified=false`, `warning="VERIFY_UNAVAILABLE"`.
  - `PAGE_MATCH_MIN_SCORE=0.35` vẫn chỉ là ngưỡng **candidate** đưa vào LLM.
- **Contract**: `PageMatchIn.scan_all` (mặc định `false`), `PageMatchItemOut.confidence`; `openapi.json` và `schema.d.ts` regenerate.

### 2.2. Extension (`28f926f`)

- **Đo trước khi quét**: `RawPage.textChars` + `getPageTextChars()` (bản sao DOM, bỏ script/style/ô nhập). RPC mới `pageMatch/inspect` trả `{textChars, url, title}` — **không tải HTML lên server** chỉ để đếm.
- **Dialog phạm vi** (`ScanScopeDialog`):
  - Mở khi trang/dán > `50.000` ký tự; hiện số ký tự, ước tính `~chars/2` token và số lô `ceil(ceil(chars/1200)/32)`.
  - Nút **“Quét 50k đầu”** (mặc định) / **“Quét toàn bộ”** / **“Huỷ”**; **không tự quét** khi chưa chọn.
  - Nội dung dán dùng `pasted.length`, không cần đọc trang.
- **Stream + huỷ**:
  - `runPageMatch` gọi `api.ai.pageMatchStream` với `requestId`; background giữ `AbortController` theo id.
  - RPC `pageMatch/cancel { requestId }` → abort fetch; UI bỏ qua lỗi `ABORTED` để không hiện ErrorState sau khi người dùng chủ động huỷ.
  - Background parse SSE bằng `createSseParser`, forward `pageMatch/progress` qua broadcast; lỗi trong event `error` được dựng lại thành `AppError` đúng mã/HTTP status.
- **Tiến độ**: thanh xác định `lô i/n` (`role="progressbar"`, `aria-valuenow/max`) khi có `batch`; thanh không xác định cho `extract`/`verify`; nút **Huỷ** ngay cạnh nhãn.
- **Hiển thị kết quả**:
  - Segmented control **“Thứ tự trong trang”** / **“Tin cậy giảm dần”**, sort trên bản copy; `selected` theo id không đổi.
  - Nhãn “Đoạn n” vẫn lấy theo **thứ tự trang** dù đang sort; lưu luôn theo thứ tự trang + hint “Khi lưu, các đoạn xếp theo thứ tự trong trang.”
  - Badge dùng `confidence` thay `score`; tooltip phân biệt “AI tin cậy…” và “AI chưa thẩm định — theo độ tương đồng cosine”.
  - Banner `truncated` khi chọn 50k; empty state “Không tìm thấy đoạn nào đủ tin cậy”.

## 3. Kiểm chứng

### 3.1. Đã chạy trên máy dev

| Lệnh | Kết quả |
|---|---|
| `ruff check src tests` (apps/api) | ✅ All checks passed |
| `pytest -q` (apps/api) | ✅ **225 passed, 154 skipped** (integration skip có chủ ý — không có DB) |
| `pytest -q tests/unit/business/page_match` | ✅ **44 passed** |
| `python scripts/export_openapi.py --check` | ✅ `openapi.json khớp code` |
| `npm run typecheck` (apps/extension) | ✅ không lỗi |
| `npm test` (vitest) | ✅ 18 files, **208/208** tests |
| `npm run build` + `npm run check:bundle` | ✅ build xanh, bundle đạt rà soát |

Test mới/cập nhật:

- **Unit API**: parser `confidence`, legacy `relevant`, clamp/bỏ giá trị hỏng; mock AI trả confidence; extractor `max_chars=None` + batch chia lô.
- **Integration API (3 mới, chờ DB)**: confidence < 0.5 bị lọc; `scan_all` bỏ trần ký tự và embed theo lô; stream phát `batch` rồi `done`; fallback giữ cosine ≥ 0.5 với `confidence == score`.
- **Extension background (page-match)**: `inspect`, stream progress/done/error, cancel; `textChars`; kiểm tra hàm tiêm **tự chứa** (không tham chiếu biến module).
- **UI page-finder (mới)**: ước lượng lô; dialog trang dài (chưa quét, `scanAll=true/false`); dialog nội dung dán dài; tiến độ lô + Huỷ; sort đổi thứ tự hiển thị nhưng lưu theo thứ tự trang; badge confidence/fallback; empty state.

### 3.2. Chưa chạy được trên máy dev (cần PostgreSQL + pgvector + Docker)

```bash
# Integration API (gồm 3 test page-match mới)
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
  .venv/bin/python -m pytest -q -m integration

# E2E extension
docker compose -f infra/docker-compose.yml up --build
cd apps/extension && npm run test:e2e
```

Chưa thêm spec page-finder mới: e2e hiện có (`ux-screens.spec.ts`) cần `UX_SCREENS=1` + backend thật, và luồng quét phụ thuộc LLM. Các tình huống “trang dài / paste dài / LLM lỗi” đang được phủ ở UI test với mock.

## 4. Đối chiếu checklist Phase 3 (§11)

- [x] *Nội dung > 50k → dialog cảnh báo trước khi quét, có ước tính token/lô* — `ScanScopeDialog` + UI test (trang và dán).
- [x] *Chọn “50k đầu” → `truncated=true` và banner; chọn “Toàn bộ” → không cắt, có progress lô i/n* — backend `max_chars=None`, UI banner/tiến độ, UI test `scanAll`; integration test chờ DB.
- [x] *LLM trả confidence; item < 0.5 bị loại; fallback cosine ≥ 0.5 khi LLM lỗi* — parser + threshold unit test; fallback integration test chờ DB.
- [x] *Sort toggle đổi thứ tự hiển thị; lưu vẫn theo thứ tự trang* — UI test.
- [x] *Timeout từng lô; lỗi giữa chừng có thông báo và release quota* — timeout/lô trong service; lease context manager + `aclose()` khi client huỷ; UI hiện `error`/ErrorState.
- [ ] *E2E `ux-screens`/page-finder cho trang dài, paste dài, LLM lỗi* — **chưa chạy** do thiếu Docker/DB/backend (xem §3.2).

## 5. Hạn chế & ghi chú

- **Batch tuần tự**: các lô embed chạy lần lượt (không song song) để giữ một lease và tránh đẩy áp lực lên provider; trang rất dài có thể mất `n × 30s` worst-case. Huỷ giữa chừng cắt được phần còn lại.
- **Ước lượng ở UI là heuristic**: token `chars/2`, block `1.200` ký tự, lô `32` block — khớp mặc định backend nhưng có thể lệch nếu đổi cấu hình server mà không đổi `config.ts`.
- **LLM chỉ thẩm định `PAGE_MATCH_TOP_CANDIDATES=15` đoạn**; confidence ≥ 0.5 chỉ áp dụng trong nhóm ứng viên này. Đoạn ngoài top vẫn không bao giờ được trả về dù cosine cao.
- **`inspect` và `capture` là hai lần đọc trang**: nếu trang đổi nội dung giữa hai bước, cảnh báo có thể ước lượng lệch; lần quét vẫn chụp lại HTML mới.
- **JSON endpoint cũ không có tiến độ**; extension chuyển hẳn sang SSE. Ai gọi JSON vẫn nhận đúng contract cũ (thêm field `confidence`, `scan_all` mặc định false).
- **Huỷ không có event riêng**: client abort → server phát hiện đóng kết nối và `aclose()` generator. Đây là cách giải phóng lease; không có API “cancel theo id” phía server.
- **Lỗi hàm tiêm đã sửa trong lúc kiểm chứng**: `DROP_TAGS` từng được tách ra module-level, nhưng `chrome.scripting.executeScript` không mang closure sang trang → sẽ `ReferenceError`. Đã đưa hằng số vào thân `getPageTextChars`/`getRawHtml` và thêm test chạy hàm bằng `new Function` để chặn tái phát.
- **`docs/self_sustained/ux_recommendation.md` và `ux_improvement_plan.md` vẫn là file chưa track của người dùng** — không sửa trong P3.

## 6. Đề xuất tiếp theo

1. Chạy integration + e2e ở §3.2 trên môi trường có DB/Docker; đặc biệt xác nhận `scan_all` không cắt cuối và stream trả đủ `batch i/n`.
2. Đo thời gian/token thực tế cho trang 50k/150k/300k (mục §13 của kế hoạch) để chốt batch 32 và timeout 30s.
3. Viết ADR cho page-match streaming/progress (mục Phase 5) — ghi rõ vì sao tách endpoint stream thay vì đổi JSON cũ.
4. Làm **Phase 4 (Hỏi AI — nguồn nhóm)** rồi Phase 5 hardening (component dùng chung, e2e/a11y toàn bộ).
