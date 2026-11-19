# Báo cáo triển khai P2 — Thư viện source-first: nhóm theo nguồn, summary-first, bulk move

> Nguồn: `docs/self_sustained/ux_improvement_plan.md` §4 Phase 2, §5.2, §6.1/§6.4, §11 checklist Phase 2  
> Ngày: 17/11/2026 · Nhánh: `son-test-dev`  
> Trạng thái: **Hoàn tất phần code** — 5 commit, typecheck/test/build extension + unit/architecture API xanh; integration/e2e **cần PostgreSQL + pgvector** để chạy (xem §3.2).

## 1. Phạm vi đã làm

| # | Hạng mục | Commit | File chính |
|---|---|---|---|
| 1 | API bulk move `POST /notes/move` + RPC `notes/move` | `47069bb` | `schemas/notes.py`, `note_repository.py`, `notes_service.py`, `notes_controller.py`, `openapi.json`, `schema.d.ts`, `endpoints.ts`, `protocol.ts`, `handlers.ts` |
| 2 | Kết quả tìm kiếm dùng contract grouped + `SearchResults` dùng chung | `8c76308` | `SearchResults.tsx` (mới), `SourceGroup.tsx` (mới), `SearchView.tsx`, `NotesView.tsx`, `protocol.ts`, `handlers.ts`, `styles.css` |
| 3 | Thư viện nhóm theo nguồn + summary-first + tóm tắt nhóm (không AI) | `506c61e` | `groupNotes.ts` (mới), `NoteCard.tsx`, `NotesView.tsx`, `styles.css`, `group-notes.test.ts` (mới) |
| 4 | Bulk move UI: chọn thư mục đích, chọn cả nhóm, reload sau move | `82d87bc` | `MoveNotesDialog.tsx` (mới), `NotesView.tsx` |
| 5 | E2E: thư viện nhóm nguồn + bulk move; tìm kiếm grouped | `bfc4997` | `e2e/c05-library.spec.ts`, `e2e/r05-search.spec.ts` |

Không còn interface `SearchHit` phẳng hay đoạn phẳng hoá ở `handlers.ts` — UI đọc trực tiếp `SearchSource[]` từ Phase 1.

## 2. Thay đổi chi tiết

### 2.1. Backend — bulk move (`47069bb`)

- **Contract** (`schemas/notes.py`): `NotesMoveIn { ids: UUID[1..200], folder_id: UUID | null }`, `NotesMoveOut { moved, missing }`. `folder_id = null` nghĩa là Inbox (server resolve qua `_resolve_folder`).
- **Repository** (`note_repository.move_many`): một câu `UPDATE … WHERE user_id = :uid AND id IN (…) AND deleted_at IS NULL RETURNING id`; tăng `version`, `index_rev`, `updated_at` như mọi thay đổi note để client sync được.
- **Service** (`NotesService.move_many`):
  1. Resolve thư mục đích — thư mục không tồn tại/không sở hữu → `404 FOLDER_NOT_FOUND` (kiểm tra ownership theo user).
  2. Chỉ cập nhật note của chính user, chưa xoá; id lạ/không sở hữu **không làm hỏng lô**, trả về `missing`.
  3. `publish_note_changed` cho từng note đã chuyển trong **cùng transaction** (outbox ADR-0003) rồi commit → note + job index cùng sống/chết.
- **Controller**: `POST /notes/move` (write rate-limit), trả `{ moved, missing }`.
- **Extension**: endpoint `api.notes.move`, RPC `notes/move`, handler gọi API → `syncNotes()` (cập nhật IndexedDB) → broadcast `notes/changed`. OpenAPI + `schema.d.ts` regenerate.

**Ghi chú kiến trúc:** `NoteChunk.folder_id` do `business/semantic_search` sở hữu (L4 trong `test_layers.py`). Vì vậy P2 dùng đúng pattern sẵn có của repo (outbox + job index): note và event nằm cùng transaction, job `index_note` đi nhánh “nội dung không đổi” và cập nhật `NoteChunk.folder_id`. Integration test mới kiểm chứng sau `drain()` chunk đã đổi folder. Nếu muốn ghi bảng chunk theo nghĩa SQL transaction tuyệt đối, cần thêm contract công khai ở `business/semantic_search` — sẽ tạo phụ thuộc vòng `notes ↔ semantic_search` hoặc phải nới luật L4; mình chọn không phá kiến trúc.

### 2.2. Kết quả tìm kiếm grouped dùng chung (`8c76308`)

- `protocol.ts`: `search/query` trả `SearchSource[]`; `handlers.ts` bỏ `flatMap`, trả thẳng `r.sources`.
- `SourceGroup.tsx` (mới): header nguồn gồm domain + số ghi chú, nút mở/đóng có `aria-expanded`, `aria-controls`, `aria-label="Nguồn <domain>"`; nhận `actions` (dùng cho “Chọn cả nhóm”) và `summary`.
- `SearchResults.tsx` (mới), dùng chung cho tab Tìm kiếm và tab tìm gộp trong Thư viện:
  - Mỗi nguồn hiện **3 ghi chú** đầu, nút **“Xem thêm N ghi chú”** mở tới tối đa note API trả (10/nguồn); nếu `note_count` lớn hơn số note đã tải → “và N ghi chú khác trong nguồn này”.
  - Summary-first: có `summary` → hiện summary + badge “Tóm tắt”; không → `snippet`.
  - Badge phần trăm = `similarity` (cosine) kèm tooltip; đổi truy vấn tự reset trạng thái mở/đóng.
- `SearchView.tsx` và phần kết quả của `NotesView.tsx` dùng cùng `SearchResults`; select đổi thành **“Số nguồn tối đa”** (5/10/20 nguồn, mặc định 5).
- Empty state đổi copy theo §5.1.8: “Không có nguồn/ghi chú đủ tin cậy” + gợi ý diễn đạt khác/bỏ lọc/chờ index.
- Subtitle kết quả hiện `X nguồn · Y ghi chú`.

### 2.3. Thư viện nhóm theo nguồn + summary-first (`506c61e`)

- `groupNotes.ts` (hàm thuần, có unit test):
  - Gom theo `Note.domain`; domain rỗng/null → nhóm **“Không rõ nguồn”**, luôn xếp cuối.
  - Nhóm xếp theo **số ghi chú giảm dần**, tie-break lần cập nhật gần nhất rồi label; trong nhóm **mới nhất trước**.
  - `groupSummary`: ghép tối đa **2** `summary_text`/excerpt gần nhất, chuẩn hoá khoảng trắng, cắt 160 ký tự — **không gọi AI** (giải open question 1 theo đề xuất).
- `NoteCard.tsx`: summary-first — `summary_text` + badge “Tóm tắt” trước, fallback excerpt nội dung gốc.
- `NotesView.tsx`: danh sách mặc định render `SourceGroup` (thay `<ul>` phẳng), nhóm mở/đóng được; nút **“Chọn cả nhóm”** chỉ hiện ở chế độ chọn.
- `NoteReader` giữ nguyên summary card phía trên nội dung (đã có từ trước).

### 2.4. Bulk move UI (`82d87bc`)

- `MoveNotesDialog.tsx` (mới): chọn thư mục đích (mặc định **Inbox**, kèm các thư mục người dùng), nêu rõ “Chỉ N ghi chú đã chọn được chuyển”, nút xác nhận `Chuyển (N)`.
- `NotesView`: thêm nút **“Chuyển thư mục”** cạnh “Xoá” trong thanh chọn; `doMove` gọi RPC, toast số đã chuyển, báo `missing` nếu có, xoá lựa chọn, thoát chế độ chọn và `notes.reload()`.
- “Chọn cả nhóm” chọn/bỏ chọn đúng id trong nhóm, **không tự move** — người dùng vẫn phải bấm “Chuyển thư mục”.

### 2.5. E2E (`bfc4997`)

- `c05-library.spec.ts`: thêm test seed 2 note cùng `https://same.example`, 1 note không URL → kiểm tra region “Nguồn same.example”/“Nguồn Không rõ nguồn”; chọn 2 note, mở dialog, chọn thư mục đích, xác nhận `{moved: 2}`; note không chọn vẫn còn.
- `r05-search.spec.ts`: bỏ tiền tố số thứ tự (`1. `) vì UI grouped không đánh số phẳng; cập nhật copy empty state.

## 3. Kiểm chứng

### 3.1. Đã chạy trên máy dev

| Lệnh | Kết quả |
|---|---|
| `ruff check src tests migrations scripts` (apps/api) | ✅ All checks passed |
| `pytest -q` (apps/api) | ✅ **221 passed, 151 skipped** (integration skip có chủ ý — không có DB) |
| `python scripts/export_openapi.py --check` | ✅ `openapi.json khớp code` |
| `npm run typecheck` (apps/extension) | ✅ không lỗi |
| `npm test` (vitest) | ✅ 18 files, **197/197** tests |
| `npm run build` + `npm run check:bundle` | ✅ build xanh, bundle đạt rà soát |

Test mới/ cập nhật:

- **Unit `groupNotes` (7)**: gom domain + thứ tự nhóm/trong nhóm; “Không rõ nguồn” cuối; hoà số note → mới nhất trước; rỗng; summary 2 note + chuẩn hoá; cắt 160; không nội dung → null.
- **UI Thư viện (3 mới)**: nhóm có `aria-expanded` + summary-first + “Không rõ nguồn” cuối; bulk move chỉ note đã chọn + toast + reload; “Chọn cả nhóm” chọn đúng nhóm và không gọi move.
- **UI tìm kiếm**: mock chuyển sang `SearchSource[]`; assert grouped vẫn mở đúng ghi chú và giữ nguồn.
- **Integration API (3 mới, chờ DB)**: bulk move selected-only + `missing` + isolation; move về Inbox + thư mục người khác 404; chunk `folder_id` cập nhật sau `drain()`.

### 3.2. Chưa chạy được trên máy dev (cần PostgreSQL + pgvector)

```bash
# Integration API (gồm 3 test bulk move mới + chunk folder)
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
  .venv/bin/python -m pytest -q -m integration

# E2E extension (c05-library / r05-search)
docker compose -f infra/docker-compose.yml up --build
cd apps/extension && npm run test:e2e
```

## 4. Đối chiếu checklist Phase 2 (§11)

- [x] *Danh sách Thư viện nhóm theo domain; nhóm mở/đóng được, có `aria-expanded`* — `groupNotes` unit + UI test.
- [x] *NoteCard hiển thị summary_text trước content; fallback excerpt* — `NoteCard` + UI test.
- [x] *Search results nhóm theo nguồn, 3 note + Xem thêm* — `SearchResults` dùng chung 2 màn.
- [x] *Chọn nhiều note → Chuyển thư mục → note biến mất khỏi thư mục cũ, xuất hiện ở thư mục mới* — UI test + integration test (chờ DB) + e2e (chờ môi trường).
- [x] *“Chọn cả nhóm” chọn đúng các note trong nhóm; không tự move note chưa chọn* — UI test.
- [x] *API move kiểm tra ownership/folder; rollback khi lỗi* — note + outbox event cùng transaction; folder lạ 404 trước khi update. Chunk cập nhật qua job (xem §2.1); integration test chờ DB.
- [x] *SearchView (tab ẩn) dùng chung component với Thư viện* — cùng `SearchResults`/`SourceGroup`.
- [ ] *E2E `c05-library` xanh* — đã viết/cập nhật, **chưa chạy** (cần Docker + backend + DB).

## 5. Hạn chế & ghi chú

- **Bulk move và transaction chunk**: như §2.1, chunk `folder_id` được cập nhật bởi job index trong cùng outbox transaction với note; không phải một câu SQL ghi cả hai bảng. Đây là pattern sẵn có của repo (folder delete cũng vậy) và giữ đúng luật sở hữu repository.
- **“Xem thêm”** chỉ mở trong số note API đã trả (mặc định 10/nguồn). Phần vượt 10 hiện “và N ghi chú khác” — đúng phương án dự phòng của kế hoạch; muốn xem hết cần phân trang search (ngoài phạm vi P2).
- **Tóm tắt nhóm** ghép 2 note gần nhất và cắt 160 ký tự; không cache, không gọi AI nên chi phí bằng 0. Nếu nhóm toàn note không có summary, tóm tắt là excerpt nội dung — có thể trùng với note đầu.
- **Thứ tự nhóm** chọn “số note giảm dần → cập nhật gần nhất” (kế hoạch cho phép “số note/updated_at”); note trong nhóm mới nhất trước.
- **Không đánh số thứ tự phẳng** trong kết quả grouped (trước là `1.`, `2.`…). E2E/UI test đã cập nhật theo title; citation `[n]` của Hỏi AI vẫn giữ nguyên theo note (Phase 1).
- **Chuyển vào chính thư mục đang mở** vẫn tăng `version`/`updated_at` (idempotent về dữ liệu, chỉ tốn một lần sync). Có thể bỏ qua nếu `folder_id` hiện tại trùng đích ở vòng tối ưu sau.
- **`docs/self_sustained/ux_recommendation.md` vẫn là file chưa track của người dùng** — chưa đổi sang checklist trạng thái (theo cách P1 đã làm); nếu muốn, mình có thể cập nhật riêng.
- **E2E/Integration chưa chạy** do máy dev không có PostgreSQL/Docker — đây là phần cần chốt trước khi coi Phase 2 nghiệm thu xong.

## 6. Đề xuất tiếp theo

1. Chạy 2 lệnh ở §3.2 trên môi trường có DB; nếu integration chunk-folder lệch, kiểm tra job `index_note` có đi nhánh “content_hash không đổi” không.
2. Làm **Phase 4 (Hỏi AI — hiển thị nguồn nhóm)** ngay: `ChatSource` đã có `source_index`/`source_domain` từ P1, `SourceGroup`/`SourceChip` có thể tái dùng — phạm vi 1–1,5 ngày theo kế hoạch.
3. Phase 3 (Tìm trong trang) độc lập retrieval, có thể chạy song song; ưu tiên dialog cảnh báo trước khi quét + confidence ≥ 50% vì là yêu cầu cốt lõi.
4. Khi Phase 4/5 xong, gom token/component dùng chung còn lại (`PaneHeader`, `ConfidenceBadge`, `BulkActionBar`) và chạy lại e2e/a11y toàn bộ.
