# P4 — Hỏi AI: nhóm con theo trang trong “Chi tiết nguồn”

> Phase 4 của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-20 · Trạng thái: ✅ Hoàn thành

## Đã làm

- `apps/extension/src/ui/features/chat/Sources.tsx`:
  - `ChatSourceGroup` thêm `pages: PageGroup<ChatSource>[]`; `groupChatSources` tính `pages = groupByPage(notes)` sau khi gom domain.
  - Tách `SourceCards` (dùng lại ở cấp domain hoặc trong nhóm trang) — tránh nhân bản JSX.
  - “Chi tiết nguồn”: `pages.length <= 1` → render như cũ; `> 1` → mỗi trang một `<section class="source-page">` (header link external + count “N trích dẫn”).
  - Domain head thêm `· M trang` khi có > 1 trang.
  - **Chip giữ nguyên theo domain** (D8): không dính nhãn trang.
  - Chat history cũ (không `url`) → 1 nhóm “Không rõ trang”, header ẩn — không crash.
- Test: `tests/chat-sources.test.ts` (+3 case thuần: pages nhiều nhóm/unknown cuối, 1 nhóm khi cùng URL, legacy không url); `tests/ui/chat.test.tsx` (+1 case UI: chip vẫn “Nguồn (1)”, domain head “2 ghi chú · 2 trang”, nhóm trang đúng note).

## Kết quả kiểm chứng

- `npx vitest run tests/chat-sources.test.ts tests/ui/chat.test.tsx` → 26/26 pass.
- Full suite → **280/280 pass**; `npm run typecheck` → pass (sau khi bổ sung `source_type`, `part_count/part_index` trong helper test SearchResults).

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P4-D1 | Nhãn số lượng trong nhóm trang | “N trích dẫn” (không phải “N ghi chú”) | 1 note có thể có nhiều chunk/trích dẫn trong cùng trang; “trích dẫn” khớp ngữ nghĩa nguồn chat |
| P4-D2 | Domain head thêm “· M trang” | Chỉ khi `pages.length > 1` | Nhất quán với nguyên tắc ẩn header khi 1 trang |
| P4-D3 | Count domain | Giữ “số note khác nhau” như cũ | Không đổi hành vi đếm sẵn có; chỉ bổ sung số trang |
| P4-D4 | CSS nhóm trang | Tái dùng class `.source-page*` của P3 | Cùng một visual pattern ở Tìm kiếm và Hỏi AI |

## Chưa rõ / để lại

- Không có. Chip nguồn không đổi — đúng D8.
