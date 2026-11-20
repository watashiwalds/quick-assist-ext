# P5 — Docs/ADR + QA regression

> Phase 5 (cuối) của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-21 · Trạng thái: ✅ Hoàn thành

## Đã làm

- **ADR-0015** (`docs/adr/0015-page-match-pasted-text-source.md`) cập nhật:
  - Quyết định 1: nguồn dán **có thể** kèm `url`/`title` làm nguồn tham chiếu (không còn `url = null` cứng).
  - Quyết định 4: tooltip “Xem trên trang” + chip nguồn tham chiếu.
  - Quyết định 6: ghi chú dán lưu `url` = nguồn tham chiếu người dùng chọn.
  - Hệ quả: thêm (-) “nguồn tham chiếu có thể sai → UI cho sửa/bỏ”; note cập nhật trỏ sang ADR-0018.
- **ADR-0018 mới** (`docs/adr/0018-detailed-source-attribution.md`): raw URL bỏ query/hash; domain vẫn là đơn vị
  truy xuất; page grouping ở client cho 3 màn hình; nguồn dán có nguồn tham chiếu; không thêm permission/migration.
  Cập nhật bảng index `docs/adr/README.md`.
- **docs/user-guide.md**: §4 (toggle Trang/Trang web, link ↗), §5 (nhóm con theo trang trong tìm kiếm), §7 (Chi tiết
  nguồn nhóm trang), §8 (chip nguồn tham chiếu khi dán + cảnh báo kiểm tra/bỏ chip).
- **docs/ux/README.md**: Luồng 4 (search flow có nhóm trang), Luồng 7 (nguồn dán + gom nhóm nguồn ADR-0018).
- **docs/plan/page-paste/plan.md**: ghi chú thay đổi so với MVP ban đầu (`url: null` → nguồn tham chiếu).

## Kết quả kiểm chứng (QA regression)

| Kiểm tra | Kết quả |
|---|---|
| `npm run test` (extension) | ✅ **280/280 pass** (24 file) |
| `npm run typecheck` | ✅ pass |
| `npm run build` | ✅ built (không lỗi) |
| `pytest -q` (backend, venv `apps/api/.venv`) | ✅ **230 passed, 161 skipped** (skip = cần Postgres/Qdrant) |
| `ruff check .` (backend) | ✅ All checks passed |
| Thay đổi `manifest.config.ts` | ✅ Không có — permissions giữ nguyên |
| Migration DB | ✅ Không có |
| Đổi prompt/RAG/`source_index` backend | ✅ Không có |

**Không có thay đổi gì ở `apps/api/src`** trong toàn bộ P0–P5 — backend chỉ chạy regression.

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P5-D1 | QA matrix 12 kịch bản (plan §9.3) | Kịch bản 1–12 cần **trình duyệt thật** — không chạy được trong môi trường agent; đã phủ bằng test tự động phần logic/UI (URL rules, chip, grouping, legacy data). Danh sách 12 kịch bản để lại cho người dùng tự QA thủ công theo `docs/self_sustained/source-attribution-plan.md` §9.3 | Môi trường không có Chrome + tab thật + site thật |
| P5-D2 | pytest/ruff không có ở python hệ thống | Chạy qua venv `apps/api/.venv/bin/python` | Venv của repo có sẵn toolchain |
| P5-D3 | Ngày trong ADR/report | P0–P4 ghi 20/11, P5 ghi 21/11 (phiên làm việc kéo qua đêm) | Trung thực về thời điểm thực hiện |

## Chưa rõ / để lại

- QA matrix 12 kịch bản: người dùng nên tự chạy trên trình duyệt (đặc biệt kịch bản 1–4 liên quan tab thật và quyền đọc trang).
- Các mục “Việc để sau” (source_title, backend source_url, query-ID guard, canonicalize www/AMP, nhãn trang trên chip) giữ nguyên như plan §13.

## Definition of Done (plan §14)

- [x] P0–P5 hoàn thành.
- [x] `npm run test`, `npm run typecheck`, `npm run build` xanh.
- [x] `pytest`, `ruff check .` xanh (backend không đổi).
- [x] Không đổi permissions manifest.
- [x] ADR-0015 cập nhật + ADR-0018 mới.
- [x] User guide / UX docs cập nhật.
- [x] QA matrix: phần tự động hoá được đã pass; 12 kịch bản thủ công để lại cho người dùng.
- [x] Không còn `url: null` cố ý cho nguồn dán khi có nguồn tham chiếu.
