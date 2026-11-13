# Tìm trong trang — demo tĩnh cho hướng redesign

> **Trạng thái:** bản thiết kế tham chiếu — **đã triển khai** vào extension (`PageFinderView.tsx` + `styles.css`, 2026-11-13) · **Phạm vi:** một màn kết quả, light + dark · **Ngày:** 2026-11-12
> Nguồn: wireframe [`../redesign_pagematch.svg`](../redesign_pagematch.svg) / [`../redesign_pagematch.png`](../redesign_pagematch.png) · phong cách: [`../../ui-evolution/demo/`](../../ui-evolution/demo/) · hành vi hiện tại: `apps/extension/src/ui/features/page-finder/PageFinderView.tsx`

## Problem Statement

> Làm sao để người dùng vừa mô tả điều cần tìm, vừa rà các đoạn AI trả về, vừa chọn/lưu — trong cùng một màn, không phải cuộn qua lại giữa ô nhập và danh sách, và vẫn dùng tốt ở cả side panel hẹp lẫn cửa sổ mở rộng?

## Recommended Direction

**Split-view "query rail + kết quả"** ở landscape, thu thành **composer trên + kết quả dưới** ở portrait:

1. **Query rail cố định** (trái, ~34%): headline, trạng thái trang, ô truy vấn neo đáy, `Quét trang` + `Dán thủ công`, dòng trấn an "Không tự lưu".
2. **Results pane** (phải): banner gợi ý full-page → header `Kết quả truy vấn` + số đoạn/đã chọn + `Xem tất cả trên trang` / `Bỏ chọn` → danh sách card → footer lưu dính đáy.
3. **Portrait (≤720px viewport trong demo):** rail thành composer gọn ở trên; toàn bộ vùng kết quả cuộn chung; footer lưu sticky đáy.

### Vì sao hướng này

- **Truy vấn và kết quả không tranh chỗ.** Người dùng thường phải diễn đạt lại; giữ rail cố định giúp tinh chỉnh luôn cách 1 click, đúng câu trả lời đã chốt.
- **Kết quả là vùng đọc chính.** Bỏ clamp 4 dòng: người dùng cần đọc trọn đoạn để quyết định lưu. Danh sách cuộn, header/footer đứng yên.
- **Chọn là hành động mặc định.** Checkbox + badge % nằm cùng hàng với `Đoạn N`; toàn bộ text nằm dưới, không bị cắt bởi metadata.
- **Full-page chỉ là một nhánh.** Banner nói rõ 71% khớp; `Lưu toàn bộ` xuất hiện **chỉ khi** `mode === 'full_page'`. Ở `segments`, footer chỉ còn `Lưu lựa chọn`.
- **Portrait không phải bản thu nhỏ.** Composer lên trên, bỏ headline/lede, footer gộp còn một hàng action; vẫn giữ đủ checkbox, badge, `Xem trên trang`.
- **Không phá ngôn ngữ thị giác.** Token, font hệ thống, radius 8px, accent xanh, mật độ cozy — lấy nguyên từ demo W03.

## Design contract

| Mục | Chốt |
|---|---|
| Job của màn | Rà các đoạn AI gom được và lưu thành **một ghi chú** (hoặc nhiều phần nếu vượt giới hạn). |
| Hành động chính | `Lưu lựa chọn` (các đoạn đang tích). `Lưu toàn bộ` là hành động phụ, chỉ hiện ở full-page. |
| Trạng thái bắt buộc | Kết quả full-page (demo), kết quả segments, idle, đang đọc, đang phân tích, rỗng, lỗi quyền/hạn mức, paste, xác nhận lưu lớn. Demo chỉ dựng màn kết quả full-page theo yêu cầu. |
| Responsive | ≥721px: 2 cột; ≤720px: 1 cột composer trên; min 320px. Production nên dùng **container query ~560px** thay viewport query. |
| Từ chối | Gradient, tím/indigo, bo tròn quá mức, lưới card đồng nhất, hero rỗng, shadow dày, copy tiếng Anh. |

## Những chỗ wireframe ẩn và cách xử lý

| Chi tiết | Quyết định trong demo |
|---|---|
| Badge thẩm định AI | Badge nhỏ chỉ hiện **% tương đồng** (`94%`), tooltip/aria mô tả "AI đã xác nhận". Đoạn chưa thẩm định dùng style neutral (`is-unverified`). |
| `Xem tất cả trên trang` | Thêm ở header kết quả; `Xem trên trang` giữ ở từng card. |
| Trạng thái trang | `Trang có thể quét tự động` + dot xanh, có tooltip "chỉ đọc khi bấm Quét trang". Copy cho "cần quyền" / "không hỗ trợ" ghi ở phần trạng thái bên dưới. |
| Nút `Dán thủ công` | Giữ đúng nhãn wireframe, style text + underline + icon clipboard; mở paste panel trong code thật. |
| Full-page banner | Banner info có icon, `71%` nhấn accent; không thêm nút riêng vì hành động đã ở footer. |
| Footer | 2 hàng như wireframe: thư mục → actions. Select giới hạn 420px ở landscape để không kéo dài vô ích. |
| Card | Bỏ clamp 4 dòng; giữ border 8px, nền trắng, selected = tint accent rất nhẹ + border accent-soft. Không tô đậm cả 11 card. |
| Scroll | Landscape: header cố định, chỉ danh sách cuộn. Portrait: cả head + list cuộn, footer sticky. |
| Dark mode | Dùng token dark sẵn có của extension; axe AA xanh ở 1200px và 392px. |

## Key Assumptions to Validate

- [ ] **Rail cố định đáng chỗ.** Người dùng thật sự quét lại / sửa truy vấn nhiều lần. Đo số lần `Quét trang` trên mỗi phiên; nếu ~1 lần, cân nhắc thu gọn rail sau lần đầu.
- [ ] **Đọc trọn đoạn giúp chọn đúng.** So sánh tỉ lệ bỏ tích / lưu lại với bản clamp 4 dòng; nếu danh sách quá dài, thêm "Mở rộng" thay vì clamp cứng.
- [ ] **% tương đồng không gây nhiễu.** Nếu người dùng bỏ qua badge, gộp thành dòng tổng "11 đoạn · 9 đã xác nhận" hoặc chỉ hiện % cho đoạn chưa thẩm định.
- [ ] **Full-page là lựa chọn phụ.** `Lưu lựa chọn` vẫn là primary dù AI đề xuất lưu toàn bộ. Kiểm tra xem người dùng có bấm nhầm `Lưu toàn bộ` không; nếu có, đổi primary theo mode.
- [ ] **Hai hàng footer không quá cao ở portrait.** Ở 392×760 footer còn 120px; nếu side panel thấp hơn, gộp thư mục vào hàng action hoặc đưa vào menu.
- [ ] **Ngưỡng 1 cột.** Demo dùng 720px viewport; production cần đo container thật (~560–640px) để quyết định.

## MVP Scope (demo này)

- Một màn **kết quả full-page** có dữ liệu thật (11 đoạn, 71%, 7.517 ký tự).
- **Landscape 2 cột** + **portrait 1 cột**; dark mode theo `prefers-color-scheme`.
- Checkbox hoạt động thật; selected state đổi màu card; select thư mục hoạt động; hover/focus-visible đầy đủ.
- Nút API (`Quét trang`, `Dán thủ công`, `Xem trên trang`, `Lưu…`) là tĩnh — chỉ để review bố cục và phân cấp.
- Ảnh chụp: `preview-1200-light.png`, `preview-1200-dark.png`, `preview-1000-light.png`, `preview-721-light.png`, `preview-380-light.png`.

## Not Doing (và vì sao)

- **Các trạng thái idle/loading/empty/error/paste/confirm** — đã ghi đặc tả bên dưới, chưa dựng để giữ demo đúng một màn theo yêu cầu.
- **Gọi API / highlight trên trang / lưu thật** — demo tĩnh, không có JS.
- **`Bỏ chọn` và `Chọn tất cả` hoạt động** — cần state React; checkbox từng đoạn đã đủ để review.
- **Virtualize danh sách** — 11 đoạn chưa cần; production nếu có hàng trăm đoạn thì phải tính.
- **Component hóa, test, axe trong CI** — demo chỉ chạy axe thủ công; code thật phải đưa vào test.
- **Sửa `PageFinderView` hoặc backend** — ngoài phạm vi bước review này.
- **Pixel-perfect Figma** — chưa có Figma; bám token + wireframe.

## Đặc tả trạng thái còn lại (để implement)

| Trạng thái | Vị trí | Nội dung / hành vi |
|---|---|---|
| Idle | Results pane | EmptyState giữa vùng kết quả: "Gom nội dung theo ý bạn" + 3 bước ngắn + link `Dán thủ công`. Rail giữ headline + composer. |
| Đang đọc trang | Results pane | Spinner + "Đang đọc trang…"; composer/buttons disabled; status rail đổi "Đang đọc trang". |
| Đang phân tích | Results pane | Spinner + "Đang phân tích & thẩm định bằng AI…"; có thể là progress 3 bước Đọc → Tìm → Thẩm định. |
| Segments | Results pane | Không banner full-page; footer chỉ `Lưu lựa chọn` + số đoạn. Badge % cho từng đoạn. |
| Rỗng | Results pane | "Không tìm thấy đoạn nào đủ tin cậy" + gợi ý diễn đạt lại / bôi đen thủ công; giữ composer để thử lại; không footer lưu. |
| `PAGE_ACCESS_DENIED` | Results pane | ErrorState + `Cho phép đọc trang` (xin quyền khi bấm) + `Dán thủ công`. |
| `QUOTA_EXCEEDED` | Results pane | ErrorState + `Xem hạn mức` → Cài đặt. |
| `PAGE_TOO_LONG` / `PAGE_NO_CONTENT` | Results pane | ErrorState + gợi ý dán nội dung; không retry vô hạn. |
| `VERIFY_UNAVAILABLE` | Trên danh sách | Banner warn "AI chưa thẩm định được lần này…"; mọi badge chuyển `is-unverified`. |
| Trang bị cắt | Trên danh sách | Banner info "Trang rất dài — chỉ phần đầu (~50.000 ký tự) được quét." |
| Paste mode | Query rail | Đổi headline thành "Dán nội dung để tìm và gom đoạn"; TextArea + đếm ký tự + `Quét nội dung` + `Huỷ dán`; ẩn status trang. |
| Đang lưu | Footer | Buttons busy/disabled; checkbox disabled; toast "Đã lưu 11 đoạn thành ghi chú". |
| Lưu nhiều phần | ConfirmDialog | "Nội dung dài X ký tự, sẽ lưu thành N ghi chú… ~Y token hạn mức"; `Huỷ` / `Lưu`. |
| Lưu lỗi một phần | Error banner | "Đã lưu 1/3 phần. [message]" + thử lại phần còn lại. |
| Không hỗ trợ | Query rail | "Trang này không hỗ trợ quét" (chrome://, PDF viewer…) + `Dán thủ công`. |

## Ghi chú triển khai

- **File:** [`index.html`](index.html) · [`styles.css`](styles.css). Không JS; checkbox/select/hover/focus là native, các nút gọi API là tĩnh.
- **Map component thật:** `PageFinderView` → layout 2 pane; dùng `Field`, `Input`/`TextArea`, `Button`, `Banner`, `Select`, `ConfirmDialog`, `EmptyState`, `ErrorState`, `Spinner`, `Toast` hiện có.
- **Container query:** demo dùng `@media` cho đơn giản (giống demo W03). Production đặt `container-type: inline-size` trên workspace và chuyển layout ở ~560px container, không phải viewport.
- **Rail width:** demo `clamp(340px, 34vw, 408px)`; production chuyển sang token/`cqi`.
- **Full-page:** `result.mode === 'full_page'` → hiện `Lưu toàn bộ` + `~ result.total_chars`; `segments` → ẩn. `Lưu toàn bộ` dùng `result.full_text` (hoặc ghép `items`) như code hiện tại.
- **Selection:** mặc định tích `verified`; `Bỏ chọn` / `Chọn tất cả` đổi nhãn theo `selected.size`. Badge % lấy `score`; `verified` chỉ đổi style/tooltip, không thêm chữ.
- **Highlight:** `Xem trên trang` gọi `pageMatch/highlight` với 1 item; `Xem tất cả trên trang` với toàn bộ; lỗi → toast "Không tìm thấy đoạn trên trang…".
- **Status trang:** kiểm tra URL tab + `chrome.permissions.contains`; không thêm host permission. Ba copy: `Trang có thể quét tự động` / `Cần cấp quyền đọc trang` / `Trang này không hỗ trợ quét`.
- **Footer:** thư mục lấy từ `folders/list`, mặc định Inbox; `buildNoteParts` + ngưỡng `CONFIRM_CHARS = 8_000` giữ nguyên.
- **A11y:** axe WCAG 2.1 AA không vi phạm ở 1200×800 light/dark và 392×760 light/dark; checkbox có accessible name "Chọn đoạn N"; badge có "Độ tương đồng X%"; focus-visible rõ; contrast token đạt AA.

## Open Questions

1. Full-page: có nên đảo primary thành `Lưu toàn bộ` (vì AI đề xuất) hay giữ `Lưu lựa chọn` như demo?
2. Có cần sticky header kết quả ở landscape khi danh sách cuộn dài không? Hiện header đứng yên, chỉ list cuộn.
3. Query box nên là textarea + `Ctrl+Enter` hay input 1 dòng như code hiện tại? Wireframe cho thấy 2 dòng.
4. Có nên giữ `Xem tất cả trên trang` ở header hay đưa vào menu "…" để giảm 2 action cùng hàng?
5. Ngưỡng chuyển 1 cột thật: 560px hay 640px container? Cần đo với side panel Chrome thực tế.

## Cách mở

```bash
xdg-open upgrade-plan/redesign/demo/index.html
```

Hoặc chạy server tĩnh:

```bash
cd upgrade-plan/redesign/demo
python3 -m http.server 8099
# http://localhost:8099
```

Nên xem ở **1200×800** (landscape thoải mái), **1000×760** (cửa sổ mở rộng tham chiếu) và **392×760** / **360×760** (side panel). Dark mode theo cài đặt hệ điều hành.
