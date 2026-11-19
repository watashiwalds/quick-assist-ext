# Báo cáo triển khai P4 — Hỏi AI: nguồn nhóm theo domain trong câu trả lời

> Nguồn: `docs/self_sustained/ux_improvement_plan.md` §4 Phase 4, §5.4, §6.2, §11 checklist Phase 4  
> Ngày: 18/11/2026 · Nhánh: `son-test-dev`  
> Trạng thái: **Hoàn tất** — 1 commit code (kèm test), typecheck/unit/build extension xanh; e2e **cần backend + Docker + Playwright chromium** để chạy (xem §3.2).

## 1. Phạm vi đã làm

Phase 4 gồm 5 hạng mục, trong đó **4 hạng mục đã hoàn tất từ Phase 0** (quick wins làm trước để có nền):

| # | Hạng mục | Trạng thái | Commit |
|---|---|---|---|
| 1 | Timestamp & thứ tự phiên chỉ đổi khi gửi câu hỏi | ✅ từ P0 | `07743f8` |
| 2 | Context 5 lượt theo phiên (`replace`/`reset` đồng bộ ref, chống rò history chéo phiên) | ✅ từ P0 | `6fe29a1` |
| 3 | 3 câu hỏi gợi ý tổng quan + hint "Ngữ cảnh: 5 lượt gần nhất trong phiên này" | ✅ từ P0 | `42d8e30` |
| 4 | **Nguồn nhóm trong câu trả lời** — chip + chi tiết nguồn nhóm theo domain | ✅ **P4 (báo cáo này)** | `679bf70` |
| 5 | Token `--rail-bg`/`--rail-border` đồng bộ màu rail 3 màn | ✅ từ P0 | `cd9a628` |

Hạng mục 4 phụ thuộc Phase 1 (hợp đồng `ChatSource` có `source_index`/`source_domain`, commit `a56ff60`) — đã sẵn sàng từ P1, nên P4 chỉ còn phần UI extension.

| Slice | Commit | File |
|---|---|---|
| Nhóm nguồn UI + CSS + test | `679bf70` | `ChatView.tsx`, `styles.css`, `tests/ui/chat.test.tsx` |

## 2. Thay đổi chi tiết (`679bf70`)

### 2.1. Nhóm nguồn (`ChatView.tsx`)

- Hàm thuần `groupChatSources(sources)`:
  - Key nhóm ưu tiên **`source_index`** (backend gắn theo hạng nguồn 1..5, một nguồn = một domain).
  - **Hội thoại cũ** lưu trước Phase 1 chưa có `source_index` → lọt về nhóm theo `source_domain`; thiếu cả hai → nhóm "Không rõ nguồn". Không crash với dữ liệu cũ (runtime có thể thiếu field dù type khai báo bắt buộc).
  - Mỗi nguồn thuộc **đúng một nhóm** (đảm bảo "không có nguồn trùng lặp giữa các nhóm" bằng cấu trúc, không cần dedupe riêng).
  - Nhóm "Không rõ nguồn" luôn xếp **cuối** — nhất quán với xếp hạng nguồn ở Thư viện (P2) và `grouping.py` (P1).
- **Hàng chip**: nhãn `Nguồn (N)` đổi từ đếm số nguồn sang **đếm số domain** (đúng §5.4.4: "nhãn 'Nguồn (5)' là số domain, bên trong là các note chip"); chip gom thành cụm theo domain, đầu cụm là nhãn domain (ellipsis khi dài, có `title` đầy đủ), các chip ghi chú giữ nguyên class `source-chip`, `is-cited`, `aria-label` cũ.
- **Chi tiết nguồn**: mỗi nhóm một khối với đầu nhóm = domain + badge đếm **số ghi chú khác nhau** (đếm distinct `note_id` — dữ liệu cũ nhiều chunk/note không phình số đếm); card giữ nguyên `source-card`.
- **Trích dẫn `[n]` không đổi**: `index` vẫn là số theo note; chip và card mở đúng `note_id` của nhóm mình.

### 2.2. CSS (`styles.css`)

- Thêm: `.source-cluster` (inline-flex, cách cụm 8px > cách chip 4px), `.source-cluster-label` (max-width 140px, ellipsis), `.source-groups` (grid thay danh sách phẳng), `.source-group-block`, `.source-domain-head`/`.source-domain-name`/`.source-domain-count` (badge pill dùng `--surface` + `--border-soft` như `.source-group-count` của Thư viện).
- **Panel hẹp ≤480px**: ẩn `.source-cluster-label` cùng triết lý "chip nguồn chỉ còn số" hiện có (ẩn `.chip-title` từ trước); thông tin domain vẫn đầy đủ trong "Chi tiết nguồn".
- Không token mới, không màu cứng — chỉ dùng cặp `--muted` trên `--bg`/`--surface`, đã được `tests/contrast.test.ts` kiểm chứng WCAG AA ở cả sáng & tối.

## 3. Kiểm chứng

### 3.1. Tự động (đã chạy trên máy dev)

| Lệnh | Kết quả |
|---|---|
| `npm run typecheck` (apps/extension, gồm `tests/`) | ✅ không lỗi |
| `npm test` (vitest) | ✅ 18 files, **212/212** tests (tăng 5 test mới) |
| `npm run build` | ✅ built |
| `npm run check:bundle` | ✅ Bundle đạt rà soát |

Test mới thêm (đều fail trên code cũ — code cũ không có `.source-cluster-label`/`.source-groups` và `Nguồn (n)` đếm số nguồn nên `Nguồn (3)` với 4 nguồn không thể pass):

- **Chip nhóm theo domain**: 4 note / 3 domain → nhãn `Nguồn (3)`; thứ tự nhãn cụm `amthuc.example → wiki.example → Không rõ nguồn` (cuối); 4 chip, `aria-label` đôi một không trùng (không trùng giữa các nhóm).
- **Trích dẫn + chi tiết nhóm đúng**: `[2]` trong câu trả lời và "Mở ghi chú" trong khối `wiki.example` đều mở `n2` (2 lượt, không lẫn note nhóm khác); đầu nhóm đủ 3 domain, badge đếm đúng.
- **Đếm distinct note**: 2 chunk cùng `note_id` (dữ liệu cũ) → badge "1 ghi chú", không đếm 2.
- **Dữ liệu legacy**: nguồn không có `source_index`/`source_domain` → 1 nhóm "Không rõ nguồn", 2 chip, không crash.

### 3.2. Trên Chrome thật (chrome-devtools MCP) — preview giao diện

E2E `x02-chat.spec.ts` **chưa chạy được** (thiếu backend/Postgres/Docker + Playwright chromium — như P0/P3). Thay thế: dựng trang preview tại `/tmp/opencode/p4-verify/` (ngoài repo) **dùng nguyên file `styles.css` thật** với đúng cấu trúc DOM component render, kiểm tra bằng chrome-devtools:

- **Light**: cụm chip có nhãn domain, chip cited tô accent, "Không rõ nguồn" ở hàng cuối; "Chi tiết nguồn" hiển thị đầu nhóm + badge "2 ghi chú/1 ghi chú", card nhóm dưới đầu nhóm, khoảng cách giữa nhóm rõ ràng.
- **Dark**: đúng token (chip nền tối, badge viền `--border-soft`), không lệch màu.
- **Panel hẹp 400px**: nhãn cụm ẩn, chip còn `[1] [2] [3] [4]`, chi tiết nguồn vẫn nhóm đầy đủ.
- `getComputedStyle` xác nhận: chip = `--bg`/`--muted`, bubble = `--surface` — khớp token, không giá trị lạ.

### 3.3. Không cần chạy lại phần API

Không đổi code API trong P4 (hợp đồng `source_index`/`source_domain` đã có từ P1, integration test `test_chat.py` đã assert đúng contract này).

## 4. Đối chiếu checklist Phase 4 (§11)

- [x] *Chip nguồn nhóm theo domain; "Nguồn (N)" đếm đúng số domain* — `groupChatSources` + UI test `Nguồn (3)` với 4 note/3 domain.
- [x] *Citation `[n]` vẫn mở đúng note; chi tiết nguồn nhóm đúng* — UI test bấm trích dẫn `[2]` và "Mở ghi chú" trong khối domain đều mở đúng note.
- [x] *Không có nguồn trùng lặp giữa các nhóm; note không domain vào nhóm "Không rõ nguồn"* — mỗi nguồn đúng một nhóm theo cấu trúc; test xác nhận 4 chip/4 `aria-label`, "Không rõ nguồn" cuối.

Đối chiếu thêm phần Phase 4 trong §5.4 (các mục 1–3, 5 đã nghiệm thu trong báo cáo P0).

## 5. Hạn chế & ghi chú

- **E2E chưa chạy**: `x02-chat.spec.ts` tương thích về cấu trúc (regex `Nguồn \(\d\)` vẫn khớp vì nhãn giữ format; `.source-card` vẫn tồn tại; chip aria-label giữ nguyên) nhưng cần môi trường thật để nghiệm thu lại.
- **Badge đếm theo distinct `note_id`**: dữ liệu mới (P1) mỗi note đúng 1 nguồn nên đếm = số chip; chỉ dữ liệu cũ nhiều chunk/note mới thấy khác biệt — đây là chủ ý (ghi chú, không phải chunk, mới là "nguồn" người dùng hiểu).
- **Nhãn cụm chip ẩn ở panel hẹp ≤480px** (như `.chip-title`): domain chỉ còn thấy trong "Chi tiết nguồn" ở bề rộng này. Nếu người dùng phản hồi cần thấy domain ngay, có thể đổi thành hiển thị nhãn rút gọn (tên miền ngắn nhất) — để Phase 5.
- **Thứ tự chip trong cụm giữ nguyên thứ tự trích dẫn** (`index` tăng dần theo hạng nguồn→note từ backend); không sort thêm ở client.
- **Hạn chế từ P0 vẫn mở cho Phase 5**: log a11y "form field thiếu id/name" trên sidepanel thật; e2e Playwright chưa cài chromium.
- `docs/self_sustained/ux_improvement_plan.md` và `ux_recommendation.md` vẫn là file chưa track của người dùng — không sửa/commit trong P4.

## 6. Đề xuất tiếp theo

1. Chạy e2e `x02-chat` (cài `npx playwright install chromium` + backend E2E) để nghiệm thu luồng thật, kèm xác nhận nguồn trả về từ RAG đã có `source_index`/`source_domain` đúng nhóm.
2. Bắt đầu **Phase 5 (Hardening)**: tách component dùng chung khi có ≥ 2 nơi dùng thật (`SourceGroup` của Thư viện và nhóm nguồn chat có thể gom), gom selector trùng, e2e/a11y toàn bộ, ADR-0006 cập nhật ngưỡng/grouping.
3. Đánh giá 20–30 phiên chat thật để xem nhãn "Không rõ nguồn" xuất hiện thường xuyên thế nào — nhiều quá thì rà bước trích domain khi lưu note (phạm vi ngoài P4).
