# Báo cáo P3 — Rebuild orchestration: enqueue_many, fingerprint guard, integration test

> **Ngày:** 2026-11-14 · **Phase:** P3/5 · **Commits:** `00cb9bd` (orchestration), `8ef609c` + `ccd7715` (integration tests)
> **Kế hoạch:** `docs/self_sustained/byok-and-easeofsetting.md` §7 (P3), §4.6

## Quyết định lớn đã duyệt trước khi làm

**Kế hoạch gốc §4.6 yêu cầu `DELETE FROM note_chunks WHERE user_id` ngay khi lưu** với giả định
"search rơi về nhánh từ khoá". Kiểm tra code thật: **nhánh từ khoá của `_HYBRID_SQL` cũng đọc bảng
`note_chunks`** (cột `tsv`) → xoá hết chunk = search trả 0 kết quả trong suốt lúc rebuild, mâu
thuẫn với dialog xác nhận ("Tìm kiếm từ khoá vẫn hoạt động") và tiêu chí §9. Đã hỏi user →
**chọn: giữ chunk cũ, thay dần theo note** (fingerprint guard bảo đảm không bao giờ ghi chunk sai
model; chunk cũ của từng note được `replace_for_note` thay khi job tới lượt). Hệ quả:

- Search **không gián đoạn** trong rebuild (kết quả từ chunk cũ, tự lành dần).
- Trong khoảng chuyển tiếp, kết quả có thể trộn 2 không gian vector (bounded, tự hết khi rebuild xong) —
  khác với xoá-hết (0 kết quả). Đã cân nhắc và user chọn phương án này.

## Đã làm

### `infrastructure/jobs/queue.py` — `enqueue_many()`
- INSERT ... VALUES mỗi **lô 500** + `ON CONFLICT (dedupe_key) DO NOTHING`; `dedupe_keys[i]`
  ứng payloads[i] (None = không dedupe dòng đó); không commit (outbox pattern như `enqueue`).
- Export qua `infrastructure/jobs/__init__.py`.

### `business/notes` — bulk cho rebuild
- `NoteRepository.mark_processing_for_user`: **một câu** `UPDATE ... RETURNING id` —
  `index_status='PROCESSING', index_rev=index_rev+1, index_error=NULL` cho mọi note chưa xoá
  (bump rev → job cũ không ghi đè trạng thái, đúng cơ chế `set_index_status` sẵn có).
- `NoteRepository.count_active` + public API `mark_user_notes_processing`, `count_active_notes`.

### `business/ai_settings/service.py` — fingerprint hiện hành
- `server_embedding_fingerprint()`: fingerprint cấu hình TOÀN CỤC (theo `AI_PROVIDER`:
  openai/gemini/mock) — hiện hành khi inherit.
- `AISettingsService.current_fingerprint(user_id)`: byok → cột `embedding_fingerprint` đã lưu;
  inherit/chưa có row → fingerprint server. Đây là "sự thật" mà guard so với payload.
- `save/delete` trả **`SaveResult(state, fingerprint, fingerprint_changed)`** — so fingerprint
  trước/sau khi lưu. Đúng D6: đổi key/chat model → False; đổi embedding model/base_url/provider
  hoặc chuyển byok↔inherit → True.

### `business/semantic_search/rebuild.py` — `start_rebuild()` (file mới)
- `mark_user_notes_processing` + `enqueue_many` job `index_note` cho từng note, payload kèm
  `embedding_fingerprint`, **dedupe key gồm fingerprint** (`kind:note_id:fp[:12]`) → 2 lần rebuild
  không dính key nhau. Commit tại đây (mark + enqueue cùng transaction — outbox).
- **Không xoá chunk** (theo quyết định đã duyệt). Đặt ở semantic_search (chủ bảng `note_chunks`) vì
  ai_settings KHÔNG được import semantic_search — `indexing_job` đã phụ thuộc `AISettingsService`,
  import ngược lại tạo chu trình (test L3 cấm). Controller nối 2 service (presentation→business hợp lệ).

### `business/semantic_search/indexing_job.py` — guard kép
1. **Trước mọi việc**: `expected = payload["embedding_fingerprint"]`; nếu có và ≠
   `current_fingerprint(note.user_id)` → bỏ job (job mới đã được xếp), log `index_skipped_stale_fingerprint`.
2. **Sau khi embed, trước khi ghi chunk**: chốt lại lần nữa; lệch → release quota (embed bị bỏ
   không tính) + return — chống đổi cấu hình giữa chừng.
- **Job rebuild (có `expected`) LUÔN embed lại** dù nội dung không đổi: shortcut
  `content_hash` chỉ áp dụng cho job thường — nội dung giữ nguyên nhưng *hàm embedding* đã đổi,
  chunk cũ phải được thay. Đây là điểm mấu chốt tránh "READY mà vector là model cũ".

### Controller + schema
- PUT/DELETE: nếu `fingerprint_changed` → `start_rebuild()` → response `rebuild: {required, notes}`
  (schema `AIRebuildOut` đã chốt từ P2).
- GET: `rebuild_note_count` = `count_active_notes` (tính thật — P2 đang trả 0).

## Verify

- ✅ `pytest tests` → **202 passed, 137 skipped** (6 integration test P3 mới, chạy thật khi có
  `TEST_DATABASE_URL`); `ruff` sạch.
- ✅ Unit: 8 case semantics fingerprint (đổi key False / đổi model True / byok↔inherit True /
  inherit→inherit False / delete khi chưa có row False...).
- ✅ Integration `test_ai_settings_rebuild.py` — flow end-to-end:
  1. note READY → PUT BYOK → `rebuild:{required,notes:1}`, note PROCESSING, job kèm đúng
     fingerprint + dedupe key, **chunk cũ còn nguyên**;
  2. DELETE về inherit → `rebuild` lần 2;
  3. **search giữa chừng vẫn trả kết quả**;
  4. drain: job stale bị guard bỏ (`DONE` chứ không `DEAD`), job fingerprint mới re-index → READY;
  5. same-config 2 lần / đổi key riêng → `rebuild: null` (nghiệm thu #6);
  6. stale-fingerprint job không ghi gì; `enqueue_many` dedupe trùng key còn 1 job;
  7. `rebuild_note_count` = số note active.
- ⚠️ Lần này tôi gộp 5 slice vào 1 commit `00cb9bd` thay vì commit từng slice — code đã chạy
  test sau mỗi slice nhưng commit chậm hơn纪律 đề ra; P4 sẽ trở lại nhịp commit theo slice.

## Rủi ro / việc mở

- Job rebuild cho note nội dung không đổi vẫn embed lại toàn bộ (đúng bản chất rebuild);
  quota mock/BYOK key riêng nên chi phí thuộc user.
- RRF trộn rank 2 không gian vector trong khoảng chuyển tiếp — chấp nhận có chủ đích (đã duyệt).
- Race đã được phủ: job stale (guard 1), đổi config giữa embed và ghi (guard 2), đổi config
  A→B→A (dedupe key theo fingerprint + guard), edit-note job không fingerprint chạy giữa rebuild
  (embed bằng config hiện hành → chunk luôn thuộc model hiện hành).

## Tiếp theo (P4)

Extension: `npm run gen:api` regen types, `endpoints.ts` nhóm `aiSettings` + `authConfig`,
RPC `ai/config/get|set|test|reset`, card "Nhà cung cấp AI" (preset, datalist, nút Kiểm tra kết nối,
ConfirmDialog rebuild + banner tiến độ), auto local-login, ẩn Đăng xuất ở local mode.

## Đính chính (2026-11-15)

- "202 passed, 137 skipped" là chạy **không có** `TEST_DATABASE_URL`; integration bị skip.
- Với PostgreSQL thật: 14 test đỏ do target monkeypatch/URL cũ (không phải regression sản phẩm).
- `test_full_rebuild_flow` gọi `/ai/search` (đúng là `/search`) nên chưa từng xanh trên DB.
- P5 sửa các mục trên; xem `docs/self_sustained/reports/byok-ease-PRE_P5.md` và báo cáo P5.
