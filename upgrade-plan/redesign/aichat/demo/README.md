# Hỏi AI — demo tĩnh cho hướng redesign

> **Trạng thái:** bản thiết kế tham chiếu — **chưa triển khai** · **Phạm vi:** một màn hội thoại, 5 trạng thái, light mode · **Ngày:** 2026-11-13
> Nguồn: wireframe [`../redesign_aichat.svg`](../redesign_aichat.svg) / [`../redesign_aichat.png`](../redesign_aichat.png) · phong cách: [`../../notebook/demo/`](../../notebook/demo/) và [`../../pagematch/demo/`](../../pagematch/demo/) · hành vi hiện tại: `apps/extension/src/ui/features/chat/ChatView.tsx` · tầng dữ liệu: `useChatSessions.ts`, `shared/chat.ts`, `shared/storage/chat-sessions.ts` · phạm vi lịch sử: [`docs/plan/chat-session-history/plan.md`](../../../../docs/plan/chat-session-history/plan.md)

## Problem Statement

> Làm sao để người dùng vừa **đọc câu trả lời có trích dẫn**, vừa **kiểm tra nguồn**, vừa **chuyển giữa các phiên đã lưu** — mà không phải cuộn qua lại giữa dropdown phiên, ô nhập và danh sách nguồn; và vẫn dùng tốt ở cả side panel hẹp lẫn cửa sổ mở rộng?

## Recommended Direction

**Split-view "session rail + hội thoại"** ở cửa sổ mở rộng, thu thành **hội thoại toàn chiều rộng + drawer** ở side panel:

1. **Session rail** (trái, 312px; thu về 292/280px ở màn hẹp): tiêu đề + `Mới`, tìm phiên, danh sách phiên (đang mở / đang trả lời), footer dung lượng + `Quản lý`.
2. **Conversation** (phải): header tiêu đề + trạng thái lưu + `Đổi tên` / `Xoá`; câu trả lời với trích dẫn `[n]` bấm được; hàng **source chip** + `Chi tiết nguồn` thu gọn; composer có phạm vi thư mục, `Gửi` ↔ `Dừng`.
3. **≤880px:** rail thành drawer trượt trái; header còn nút mở phiên + tiêu đề + 2 action icon; composer và nguồn giữ nguyên cấu trúc.

### Vì sao hướng này

- **Lịch sử giờ là nhiều phiên.** Dropdown hiện tại che mất ngữ cảnh và không cho thấy phiên nào đang trả lời. Rail cho chuyển phiên 1 click, thấy ngay thứ tự gần đây và trạng thái live.
- **Nguồn là bề mặt tin cậy.** Chip nằm ngay dưới câu trả lời, chỉ nguồn được trích dẫn mới tô accent; chi tiết (snippet, mở ghi chú, trang nguồn) chỉ mở khi cần, không dựng một bức tường card.
- **Composer là nơi duy nhất để hỏi.** Phạm vi thư mục thuộc composer, không phải một toolbar riêng phía trên; bỏ toolbar giúp vùng hội thoại cao hơn.
- **Dung lượng là ràng buộc thật.** `chrome.storage.local` mặc định 10 MB, không có `unlimitedStorage`; footer hiển thị số phiên + thanh dung lượng + lời nhắc "chỉ lưu trên máy" để người dùng chủ động dọn.
- **Không phá ngôn ngữ thị giác.** Token sáng, accent xanh, font hệ thống, radius 8px, mật độ cozy — lấy từ demo W03 và trang Tìm trong trang.

## Design contract

| Mục | Chốt |
|---|---|
| Job của màn | Hỏi AI trên ghi chú, đọc câu trả lời có trích dẫn, kiểm tra nguồn, và quản lý các phiên lưu cục bộ. |
| Hành động chính | `Gửi` (khi rảnh) ↔ `Dừng` (khi stream). Phụ: mở ghi chú nguồn, `Đổi tên`, `Xoá`, `Quản lý`, `Mới`. |
| Trạng thái bắt buộc | Đã trả lời, đang trả lời, đã dừng, lỗi hạn mức, trống. Demo dựng đủ 5 trạng thái; các trạng thái còn lại ghi ở bảng bên dưới. |
| Responsive | ≥881px: 2 pane; ≤880px: drawer; min 320px. Production nên dùng **container query ~640px** thay viewport query. |
| Từ chối | Gradient, tím/indigo, bo tròn quá mức, shadow dày, copy tiếng Anh, cuộn vô hạn, ghi storage mỗi delta. |

## Những chỗ wireframe ẩn và cách xử lý

| Chi tiết | Quyết định trong demo |
|---|---|
| Header hội thoại | Wireframe đặt `Đổi tên` bên trái, tiêu đề giữa, `Xoá` bên phải. Demo đưa tiêu đề + meta sang trái, 2 action sang phải — dễ quét hơn và khớp các màn khác. |
| Đầu rail | Wireframe có `Mới` + `Tìm…` cùng một hàng, không có tiêu đề. Demo thêm tiêu đề `Hội thoại` + `Mới`, rồi search riêng bên dưới để phân cấp rõ. |
| Số lượt phiên thứ 3 | Wireframe ghi `32 lượt`; demo ghi `16 lượt` vì cap hiện tại là **20 cặp/phiên** (`MAX_MESSAGES_PER_SESSION = 40`). |
| Source chip | Wireframe chỉ có `[1]` kèm tiêu đề; `[2]…[5]` chỉ số. Demo cho mọi chip tiêu đề rút gọn; ≤560px ẩn tiêu đề, giữ `[n]` + `aria-label`. Chip của nguồn **được trích dẫn** tô accent-soft, nguồn không trích dẫn để neutral (giống class `cited` hiện tại). |
| `Nguồn (5)` | Wireframe là một dòng gập. Demo tách thành hàng chip luôn hiện + `Chi tiết nguồn` (`<details>`) chứa snippet và 2 action. |
| Phạm vi thư mục | Wireframe có `> Tất cả thư mục` là một hàng gập "chết". Demo dùng `<select>` native trong composer, kèm số lượng ước tính để chọn được thật. |
| Footer dung lượng | Wireframe: `3 phiên thảo luận`, `4.9/10MB bộ nhớ`, thanh tiến trình, nút `Quản lý`. Demo thêm dòng "Lịch sử chỉ lưu trên máy này." và biến `Quản lý` thành nút full-width. |
| `Quản lý` | Không có trong wireframe. Demo mở sheet: dung lượng, từng phiên + xoá, `Xoá tất cả`, `Đóng`; xoá phiên không ảnh hưởng ghi chú. |
| `Xoá` | Không có trong wireframe. Demo mở confirm nhỏ, nêu rõ tên phiên + số lượt, `Huỷ` / `Xoá phiên`. |
| `Đổi tên` | Không có trong wireframe. Demo đổi tại chỗ: input thay tiêu đề, `Huỷ` / `Lưu`; huỷ bằng label, không reload. |
| Trạng thái trống | Không có trong wireframe. Demo dựng empty state hiện tại: lời hứa "chỉ dựa trên ghi chú", 3 câu hỏi mẫu, ghi chú "không tự thành ghi chú". |
| Trạng thái stream / dừng / lỗi | Không có trong wireframe. Demo bám hành vi hiện tại: caret + pill `Đang trả lời`, pill `Đã dừng` + `Hỏi lại`, card `Đã hết hạn mức AI` + `Xem hạn mức` / `Thử lại`. |
| Câu mở đầu | Wireframe: "Dựa trên nội dung ghi chú…". Demo: "Dựa trên 5 ghi chú bạn đã lưu…" để khớp số nguồn thật. |
| Nút copy | Không có trong wireframe. Demo thêm icon copy ở góc phải mỗi câu trả lời (đã có trong hành vi hiện tại). |

## Key Assumptions to Validate

- [ ] **Rail đáng chỗ ở ≥881px.** Người dùng thật sự chuyển phiên nhiều lần; nếu chủ yếu hỏi liên tiếp trong 1 phiên, cân nhắc rail thu gọn còn icon + tooltip.
- [ ] **Người dùng kiểm tra nguồn thường xuyên.** Đo tỉ lệ bấm chip / mở `Chi tiết nguồn`; nếu thấp, gộp chi tiết vào chip và bỏ dòng `Nguồn (5)`.
- [ ] **Phạm vi thư mục được dùng.** Nếu đa số để "Tất cả thư mục", giữ select nhưng hạ xuống hàng phụ hoặc ẩn sau icon.
- [ ] **Thanh dung lượng có ích.** Người dùng có dọn phiên khi gần đầy không? Nếu không, thêm banner khi >80% thay vì chỉ thanh mảnh ở footer.
- [ ] **Tìm phiên chỉ theo tiêu đề là đủ.** Với 20 phiên, lọc tiêu đề client-side là rẻ; nếu người dùng tìm theo nội dung, cần index hoặc full-text.
- [ ] **Chặn Đổi tên/Xoá khi stream là chấp nhận được.** Demo làm mờ + `pointer-events: none`; nếu người dùng muốn xoá ngay, đổi thành "Dừng rồi xoá".
- [ ] **Chuyển phiên khi stream nên dừng stream.** Demo cho phép (rail không khoá) và dựa vào `switchSession()` hiện tại: dừng, lưu phần đã nhận dạng `stopped`, rồi mở phiên mới. Cần xác nhận không gây mất chữ.
- [ ] **Chip chỉ số là đủ ở ≤560px.** Nếu người dùng không phân biệt được nguồn, cho chip cuộn ngang kèm tiêu đề thay vì ẩn hẳn.

## MVP Scope (demo này)

- Một màn **Hỏi AI** có dữ liệu, light mode, ở 1280×900 (2 pane) và 392×760 (drawer).
- **5 trạng thái** chuyển bằng thanh demo phía trên: Đã trả lời, Đang trả lời, Đã dừng, Lỗi hạn mức, Trống.
- **Session rail:** 3 phiên mẫu, phiên đang mở, chip `Đang trả lời` khi stream, search, `Mới`, footer `3 phiên · 4,9 / 10 MB`, meter, `Quản lý`.
- **Hội thoại:** header + meta `Đã lưu trên máy`; câu trả lời 5 bullet với trích dẫn `[n]`; hàng 5 source chip (cited/uncited); `Chi tiết nguồn` với 5 card snippet + `Mở ghi chú` / `Trang nguồn`.
- **Composer:** select phạm vi thư mục, textarea, hint `Enter để gửi · Shift+Enter xuống dòng`, `Gửi` ↔ `Dừng`.
- **Modal/sheet:** `Quản lý` (dung lượng + xoá từng phiên + `Xoá tất cả`), `Xoá` (confirm), `Đổi tên` (inline).
- **CSS-only:** `:has()`, radio/checkbox ẩn, `<details>`, label `for`; không JavaScript.
- Responsive: 2 pane ≥881px, drawer ≤880px; demo bar xuống 2 dòng ≤560px.

## Not Doing (và vì sao)

- **Dark mode** — yêu cầu review lần này chỉ light mode; token dark để vòng sau.
- **Gọi API / SSE / lưu storage thật** — demo tĩnh, không JS; mọi nút API là tĩnh.
- **Chuyển phiên, tìm phiên, đổi tên, xoá phiên hoạt động thật** — cần state React + RPC mới; demo chỉ review bố cục.
- **Các trạng thái còn lại** (không ngữ cảnh, lỗi mạng, storage đầy, search rỗng, đang tải lịch sử, lỗi lưu tên, xoá phiên đang mở) — đã ghi đặc tả bên dưới, chưa dựng để giữ demo gọn.
- **Nguồn bị xoá / mở ghi chú lỗi** — cần toast + kiểm tra note tồn tại; ngoài phạm vi review bố cục.
- **Virtualize danh sách phiên / tin nhắn** — cap 20 phiên × 40 tin nhắn chưa cần.
- **Component hóa, test, axe trong CI** — demo chỉ kiểm tra thủ công; code thật phải đưa vào test.
- **Container query** — demo dùng viewport media query; production đặt `container-type: inline-size` trên workspace và chuyển layout ở ~640px container.
- **Pixel-perfect Figma** — chưa có Figma; bám token + wireframe.

## Đặc tả trạng thái còn lại (để implement)

| Trạng thái | Vị trí | Nội dung / hành vi |
|---|---|---|
| Không có ngữ cảnh | AI bubble | Backend trả `NO_CONTEXT_ANSWER`: "Mình không tìm thấy ghi chú nào liên quan tới câu hỏi này, nên không trả lời để tránh bịa thông tin. Hãy thử diễn đạt khác, bỏ lọc thư mục, hoặc lưu thêm ghi chú về chủ đề này."; **không** hiện `Nguồn`; UI render như câu trả lời `done`. |
| Lỗi mạng / `AI_UNAVAILABLE` | AI bubble | Error card + `Thử lại`; giữ câu hỏi trong phiên; không tự gửi lại. |
| Lỗi khác (`RATE_LIMITED`, `INTERNAL_ERROR`) | AI bubble | Error card theo `SerializedError`; `Thử lại` trừ khi lỗi không retry được. |
| Câu hỏi rỗng / quá dài | Composer | Rỗng → `Gửi` disabled (demo tĩnh nên luôn bật). `maxlength=2000` chặn gõ; dán quá dài → cắt hoặc hint "Tối đa 2.000 ký tự". `CHAT_INPUT_TOO_LONG` / `CHAT_INPUT_INVALID` từ API → giữ câu hỏi, không thêm vào log. |
| Đang tải lịch sử | Session rail | Skeleton 2–3 dòng; composer disabled đến khi `ready`; tránh nháy "Trống" rồi mới hiện phiên. |
| Tìm phiên rỗng | Session rail | "Không tìm thấy phiên nào" + `Xoá tìm kiếm`; không đổi phiên đang mở. |
| Lưu phiên lỗi / storage đầy | Trên rail hoặc banner | "Không lưu được phiên — bộ nhớ trình duyệt đã đầy." + `Quản lý`; giữ hội thoại trong RAM, không mất câu trả lời đang đọc. |
| Đang đổi tên | Header | Input giữ focus; `Lưu` busy; tên rỗng → giữ form + hint "Tên không được để trống"; `Esc`/`Huỷ` khôi phục tên cũ. |
| Đang xoá phiên | Confirm | Nút `Xoá phiên` busy; xoá phiên đang mở → chuyển sang phiên kế (mới nhất) hoặc về "Cuộc trò chuyện mới"; không tự gửi lại. |
| Xoá tất cả | Sheet | Confirm lần 2 (hoặc nút đỏ có đếm) vì không hoàn tác; xong → rail rỗng + empty state. |
| Phiên đang stream bị đóng panel | Khôi phục | `normalizeRestored()` đã đổi `streaming` → `stopped`, giữ phần text; UI hiện pill `Đã dừng` + `Hỏi lại`. |
| Thư mục đã bị xoá | Composer | `folderId` không khớp option → rơi về "Tất cả thư mục", không lỗi (đã có test UI hiện tại). |
| Nguồn đã bị xoá | Source chip / card | Mở ghi chú lỗi → toast "Ghi chú nguồn không còn tồn tại"; chip vẫn hiện để người dùng biết nguồn cũ. |
| Hết hạn mức giữa phiên | AI bubble | `QUOTA_EXCEEDED` xảy ra trước khi mở SSE nên không có nguồn; card + `Xem hạn mức` như demo. |

## Ghi chú triển khai

- **File:** [`index.html`](index.html) · [`styles.css`](styles.css). Không JS; radio/checkbox/`<details>`/`<select>` là native, các nút API là tĩnh.
- **Map component thật:** `ChatView` → `ChatSessionRail` + `ChatConversation` + `ChatComposer`; dùng `Button`, `Select`, `TextArea`, `Banner`, `ErrorState`, `EmptyState`, `ConfirmDialog`, `ProgressBar` hiện có.
- **Tầng dữ liệu:** `useChatSessions` đã có `switchSession`, `newSession`, `flush`; cần thêm `renameSession(id, title)`, `deleteSession(id)`, `clearSessions()`, `storageUsage()` và filter tiêu đề client-side. Storage thêm RPC `chatSessions/rename|delete|clear|usage` để giữ luật phân tầng (`ui/` không import `shared/storage/`).
- **Cap giữ nguyên:** `MAX_SESSIONS = 20`, `MAX_MESSAGES_PER_SESSION = 40`, `SESSION_TITLE_MAX = 60`. Xoá/đổi tên không đổi cap.
- **Dung lượng:** `chrome.storage.local` mặc định 10 MB (manifest không có `unlimitedStorage`). Đo bằng `chrome.storage.local.getBytesInUse(CHAT_SESSIONS_KEY)`; thanh demo dùng 4,9 MB như số minh hoạ, không phải số thật.
- **Nguồn:** `ChatSource` gồm `index`, `note_id`, `chunk_id`, `title`, `url`, `snippet`. Chip dùng `title` rút gọn + `aria-label` đầy đủ; card dùng `snippet`, `Mở ghi chú` gọi `onOpenNote(note_id)`, `Trang nguồn` chỉ hiện khi `url`.
- **Trích dẫn:** giữ `withCitations()` và regex `\[(\d+)\]`; tập `cited` quyết định chip/card tô accent. Nguồn không được trích dẫn vẫn hiện (RAG trả về cả chunk chưa dùng).
- **Stream:** `sources` là sự kiện **đầu tiên**, trước mọi `delta` (ADR-0009). Vì vậy chip có thể hiện đủ 5 nguồn ngay khi stream; chỉ trạng thái `cited` tăng dần. `Chi tiết nguồn` khoá đến khi `done`/`stopped`.
- **Lỗi hạn mức:** `QUOTA_EXCEEDED` → `Xem hạn mức` mở Cài đặt; copy không hứa "reset lúc 00:00" vì backend chỉ reset qua `reset_demo`/quản trị.
- **Stopped:** `status === 'stopped'` giữ text đã nhận; `Hỏi lại` gửi lại đúng câu hỏi cũ (cần lưu `question` của lượt đó hoặc lấy từ message user liền trước).
- **A11y:** chip có `aria-label` "Nguồn N: tiêu đề"; drawer/modal cần focus trap + `Esc` (JS thật); demo chỉ có focus-visible cho label. Ở ≤560px tiêu đề chip ẩn nhưng `aria-label` vẫn đủ.
- **Token:** `--bg #ffffff`, `--surface #f6f8fa`, `--fg #1f2328`, `--muted #59636e`, `--border #d0d7de`, `--accent #0b57d0`; radius 8px, font hệ thống.

## Open Questions

1. Rail rộng **312px** (demo) hay **320px** ở 1000–1200px? Demo dùng 312px và thu về 292/280px ở màn hẹp để nhường chỗ cho câu trả lời.
2. Chuyển phiên khi đang stream: **cho phép** (dừng + lưu `stopped`) như demo, hay **khoá rail** như Select hiện tại?
3. `Đổi tên` nên **inline** như demo hay mở modal? Inline giữ ngữ cảnh nhưng header thấp; modal rõ hơn khi tên dài.
4. `Xoá tất cả` có cần **confirm lần 2** hay chỉ nút đỏ + đếm số phiên?
5. Nguồn: hiện **tất cả** chunk RAG trả về (demo) hay chỉ nguồn được trích dẫn? Hiện tất cả giúp người dùng thấy cả nguồn AI bỏ qua.
6. Số lượng thư mục trong composer: **API mới** (`notes/countByFolder`) hay đếm client-side từ cache ghi chú?
7. Empty state: giữ 3 câu mẫu cố định hay **cá nhân hóa** từ ghi chú gần đây?
8. Tìm phiên: chỉ **tiêu đề** (demo) hay cả nội dung? Full-text cần index, không rẻ với 20 phiên.
9. Ngưỡng chuyển 1 pane: **640px** hay **720px** container? Cần đo side panel Chrome thật (320–400px) và cửa sổ mở rộng (~1000px).
10. Có cần **ghim phiên** hoặc **nhóm theo ngày** trong rail khi đủ 20 phiên không?

## Cách mở

Mở trực tiếp:

```bash
xdg-open upgrade-plan/redesign/aichat/demo/index.html
```

Hoặc chạy server tĩnh trong thư mục demo:

```bash
cd upgrade-plan/redesign/aichat/demo
python3 -m http.server 8098
# http://localhost:8098
```

Nên xem ở **1280×900** (2 pane, đủ cả nguồn lẫn `Chi tiết nguồn`) và **392×760** (side panel, drawer). Thanh **DEMO** phía trên chỉ để đổi trạng thái review — không thuộc sản phẩm. Demo không kèm ảnh chụp sẵn; mở trực tiếp để xem đủ 5 trạng thái và các modal.
