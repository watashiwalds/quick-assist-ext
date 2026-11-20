# P0 — Shared source utility

> Phase 0 của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-20 · Trạng thái: ✅ Hoàn thành

## Đã làm

- Tạo `apps/extension/src/shared/source.ts`:
  - `sourceKey(url)` — `origin + pathname`, bỏ `?query` + `#hash`; chỉ nhận `http/https`; giữ nguyên `www.`, trailing slash, scheme (theo D3/D4: raw URL, bỏ modifier).
  - `sourceDomain(url)` — hostname (giữ `www.`), null với URL không hợp lệ.
  - `sourceLabel(url, max=80)` — `host + path` để hiển thị, decode `%xx` có fallback, cắt ngắn có dấu `…`, path `/` chỉ còn host.
  - `groupByPage(items)` — gom generic theo `sourceKey`, giữ thứ tự xuất hiện (Map insertion), nhóm “Không rõ trang” luôn cuối; trả `PageGroup<T> { key, url, label, items }`.
  - Type `SourceRef { url, title, kind: 'tab' | 'manual' }` — dùng cho PageFinder ở P1.
- Tạo `apps/extension/tests/source.test.ts` — 11 test phủ: bảng URL §5.1 (utm/fbclid/hash/trailing slash/`?id=`), protocol không hợp lệ (`chrome://`, `file://`, `javascript:`), URL hỏng, decode path, cắt label, thứ tự nhóm, unknown cuối, gộp URL trùng.

## Kết quả kiểm chứng

- `npx vitest run tests/source.test.ts` → **11/11 pass**.
- `npm run typecheck` → pass (không lỗi mới).

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P0-D1 | `sourceKey` cho URL không có path (vd `https://a.vn`) | Trả `https://a.vn/` (pathname mặc định `/` của URL parser) | Giữ hành vi mặc định của `new URL`, không thêm rule đặc biệt |
| P0-D2 | `decodeURIComponent` lỗi (path có `%` rác) | Fallback dùng pathname nguyên bản | Tránh crash với URL thực tế; nhóm vẫn hoạt động |
| P0-D3 | `url` đại diện của nhóm trong `groupByPage` | URL **gốc** của item đầu tiên (chưa cắt query) | Link “Mở trang nguồn” nên mở đúng URL thật của note, kể cả khi có deep-link query |
| P0-D4 | Nhãn nhóm khi URL không hợp lệ | “Không rõ trang” | Nhất quán với “Không rõ nguồn” của Thư viện |

## Chưa rõ / để lại

- Không có điểm nào chặn. Hạn chế `?id=123` gộp nhầm đã được chấp nhận ở D4 (ghi trong rủi ro của plan).
