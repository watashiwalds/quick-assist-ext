# Bản đồ UI QuickAssist Extension

Map nhanh các **màn hình** và **chức năng** của extension hiện có (MV3, `apps/extension`).
UI gọi background qua RPC (`qa-rpc`) — UI không gọi API trực tiếp; background giữ token,
outbox (IndexedDB) và phát broadcast (`qa-event`) cho mọi UI đang mở (ADR-0007).

Mở file này trong VS Code (Mermaid preview) hoặc GitHub để xem sơ đồ.
Ảnh chụp từng màn nằm trong `docs/ux/screens/`.

---

## 1. Tổng quan bề mặt (surfaces & điểm vào)

```mermaid
flowchart TB
    subgraph WebPage["Trên trang web"]
        TOAST["Toast — Shadow DOM (content/injected.ts)<br/>5s đếm ngược · Hoàn tác (Alt+Shift+Z)<br/>role=status, aria-live=polite"]
    end

    subgraph ChromeUI["Chrome UI"]
        CTX["Context menu — chỉ trên vùng chọn (background/menus.ts)<br/>1. Ghi chú văn bản này → thư mục mặc định (Inbox nếu chưa đặt)<br/>2. Ghi chú vào thư mục ▸ — tối đa 15 thư mục (từ cache, dùng được offline)<br/>3. Tóm tắt đoạn văn bản này → mở side panel ở tab Tóm tắt"]
        POPUP["Popup (toolbar) — src/ui/popup/Popup.tsx<br/>Lời chào · hạn mức AI · nút Mở thư viện ghi chú"]
        SP["Side Panel — src/ui/sidepanel/App.tsx<br/>Thư viện (tìm nhanh + tìm sâu AI) · Tìm trong trang · Hỏi AI · Tóm tắt* · Cài đặt<br/>(* Tóm tắt chỉ hiện khi có vùng chọn chờ · tab 'Tìm kiếm' ẩn mặc định, bật lại trong Cài đặt)"]
    end

    KB["Alt+Shift+N (command quick-note, đổi được ở<br/>chrome://extensions/shortcuts)"] --> TOAST
    CTX -->|lưu nhanh / lưu vào thư mục| TOAST
    CTX -->|tóm tắt vùng chọn| SP
    POPUP -->|Mở thư viện ghi chú| SP

    TOAST -->|"hết 5s → gửi"| OUTBOX[("Outbox — IndexedDB<br/>notBefore = now + 5s (undo window)")]
    TOAST -->|Hoàn tác trong 5s| UNDO["quickNote/undo → xoá khỏi outbox,<br/>ghi chú không được lưu"]
    OUTBOX -->|"flush: hết undo window · alarm 1′ · lúc khởi động"| BG
    BG["Service worker (background/index.ts)<br/>RPC qa-rpc · broadcast qa-event · giữ token<br/>retry backoff 10s→15′, tối đa 8 lần<br/>lỗi vĩnh viễn → store 'failed' → banner trong Thư viện"]
    BG --> API["Backend API (apps/api)"]
```

---

## 2. Side Panel — khung chung & đăng nhập

```mermaid
flowchart TB
    HDR["Header: QuickAssist + email đang đăng nhập"] --> AUTH{"AuthGate<br/>đã đăng nhập?"}
    AUTH -->|chưa| SIGNIN["Màn đăng nhập — AuthGate.tsx<br/>QuickAssist · giới thiệu · nút Đăng nhập bằng Google<br/>Google OAuth (chrome.identity + PKCE)<br/>lỗi có nút Thử lại · ghi chú privacy"]
    AUTH -->|rồi| TABS["Tabs (Tabs.tsx): Thư viện · Tìm trong trang · Hỏi AI · (Tóm tắt) · Cài đặt<br/>'Tóm tắt' chỉ hiện khi có vùng chọn chờ · 'Tìm kiếm' ẩn mặc định<br/>(đã gộp vào thanh tìm của Thư viện, bật lại trong Cài đặt)"]
```

---

## 3. Tab Thư viện — `NotesView.tsx`

```mermaid
flowchart TB
    PN["PendingNotes — banner 'ghi chú chưa gửi'<br/>khi có mục failed / queued đang thử lại<br/>Xem/Ẩn · Gửi lại · Bỏ (xác nhận)"] --> F1
    F1["Lọc theo thư mục (Select) + nút Thư mục"] --> F2["Thanh tìm gộp (R04): gõ → lọc nhanh từ khoá (không dấu cũng được)<br/>Enter → tìm sâu bằng AI · số kết quả 5/10/20<br/>Chọn/Xong (multi-select) · ⟳ Đồng bộ (notes/sync)"]
    F2 --> MULTI["Chế độ chọn: Chọn tất cả · Xoá (n)<br/>→ ConfirmDialog xoá hàng loạt"]
    F2 --> CARDS
    F2 -->|Enter| AIHITS["Kết quả tìm sâu AI thay vùng danh sách:<br/>thẻ xếp theo RRF (thứ hạng · tiêu đề · đoạn khớp · điểm)<br/>'Mở ghi chú' → mở ngay khung đọc · 'Mở trang nguồn ↗'<br/>QUOTA_EXCEEDED → 'Xem hạn mức' (→ Cài đặt)<br/>'← Về danh sách' · gõ tiếp → quay về lọc nhanh"]

    CARDS["Danh sách NoteCard<br/>StatusBadge: Đang xử lý / Sẵn sàng tìm kiếm / Bỏ qua (hết quota) / Lỗi xử lý AI<br/>tiêu đề · nội dung (clamp) · 'Tóm tắt đã lưu' · ngày · thư mục · tên miền"]

    CARDS -->|Sửa| NOTES_EDIT["NoteEditor — modal (NoteEditor.tsx)<br/>Tiêu đề · Nội dung (≤ 20 000 ký tự, đếm trực tiếp) · Thư mục<br/>Lưu = PATCH kèm version (optimistic concurrency)"]
    NOTES_EDIT -->|409 NOTE_VERSION_CONFLICT| CONFLICT["Xung đột phiên bản<br/>→ 'Xem bản mới nhất' (bỏ thay đổi)<br/>hoặc 'Ghi đè bằng bản của tôi'"]

    CARDS -->|FAILED / SKIPPED| REINDEX["Thử lại AI (notes/reindex)"]
    CARDS -->|Xoá| DEL["ConfirmDialog xoá (một hoặc nhiều)"]
    CARDS -->|Tóm tắt| SUMPANEL["SummaryPanel (SummaryPanel.tsx)<br/>'Tóm tắt bằng AI' / 'Tóm tắt lại' → bản xem trước<br/>'Lưu tóm tắt' (kèm version) · 'Huỷ'"]

    F1 -.->|Thư mục| FM["FolderManager — modal (FolderManager.tsx)<br/>Tạo (≤100 ký tự) · Đổi tên · Xoá<br/>Xoá thư mục → ghi chú về Inbox, không mất<br/>thư mục mặc định (is_default) không sửa/xoá được"]
```

---

## 4. Tìm kiếm — gộp vào thanh tìm của Thư viện (R04)

Tìm kiếm ngữ nghĩa đã gộp vào **thanh tìm kiếm của tab Thư viện**: gõ → lọc nhanh trong danh sách
đã tải; nhấn **Enter** → gọi `search/query` (AI) với chính từ khoá đó + thư mục đang chọn.
Tab "Tìm kiếm" riêng (`SearchView.tsx`) **ẩn mặc định** — bật lại bằng tuỳ chọn trong Cài đặt
(`showSearchTab`), khi đó vẫn hành xử như mô tả dưới đây.

```mermaid
flowchart TB
    FORM["Form (role=search) trong Thư viện:<br/>câu hỏi ≤1000 ký tự · số kết quả 5/10/20 · Enter = Tìm"] --> HITS
    FORM --> ERR["Lỗi: QUOTA_EXCEEDED → 'Xem hạn mức'<br/>(nhảy sang tab Cài đặt)"]
    FORM --> EMPTY["Không có kết quả — gợi ý đổi diễn đạt /<br/>bỏ lọc thư mục / đợi ghi chú READY"]
    HITS["Kết quả xếp theo RRF: thứ hạng · tiêu đề · đoạn khớp · điểm<br/>'Mở trang nguồn ↗' → link ngoài (rel=noreferrer)"] -->|Mở ghi chú| OPEN["Mở ngay khung đọc trong Thư viện<br/>(không cần chuyển tab) + highlight"]
```

---

## 5. Tab Tóm tắt — `SelectionSummary.tsx`

Chỉ xuất hiện khi người dùng chọn **“Tóm tắt đoạn văn bản này”** trên trang (side panel mở sẵn).

```mermaid
flowchart TB
    SRC["Thẻ vùng chọn: nguồn (title/URL) + nội dung"] --> TRUNC["Cảnh báo: > 30 000 ký tự<br/>chỉ tóm tắt phần đầu"]
    SRC --> ERR["Lỗi: QUOTA_EXCEEDED → 'Xem hạn mức' (→ Cài đặt)<br/>AI_UNAVAILABLE → Thử lại"]
    SRC --> PREV["Bản xem trước — TỰ tạo khi mở tab, CHƯA lưu<br/>chọn thư mục lưu (Inbox mặc định)<br/>Lưu thành ghi chú · Sao chép (clipboard) · Huỷ"]
    PREV -->|Lưu thành ghi chú| DONE["summary/saveSelection → broadcast notes/changed<br/>→ quay về tab Thư viện"]
```

---

## 6. Tab Cài đặt — `SettingsView.tsx`

```mermaid
flowchart TB
    ACC["Tài khoản: avatar · tên · email · ngày tham gia"]
    QUOTA["Hạn mức AI: thanh tiến trình (đã dùng + đặt trước / giới hạn)<br/>nút Làm mới · hết quota → ghi chú vẫn lưu,<br/>nhưng chưa tìm ngữ nghĩa / tóm tắt được"]
    PREF["Thư mục mặc định cho lưu nhanh (Alt+Shift+N / 'Ghi chú văn bản này')<br/>Inbox hoặc một thư mục<br/>+ Ô tick 'Hiện tab Tìm kiếm' (đã gộp vào Thư viện)"]
    LOGOUT["Đăng xuất — xoá cache ghi chú trên máy"]
    DEL["Xoá tài khoản — 2 bước:<br/>bước 1/2 ConfirmDialog (liệt kê hệ quả) → bước 2/2 gõ 'XOÁ'<br/>xoá vĩnh viễn ghi chú, thư mục, chỉ mục, lịch sử quota"]
    ACC --> QUOTA --> PREF --> LOGOUT --> DEL
```

---

## 7. Các luồng chính

### 7.1 Ghi chú nhanh (kịch bản #1)

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant W as Trang web
    participant B as Background
    participant O as Outbox (IndexedDB)
    participant A as API
    U->>W: Bôi đen → chuột phải → "Ghi chú văn bản này" (hoặc Alt+Shift+N)
    W->>B: chrome.scripting đọc vùng chọn (activeTab)
    B->>O: put (notBefore = now + 5s, id = idempotency key)
    B->>W: Toast: "Đang lưu ghi chú vào …" + đếm ngược 5s
    alt Hoàn tác trong 5s
        U->>W: bấm Hoàn tác / Alt+Shift+Z
        W->>B: RPC quickNote/undo → xoá khỏi outbox
    else Hết 5s
        B->>A: POST /notes (Idempotency-Key)
        A-->>B: 201 — Note (index_status: PROCESSING)
        B-->>W: broadcast outbox/changed · notes/changed
    end
    Note over B,O: Mất mạng / 5xx / 429 → giữ lại, thử lại theo backoff (10s→15′, tối đa 8 lần)<br/>Lỗi vĩnh viễn (401, 413, 422…) → 'failed' → banner "ghi chú chưa gửi" trong Thư viện<br/>Thư mục đã bị xoá ở máy khác → tự lưu vào Inbox
```

### 7.2 Tóm tắt đoạn văn bản (SUM-03)

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant W as Trang web
    participant B as Background
    participant SP as Side Panel (tab Tóm tắt)
    participant A as API
    U->>W: Bôi đen → chuột phải → "Tóm tắt đoạn văn bản này"
    B->>SP: sidePanel.open + lưu pending selection + broadcast selection/pending
    SP->>B: summary/preview (text, ≤ 30 000 ký tự)
    B->>A: POST /summaries/preview
    A-->>SP: bản xem trước (chưa lưu)
    U->>SP: chọn thư mục → "Lưu thành ghi chú"
    SP->>B: summary/saveSelection (text, url, title, summary, folderId?)
    B->>A: POST /notes (kèm summary)
    B-->>SP: broadcast notes/changed → quay về tab Thư viện
```

### 7.3 Tìm kiếm ngữ nghĩa → mở ghi chú

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant L as Thư viện (thanh tìm)
    participant B as Background
    participant A as API
    U->>L: gõ từ khoá (không dấu được) → Enter (tìm sâu bằng AI)
    L->>B: search/query (query, folderId?, topK)
    B->>A: POST /search (hybrid: vector + keyword, xếp theo RRF)
    A-->>L: hits (chunk, điểm RRF, note_title, note_url)
    L-->>L: thay vùng danh sách bằng thẻ kết quả
    U->>L: "Mở ghi chú" trên một kết quả
    L->>L: notes/get → mở ngay khung đọc + highlight
```

---

## 8. Kiểm kê chức năng (RPC — `shared/messaging/protocol.ts`)

| Nhóm | RPC | Dùng ở đâu |
|---|---|---|
| Auth | `auth/status` · `auth/login` · `auth/logout` · `account/delete` | AuthGate · Cài đặt |
| Quota | `quota/get` | Popup · Cài đặt |
| Tuỳ chọn | `prefs/get` · `prefs/set` | Cài đặt (thư mục mặc định, hiện tab Tìm kiếm) · background khi lưu nhanh |
| Thư mục | `folders/list` · `folders/create` · `folders/rename` · `folders/delete` | Thư viện · Cài đặt · Tìm kiếm (tuỳ chọn) · context menu |
| Ghi chú | `notes/list` · `notes/get` · `notes/sync` · `notes/update` · `notes/delete` · `notes/reindex` | Thư viện · Tìm kiếm (tuỳ chọn) |
| Outbox | `outbox/list` · `outbox/retry` · `outbox/discard` · `quickNote/undo` | PendingNotes · Toast |
| Tìm kiếm | `search/query` | Thư viện (Enter = tìm sâu) · Tìm kiếm (tuỳ chọn) |
| Tóm tắt | `summary/preview` · `summary/save` · `summary/saveSelection` · `selection/takePending` | SummaryPanel · Tóm tắt · Side Panel shell |
| E2E only | `e2e/devLogin` | Chỉ bản build E2E (bị loại khỏi bản phát hành) |

Broadcast (`qa-event`): `notes/changed` · `folders/changed` · `outbox/changed` · `selection/pending` · `session/changed`.

---

## 9. Kiểm kê màn hình ↔ file ↔ ảnh chụp

| # | Màn hình | File | Ảnh (`docs/ux/screens/`) |
|---|---|---|---|
| 1 | Popup | `src/ui/popup/Popup.tsx` | `01-popup.png` |
| 2 | Đăng nhập (dùng chung popup + side panel) | `src/ui/features/auth/AuthGate.tsx` | — |
| 3 | Thư viện — trống | `src/ui/features/notes/NotesView.tsx` | `02-thu-vien-trong.png` |
| 4 | Thư viện | `src/ui/features/notes/NotesView.tsx` | `03-thu-vien.png` |
| 5 | Ghi chú chưa gửi (offline/lỗi) | `src/ui/features/notes/PendingNotes.tsx` | `04-ghi-chu-chua-gui.png` |
| 6 | Sửa ghi chú | `src/ui/features/notes/NoteEditor.tsx` | `05-sua-ghi-chu.png` |
| 7 | Xung đột phiên bản 409 | `src/ui/features/notes/NoteEditor.tsx` | `06-xung-dot-409.png` |
| 8 | Quản lý thư mục | `src/ui/features/notes/FolderManager.tsx` | `07-quan-ly-thu-muc.png` |
| 9 | Chọn nhiều & xoá hàng loạt | `src/ui/features/notes/NotesView.tsx` | `08-chon-nhieu.png` |
| 10 | Tóm tắt — xem trước (trong thẻ) | `src/ui/features/summary/SummaryPanel.tsx` | `09-tom-tat-xem-truoc.png` |
| 11 | Tìm sâu bằng AI trong Thư viện | `src/ui/features/notes/NotesView.tsx` | `10-tim-kiem.png` |
| 12 | Tìm sâu — không có kết quả | `src/ui/features/notes/NotesView.tsx` | `11-tim-kiem-khong-co-ket-qua.png` |
| 13 | Tóm tắt vùng chọn | `src/ui/features/summary/SelectionSummary.tsx` | `12-tom-tat-vung-chon.png` |
| 14 | Toast trên trang | `src/content/injected.ts` | `13-toast-tren-trang.png` |
| 15 | Toast — Hoàn tác | `src/content/injected.ts` | `14-toast-hoan-tac.png` |
| 16 | Cài đặt | `src/ui/features/account/SettingsView.tsx` | `15-cai-dat.png` |
| 17 | Xoá tài khoản — bước 2/2 | `src/ui/features/account/SettingsView.tsx` | `16-xoa-tai-khoan-buoc-2.png` |
| 18 | Hết hạn mức AI | `src/ui/features/account/SettingsView.tsx` | `17-het-quota.png` |

---

## 10. Nền tảng dùng chung

- **Design system** (`src/ui/components/`): `Button` · `Field/Input/Select/TextArea` · `Modal/ConfirmDialog` · `Banner/EmptyState/ErrorState/ProgressBar/Spinner/StatusBadge` · `Tabs` · `Toast` (`ToastProvider`, token màu trong `styles.css`, tương phản WCAG AA được test tự động — `tests/contrast.test.ts`).
- **A11y**: `role=status/alert/tabpanel`, `aria-live`, focus-visible, toast là Shadow DOM cô lập CSS.
- **Phím tắt**: `Alt+Shift+N` — ghi chú nhanh; `Alt+Shift+Z` — hoàn tác (trong lúc toast hiện).
- **Chịu lỗi**: mọi màn có trạng thái loading / empty / error kèm "Thử lại"; ghi chú không bao giờ bị âm thầm xoá (outbox + `failed` store); xung đột ghi chú xử lý bằng version, không ghi đè im lặng.
- **Quyền tối thiểu**: không content script chạy sẵn trên mọi trang — chỉ `chrome.scripting` trên tab người dùng vừa thao tác (`activeTab`).
