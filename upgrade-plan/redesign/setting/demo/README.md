# Cài đặt — demo tĩnh cho hướng redesign

> **Trạng thái:** bản thiết kế tham chiếu — **đã triển khai** vào [`SettingsView.tsx`](../../../../apps/extension/src/ui/features/account/SettingsView.tsx) và [`ProviderCard.tsx`](../../../../apps/extension/src/ui/features/account/ProviderCard.tsx) · **Phạm vi:** 3 mục Cài đặt, 6 trạng thái demo, 4 hộp thoại, light mode · **Ngày:** 2026-11-19
> Nguồn: wireframe [`../redesign_setting.svg`](../redesign_setting.svg) / [`../redesign_setting.png`](../redesign_setting.png) · phong cách: [`../../aichat/demo/`](../../aichat/demo/) và [`../../pagematch/demo/`](../../pagematch/demo/) · hành vi hiện tại: [`SettingsView.tsx`](../../../../apps/extension/src/ui/features/account/SettingsView.tsx), [`ProviderCard.tsx`](../../../../apps/extension/src/ui/features/account/ProviderCard.tsx) · tầng dữ liệu: [`protocol.ts`](../../../../apps/extension/src/shared/messaging/protocol.ts), [`types.ts`](../../../../apps/extension/src/shared/api/types.ts) · luồng: [`docs/ux/ui-map.md`](../../../../docs/ux/ui-map.md)

## Problem Statement

> Làm sao để người dùng cấu hình AI (dùng server hay endpoint riêng), quản lý tài khoản/hạn mức và tuỳ chọn lưu nhanh trong **một màn Cài đặt** — mà không phải cuộn qua một cột form dài, vẫn hiểu được các hành vi ẩn (khoá API, kiểm tra kết nối, dựng lại chỉ mục), và vẫn dùng tốt ở cả side panel hẹp lẫn cửa sổ mở rộng?

## Recommended Direction

**Settings shell chia 3 mục, mỗi mục một pane độc lập.** Rail dọc ở cửa sổ rộng (236px), thu thành hàng tab ngang ở side panel:

1. **Chung** — thư mục mặc định khi lưu nhanh, hiện/ẩn tab “Tìm kiếm”, thông tin phiên bản. Các tuỳ chọn này **lưu ngay** khi đổi, không có nút Lưu.
2. **Tài khoản** — hồ sơ, hạn mức AI (token), đăng xuất, xoá tài khoản 2 bước.
3. **Dịch vụ AI** — chọn nguồn AI; form endpoint riêng với preset, URL, khoá API, model chat/embedding; `Kiểm tra kết nối` + `Lưu` ngay cuối form; kết quả test và cảnh báo nằm cạnh hành động; `Nâng cao` chứa timeout.

### Vì sao hướng này

- **Ba câu hỏi khác nhau, ba mục khác nhau.** “Lưu ghi chú thế nào”, “tài khoản của tôi ra sao”, “AI gọi đi đâu” không cần nằm chung một cột. Rail giúp nhảy thẳng tới phần cần sửa và giữ màn Dịch vụ AI đủ rộng cho form 2 cột ở desktop.
- **Dịch vụ AI là phần sâu nhất, cần một pane riêng.** Wireframe đã đúng khi tách `Cấu hình Endpoint` khỏi các card tài khoản; demo giữ nguyên thứ tự thông tin: nguồn AI → preset → endpoint → khoá → model → kiểm tra/lưu → nâng cao.
- **Phản hồi nằm cạnh hành động.** `Kiểm tra kết nối` và banner kết quả ở cùng vùng mắt; không dùng sticky footer hay toast cho lỗi cấu hình. Người dùng thấy ngay embedding trả bao nhiêu chiều, chat có phản hồi không, và cấu hình đã sẵn sàng lưu chưa.
- **Không phá ngôn ngữ thị giác.** Token sáng, accent xanh `#0b57d0`, radius 8px, font hệ thống, mật độ cozy — lấy từ `apps/extension/src/ui/styles.css`. Không gradient, không indigo, không shadow dày.
- **Tái dùng component hiện có.** `Field`, `Input`, `Select`, `Button`, `Banner`, `ProgressBar`, `ConfirmDialog`, `Spinner`; chỉ thêm một control segmented bằng radio native.

## Design contract

| Mục | Chốt |
|---|---|
| Job của màn | Cấu hình AI, quản lý tài khoản/hạn mức, và đặt tuỳ chọn lưu nhanh. |
| Hành động chính | Dịch vụ AI: `Kiểm tra kết nối` → `Lưu` (có thể mở confirm dựng lại chỉ mục). Tài khoản: `Đăng xuất`, `Xoá tài khoản…`. |
| Trạng thái bắt buộc | Sạch, đang kiểm tra, kết nối tốt, lỗi kết nối, chưa lưu, chưa kiểm tra. Demo dựng đủ 6 trạng thái; các trạng thái còn lại ghi ở bảng bên dưới. |
| Responsive | ≥880px: rail 236px + pane nội dung tối đa 820px; ≤879px: rail thành hàng tab ngang 44px, pane toàn chiều rộng. Demo kiểm ở 1280×900 và 392×760. |
| Từ chối | Gradient, tím/indigo, active nav tô đặc theo wireframe, sticky footer, toast cho lỗi cấu hình, JS trong demo. |

## Những chỗ wireframe ẩn và cách xử lý

| Chi tiết | Quyết định trong demo |
|---|---|
| Wireframe chỉ có Dịch vụ AI | Bổ sung **Chung** và **Tài khoản** từ hành vi thật của `SettingsView`; không thêm tính năng mới ngoài phạm vi. |
| Active nav trong wireframe | Wireframe tô xanh đặc + mũi tên `>`. Demo dùng nền `--accent-soft`, viền `--accent-soft-border`, chữ `--accent` và chevron — khớp ngôn ngữ hiện tại, đỡ nặng mắt. |
| Header + email ở topbar | Wireframe lặp email ở topbar và footer. Demo giữ topbar để mô phỏng cửa sổ mở rộng, nhưng ẩn email ở ≤620px; **Về QuickAssist** mở từ icon info ở footer rail (wide) hoặc nút `Xem thông tin` trong mục Chung (narrow). |
| Nguồn AI (`inherit` / `byok`) | Thêm segmented **“Dùng AI của server” / “Endpoint riêng”**, không có trong wireframe. Đây là state ẩn quan trọng nhất của `AiSettings.mode`. |
| Server đang áp dụng | Khi chọn AI của server, form endpoint ẩn và hiện card read-only: provider, model chat, model embedding, timeout, badge `Đang áp dụng`. |
| Preset | Wireframe có 4 (`OpenAI`, `Gemini`, `llama.cpp`, `Tuỳ chỉnh`). Demo giữ đủ **6** preset hiện có, thêm `Ollama` và `LM Studio`; hàng tab cuộn ngang ở side panel. Nhãn rút gọn `Gemini` / `Ollama` cho vừa hàng tab. |
| Preset đang chọn | Wireframe gạch chân `Tuỳ chỉnh`. Demo chọn sẵn `llama.cpp` để minh hoạ URL localhost + placeholder khoá “tuỳ chọn”; bấm `Tuỳ chỉnh` để đổi underline. Demo **không tự điền** giá trị khi đổi preset — xem “Not Doing”. |
| Model fields | Wireframe chỉ có helper text. Demo giữ **input + datalist** như hiện tại, tách helper thành 2 dòng: chức năng dùng model (`Hỏi AI`, `Tìm kiếm ngữ nghĩa`) và gợi ý từ preset. Không có nút “Quét model”. |
| Khoá API | Không bao giờ hiển thị khoá đã lưu. Placeholder đổi theo ngữ cảnh (`llama.cpp` → tuỳ chọn); hint nói rõ khoá mã hoá trên server, gõ mới để thay, bỏ trống để giữ. Demo chưa dựng state “Đã lưu sk-…” + `Xoá key` — xem bảng trạng thái. |
| `Kiểm tra kết nối` | Kết quả thành công nêu **model + số chiều + latency** của embedding và **model + latency** của chat, đúng dữ liệu `AiTestResult`; lỗi nêu bước (`embedding` / `chat`) và message. Test cũ bị vô hiệu khi provider/base_url/embedding model đổi. |
| `Lưu` | Demo đặt cạnh `Kiểm tra kết nối` theo wireframe. Production hiện đặt sau `Nâng cao`; hướng này đưa hành động lên trước phần ít dùng. |
| Dựng lại chỉ mục | Đổi fingerprint embedding (provider/base_url/model) hoặc chuyển từ server sang BYOK, và `rebuild_note_count > 0` → confirm trước khi lưu. Demo dựng hộp thoại với **42 ghi chú** minh hoạ; số thật lấy từ server. |
| `Nâng cao…` | Wireframe là một hàng gập. Demo dùng `<details open>`: mở sẵn để review timeout, vẫn thu gọn được. Timeout để **trống = mặc định server 90 giây**, khoảng 5–600. |
| Checkbox tab “Tìm kiếm” | Wireframe không có. Demo nối checkbox với tabbar bằng `:has()`: bật → tab “Tìm kiếm” xuất hiện sau Thư viện; tắt → tab biến mất. Đúng `showSearchTab`, mặc định `false`. |
| Thư mục mặc định | Demo hard-code 4 thư mục mẫu. Production lấy `folders/list`, lưu ngay qua `prefs/set`, có option rỗng nếu chưa chọn. |
| Hạn mức | Wireframe không có. Demo dùng đơn vị **token**, thanh tiến trình `used + reserved / limit`; số 796/1.105 là minh hoạ. Ẩn nút `Đặt lại số liệu` của BYOK trong bản demo server-mode. |
| Xoá tài khoản | Wireframe chỉ có icon user/info. Demo giữ flow thật: card danger → bước 1/2 liệt kê dữ liệu mất → bước 2/2 gõ `XOÁ`. Nút xoá thật bị disable đến khi khớp; demo ghi chú điều đó. |
| Icon info ở footer | Không có trong wireframe. Demo biến nó thành nút mở **Về QuickAssist**: phiên bản, nơi lưu ghi chú/lịch sử, cách xử lý khoá API. |
| Nút `Làm mới` hạn mức | Có trong hành vi thật, không có trong wireframe. Demo giữ ở góc phải card hạn mức. |
| Đăng xuất ở local mode | Hiện tại bị ẩn khi `authMode === 'local'` (tự đăng nhập lại ngay). Demo hiển thị để review; implementation phải giữ điều kiện ẩn. |

## Key Assumptions to Validate

- [ ] **Rail đáng chỗ ở ≥880px.** Người dùng có mở Cài đặt đủ thường xuyên để cần rail cố định? Nếu chủ yếu sửa AI một lần, cân nhắc thu rail còn icon + tooltip.
- [ ] **Segmented “AI của server / Endpoint riêng” dễ hiểu hơn nút “Dùng cấu hình server”.** Nó làm rõ state hiện tại, nhưng thêm một bước trước khi thấy form.
- [ ] **Hàng preset cuộn ngang ổn ở side panel.** Nếu người dùng không phát hiện preset bị khuất, đổi thành `<select>` ở ≤620px.
- [ ] **Đặt `Kiểm tra`/`Lưu` trước `Nâng cao` đúng ý.** Nếu timeout được chỉnh thường xuyên, giữ `Nâng cao` mở hoặc đưa timeout lên gần model.
- [ ] **Server summary đủ tin cậy.** Người dùng có cần xem chi tiết hơn (base URL? key đã cấu hình?) hay chỉ cần provider + model?
- [ ] **Chuyển về AI server luôn cần confirm.** Hiện tại chỉ confirm khi có ghi chú cần dựng lại; nếu việc xoá key/config là mất mát, nên confirm mọi lần.
- [ ] **Info icon mở sheet là đủ.** Hay cần link tới trang tài liệu / changelog / “Kiểm tra cập nhật”.
- [ ] **Badge “Tài khoản demo” chỉ là dữ liệu mẫu.** Production nên thay bằng auth provider hoặc bỏ badge.
- [ ] **Số liệu minh hoạ không gây hiểu nhầm.** 796/1.105 token, 768 chiều, 42 ghi chú đều là mock; implementation phải lấy từ RPC.

## MVP Scope (demo này)

- Một màn **Cài đặt** đủ 3 mục, light mode, ở **1280×900** (rail dọc) và **392×760** (tab ngang).
- **6 trạng thái** chuyển bằng thanh demo: Mặc định, Đang kiểm tra, Kết nối tốt, Lỗi kết nối, Chưa lưu, Chưa kiểm tra.
- **Chung:** select thư mục, checkbox tab Tìm kiếm có hiệu lực lên tabbar, card phiên bản mở sheet.
- **Tài khoản:** profile, quota meter + `Làm mới`, `Đăng xuất`, danger zone + 2 bước xoá.
- **Dịch vụ AI:** segmented nguồn AI; server summary; 6 preset; URL; khoá API + `Hiện`; 2 model + datalist + helper; test/lưu + banner; `<details>` nâng cao với timeout.
- **4 hộp thoại:** Về QuickAssist, xoá tài khoản bước 1/2, bước 2/2, dựng lại chỉ mục.
- **CSS-only:** `:has()`, radio/checkbox ẩn, `<details>`, label `for`; không JavaScript.
- Thanh **DEMO** phía trên chỉ để review trạng thái — không thuộc sản phẩm.

## Not Doing (và vì sao)

- **Dark mode** — yêu cầu review lần này chỉ light mode; token dark để vòng sau.
- **Gọi API / RPC thật** — demo tĩnh, không JS; mọi nút `Lưu`, `Kiểm tra`, `Đăng xuất`, `Xoá` đều là tĩnh.
- **Quét model / tải danh sách model từ endpoint** — hiện tại là input + datalist; thêm scan cần API mới.
- **Tự điền form khi đổi preset** — demo chỉ đổi underline; production dùng `PRESETS` để điền provider/base_url/model như `ProviderCard` hiện tại.
- **Đồng bộ thư mục thật** — `folders/list` chưa nối; select dùng dữ liệu mẫu.
- **Quota/BYOK reset** — demo đang ở chế độ AI server; nút `Đặt lại số liệu` và nhãn “Đã dùng (key của bạn)” chưa dựng.
- **OAuth / mở trang đăng nhập** — ngoài phạm vi review bố cục.
- **Toast, optimistic update, focus trap, Esc, khoá scroll nền** — cần JS; demo chỉ có `:focus-visible` cho label và native `<details>`.
- **Container query** — demo dùng viewport media query; production nên đặt `container-type: inline-size` trên workspace và chuyển layout theo container.
- **Pixel-perfect Figma** — chưa có Figma; bám token + wireframe.

## Đặc tả trạng thái còn lại (để implement)

| Trạng thái | Vị trí | Nội dung / hành vi |
|---|---|---|
| Đang tải cấu hình AI | Card Dịch vụ AI | Skeleton hoặc `Spinner` + “Đang tải cấu hình AI…”; ẩn form và nút Lưu để tránh ghi đè. |
| Lỗi tải cấu hình | Card Dịch vụ AI | `ErrorState` + `Thử lại`; không hiện form rỗng. |
| Chưa có khoá / đã lưu khoá | Field khoá API | Chưa có: placeholder `sk-… (tuỳ chọn)` (hoặc “tuỳ chọn” với model local). Đã có: placeholder `••••••••`, hint `Đã lưu <key_hint>`, nút `Xoá key`; bấm → chuyển `clearKey`, hiện `Giữ key cũ`. |
| Xoá khoá | Field khoá API | `clearKey = true` gửi `api_key: ""` khi Lưu; không xoá ngay. Nếu đổi ý, `Giữ key cũ` khôi phục. |
| Test cũ / đã đổi field | Banner test | Test chỉ còn hiệu lực khi `provider`, `base_url`, `embedding_model` chưa đổi. Đổi → ẩn kết quả cũ, hiện cảnh báo “Cấu hình chưa được kiểm tra”; vẫn cho Lưu nhưng khuyến khích test trước. |
| Lưu khi chưa test | Banner cảnh báo | `warnUntested` hiện banner vàng; bấm Lưu vẫn gửi (server là guard cuối), trừ khi embedding > 1536 chiều. |
| Embedding > 1536 chiều | Banner lỗi + nút Lưu | Test trả `embedding_dim > 1536` → banner đỏ, disable `Lưu`; đổi model/endpoint để test lại. |
| Đang lưu | Nút Lưu | Busy + disable test/preset; lỗi `ai/config/set` hiện `ErrorState` ngay trên hàng action, giữ nguyên form. |
| Lưu xong | Banner | `afterSave` đóng form cũ, xoá test, cập nhật quota; nếu `rebuild.required` hiện banner “Đang dựng lại chỉ mục của N ghi chú” + `Ẩn`. |
| Chuyển về AI server | Segmented / confirm | Gọi `ai/config/reset`. Nếu `rebuild_note_count > 0`, confirm “Dùng lại cấu hình server?” và “Chuyển và dựng lại”; nếu 0, đổi ngay. Cân nhắc confirm cả khi 0 vì mất key/config. |
| Timeout không hợp lệ | Field timeout | Trống → gửi `null` (server mặc định 90). Ngoài 5–600 hoặc không phải số → chặn Lưu, hint đỏ; không tự kẹp giá trị. |
| Thư mục rỗng | Select thư mục | Option “— Chưa chọn —” + hint “Tạo thư mục trong Thư viện trước”; lưu `defaultFolderId: null`. |
| Tắt tab Tìm kiếm khi đang mở | App shell | `useEffect` hiện tại chuyển về Thư viện; demo không mô phỏng vì đang đứng ở Cài đặt. |
| Hết hạn mức | Card hạn mức | Banner vàng: ghi chú mới vẫn lưu nhưng không tìm ngữ nghĩa/tóm tắt được; BYOK hiện `Đặt lại số liệu`. |
| BYOK quota | Card hạn mức | Nhãn “Đã dùng (key của bạn)”; nút `Đặt lại số liệu`; ghi rõ lời gọi vẫn tính vào hạn mức server. |
| Đăng xuất | Card phiên | Busy trên nút; lỗi hiện `ErrorState`; thành công đóng side panel hoặc về trạng thái đăng nhập. Local mode ẩn card. |
| Xoá tài khoản bước 2 | ConfirmDialog | Chỉ bật `Xoá vĩnh viễn` khi gõ đúng `XOÁ`; busy; lỗi giữ hộp thoại; thành công reset session. |
| Phiên hết hạn | Toàn màn | 401 → hiện trạng thái đăng nhập lại; không giữ form AI cũ. |

## Ghi chú triển khai

> **Đã áp dụng (2026-11-19):** `SettingsView` chia 3 mục bằng state React (`initialSection` cho “Xem hạn mức” → Tài khoản); `ProviderCard` thành thân mục Dịch vụ AI (segmented nguồn, 6 preset cuộn ngang, server summary, test/save inline, banner chưa lưu/chưa kiểm tra, `details` Nâng cao); `.settings-*` trong `styles.css` dùng token A05; rail dọc ≥880px, hàng tab ngang ≤879px. Các quyết định đã chốt theo demo: giữ segmented, preset cuộn ngang, `Lưu` trước Nâng cao, badge `Google`/`Tự host`, reset quota trong card Tài khoản.

- **File:** [`index.html`](index.html) · [`styles.css`](styles.css). Không JS; radio/checkbox/`<details>` là native, các nút API là tĩnh.
- **Map component thật:** tách `SettingsView` thành `SettingsGeneral` + `SettingsAccount` + `SettingsAi` (hoặc giữ `ProviderCard` làm thân mục AI). Dùng `Field`, `Input`, `Select`, `Button`, `Banner`, `ProgressBar`, `ConfirmDialog`, `Spinner` hiện có.
- **Navigation:** production dùng state `'general' | 'account' | 'ai'` (hoặc nested route); demo dùng radio + `:has()` để không cần JS. Không thêm RPC cho navigation.
- **AI mode:** đọc `cfg.data.mode` (`inherit` / `byok`). `byok` → hiện form; `inherit` → hiện server summary từ `cfg.data.server_default`. Chuyển sang `inherit` gọi `ai/config/reset`.
- **Save AI:** giữ `buildInput()` và `afterSave()` của `ProviderCard`; `mode: 'byok'`; `api_key` chỉ gửi khi gõ mới (`null` = giữ, `""` = xoá); `embedding_dim` chỉ gửi khi test khớp form.
- **Rebuild:** fingerprint hiện tại là `provider | base_url | embedding_model`. Confirm trước khi gọi `ai/config/set` nếu `embedFieldsChanged || mode !== 'byok'` và `rebuild_note_count > 0`. Sau lưu, banner dùng `res.rebuild.notes`.
- **Test:** `ai/config/test` nhận cùng input trừ `mode`/`embedding_dim`; kết quả `stage`, `message`, `embedding.model/dim/padded/latency_ms`, `chat.model/latency_ms/sample`.
- **Preset:** dùng mảng `PRESETS` sẵn có; nhãn tab rút gọn nhưng `aria-label` giữ tên đầy đủ (`Google Gemini`, `Ollama (local)`). Sửa tay bất kỳ field nào → preset về `Tuỳ chỉnh` (hoặc bỏ chọn) như hành vi hiện tại.
- **Chung:** `prefs/set` lưu ngay từng thay đổi; `showSearchTab` mặc định `false`; `defaultFolderId` lấy từ `folders/list`.
- **Tài khoản:** `session.user` (`display_name`, `email`, `avatar_url`, `created_at`), `session.authMode === 'local'` ẩn đăng xuất. `quota/get` trả `used_tokens`, `reserved_tokens`, `limit_tokens`, `remaining_tokens`, `billing_mode`. `account/delete` là RPC xoá thật.
- **Token:** `--bg #ffffff`, `--surface #f6f8fa`, `--fg #1f2328`, `--muted #59636e`, `--border #d0d7de`, `--accent #0b57d0`; radius 8px, font hệ thống. Không dùng màu xanh bão hoà của wireframe cho active nav.
- **Responsive:** rail dọc ≥880px; ≤879px rail thành tab ngang. Production nên chuyển theo **container query** vì side panel và cửa sổ mở rộng có cùng viewport nhưng khác bề rộng khả dụng.
- **A11y:** segmented/preset là radio group native (arrow key hoạt động); `summary` có focus ring; dialog cần focus trap + `Esc` + `aria-modal` trong bản React; `aria-describedby` đã nối cho hint; nút icon có `title`/`aria-label`.
- **Số liệu mock:** 796/1.105 token, 42 ghi chú, 768 chiều, 124ms/642ms, 27/09/2026. Không dùng làm giá trị mặc định trong code.

## Open Questions

1. **Breakpoint:** 880px như demo, hay theo container ~720px? Side panel Chrome thường 320–400px; cửa sổ mở rộng có thể 700–1000px.
2. **Segmented nguồn AI:** giữ như demo, hay quay lại nút `Dùng cấu hình server` hiện tại để form luôn hiện và giảm một lớp?
3. **Confirm khi chuyển về server:** luôn confirm, hay chỉ khi `rebuild_note_count > 0` như code hiện tại? Nếu luôn, copy cần nói rõ key/config bị xoá.
4. **Preset ở side panel:** hàng tab cuộn ngang (demo) hay `<select>` để không bỏ sót preset?
5. **Vị trí `Lưu`:** trước `Nâng cao` (wireframe, demo) hay sau `Nâng cao` (code hiện tại)? Ảnh hưởng thứ tự tab khi bàn phím.
6. **Lưu ngay ở mục Chung:** có cần toast xác nhận, hay chỉ cần dòng “Thay đổi được lưu ngay” như demo?
7. **Info icon:** mở sheet như demo, hay mở trang “Giới thiệu / Phiên bản” riêng? Có cần nút kiểm tra cập nhật?
8. **Badge tài khoản:** bỏ hẳn, hay thay bằng provider đăng nhập (`Google`, `Tự host`)?
9. **Quota BYOK:** đặt `Đặt lại số liệu` trong card hạn mức hay trong mục Dịch vụ AI? Demo chưa dựng state này.
10. **Xoá tài khoản:** giữ chữ xác nhận `XOÁ` (không dấu) như code hiện tại, hay dùng `XÓA`? Cần thống nhất copy và test.

## Cách mở

Mở trực tiếp:

```bash
xdg-open upgrade-plan/redesign/setting/demo/index.html
```

Hoặc chạy server tĩnh trong thư mục demo:

```bash
cd upgrade-plan/redesign/setting/demo
python3 -m http.server 8099
# http://localhost:8099
```

Nên xem ở **1280×900** (rail dọc, đủ form AI) và **392×760** (side panel, tab ngang). Thanh **DEMO** phía trên chỉ để đổi trạng thái review — không thuộc sản phẩm. Demo không kèm ảnh chụp sẵn; mở trực tiếp để xem 6 trạng thái, 4 hộp thoại và hai bố cục.
