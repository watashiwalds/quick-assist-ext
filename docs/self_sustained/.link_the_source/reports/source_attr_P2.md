# P2 — Thư viện: gom nhóm theo trang + toggle Trang/Trang web

> Phase 2 của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-20 · Trạng thái: ✅ Hoàn thành

## Đã làm

- `apps/extension/src/ui/features/notes/groupNotes.ts`:
  - `groupNotesBySource(notes, grouping: 'page' | 'site' = 'page')`.
  - `NoteSourceGroup` thêm `url` (URL đại diện để link “Mở trang nguồn”), `kind` đổi `'source'` → `'page' | 'site'`.
  - Chế độ `page`: key = `sourceKey(url)` (raw URL bỏ query/hash); nhãn = `sourceLabel(url)`; hai bài cùng domain là hai nhóm.
  - Fallback: không có URL hợp lệ nhưng có `domain` → nhóm `site:<domain>`; không có cả hai → “Không rõ nguồn” (cuối).
  - Tài liệu nhiều part: giữ nguyên 1 nhóm, nhãn ưu tiên title, `url` = sourceKey của part 0.
- `apps/extension/src/ui/components/GroupSection.tsx`: props mới `sourceUrl?`, `labelKind?`; link “Mở trang nguồn” (external icon, ngoài nút toggle, không đụng aria-expanded); class `is-page` cho nhãn trang (bỏ uppercase).
- `apps/extension/src/ui/features/notes/NotesView.tsx`:
  - Props `groupNotesBy?` / `onGroupNotesByChange?` (optional, fallback state cục bộ mặc định `page` — không phá test/component cũ).
  - Toggle segmented “Gom theo: Trang / Trang web” trong `.pane-tools`.
  - Filter nhanh tìm cả `n.url`.
  - `ariaLabel` theo kind: `Tài liệu …` / `Trang …` / mặc định `Nguồn …`.
- `apps/extension/src/ui/features/notes/NoteReader.tsx`: link nguồn hiển thị `sourceLabel(note.url)` (fallback domain), `title` = URL đầy đủ.
- `apps/extension/src/ui/sidepanel/App.tsx`: truyền `groupNotesBy` từ prefs; đổi toggle → `prefs/set { groupNotesBy }`.
- `apps/extension/src/background/prefs.ts` + `protocol.ts`: `Preferences.groupNotesBy: 'page' | 'site'`, DEFAULTS `page`, `getPrefs` sanitize giá trị lạ về `page`.
- `styles.css`: `.groupby-toggle*`, `.source-group-link`, `.source-group-label.is-page`.
- Test: `tests/group-notes.test.ts` viết lại (17 case: 2 chế độ, fallback, URL variants, tie-break); `tests/ui/ui.test.tsx` cập nhật 4 test (đổi query tránh trùng link “Mở trang nguồn”, test toggle page↔site, “Chọn cả nhóm” theo trang).

## Kết quả kiểm chứng

- `npx vitest run tests/group-notes.test.ts` → 17/17.
- Full suite → **272/272 pass** (24 file), `npm run typecheck` → pass.

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P2-D1 | `kind` cũ `'source'` | Đổi thành `'site'`, cập nhật hết chỗ dùng + test | Đặt tên theo nghĩa mới: page/site phân biệt tầng nhóm |
| P2-D2 | Page mode với note có `url` a.vn nhưng `domain: 'b.vn'` | Gom theo **URL** (pageKey), bỏ qua trường `domain` | URL là nguồn chân lý của trang; `domain` chỉ dùng khi thiếu URL hợp lệ |
| P2-D3 | Thứ tự khi nhóm page và site cùng domain hoà số mục | Tie-break theo nhãn (giữ sort cũ) | Không thêm rule riêng; hành vi ổn định, có test chốt |
| P2-D4 | Link “Mở trang nguồn” cho nhóm **site** | Không hiển thị (chỉ document/page có `url`) | Nhiều bài khác nhau trong 1 domain — không có “trang nguồn” duy nhất |
| P2-D5 | aria-label link nhóm | `Mở trang nguồn: <label>` | Phân biệt được khi nhiều nhóm cùng màn hình (a11y); test đổi query tương ứng |
| P2-D6 | Test cũ query link `/Tài liệu dài/` | Trỏ vào `<li aria-label>` rồi `within(...)` | Card và link nhóm cùng khớp regex sau khi thêm link nguồn |

## Chưa rõ / để lại

- Toggle chưa có trong Settings (chỉ ở thanh công cụ Thư viện) — đúng plan §6.2.
- Toggle đổi giữa 2 chế độ làm reset trạng thái collapse của nhóm (collapsedGroups theo key nhóm, key đổi khi đổi chế độ) — chấp nhận: đổi chế độ là đổi cấu trúc danh sách.
