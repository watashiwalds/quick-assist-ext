# Wireframe tối thiểu — Extension v2 (brief cho người thiết kế)

> Mục đích: danh sách màn hình **chủ đạo** cần wireframe để bắt đầu và chạy Phase 2 ([`todo.md`](todo.md)) mà không phải suy luận thiết kế từ hư vô. Mọi trạng thái hoạt động khác **suy ra** từ các mẫu này + design system (Task 0.5).
> Tham chiếu: [`plan.md`](plan.md) §3.2–3.3 (2 chế độ) · hiện trạng màn v1: [`docs/ux/ui-map.md`](../../ux/ui-map.md) (18 màn, ảnh chụp thật) · nguyên tắc 5 trạng thái: [`docs/ux/README.md`](../../ux/README.md).

## Nguyên tắc dựng bộ tối thiểu

1. **Portrait làm gốc.** Side panel là surface chính — mọi module vẽ portrait trước; landscape chỉ vẽ riêng ở nơi cấu trúc đổi thật sự (split-view, mẫu W03), còn lại suy ra.
2. **Một trạng thái chuẩn mỗi màn.** Wireframe vẽ trạng thái "có dữ liệu". Loading/empty/error/hết-quota dùng chung pattern State + copy ghi chú tại từng màn (đúng nguyên tắc 5 trạng thái của `docs/ux/`).
3. **Không vẽ modal riêng trừ khi bắt buộc.** 409, xoá tài khoản, xoá hàng loạt là hộp thoại — chỉ ghi chú nội dung trong wireframe liên quan.
4. **AutoChunk không nằm trong bộ này.** Slot tab "Tìm trong trang" chỉ chừa chỗ; wireframe PageFinderView thuộc kế hoạch `docs/plan/autochunk/` (T6).

Kích thước vẽ: portrait **360–420px** (responsive tới 480, theo quy ước `docs/ux/`) · landscape **1000×760** (tham chiếu cửa sổ mở rộng) · popup rộng ~360px, cao theo nội dung.

## P1 — cần trước khi bắt đầu Phase 2 (8 màn)

### W01 · Popup (toolbar) — Task 2.1
Glance 5 giây: trạng thái + capture + quota.
- Header: logo QuickAssist + trạng thái đăng nhập (avatar/email hoặc nút Đăng nhập)
- Nút chính "Ghi chú đoạn đã chọn" (disabled khi không có vùng chọn)
- Quota meter mini (đã dùng + đặt trước / giới hạn)
- Link "Mở thư viện" (side panel) + nút "Mở rộng" (cửa sổ landscape)

Suy ra: signed-out (AuthGate bản compact), offline / đang flush (chip trạng thái), lỗi đăng nhập.

### W02 · Khung side panel portrait (shell) — Task 2.2
Khung chung mà mọi module dán vào.
- Header: QuickAssist + email đang đăng nhập + nút "Mở rộng" (icon + tooltip)
- Tab bar: Thư viện · Tìm kiếm · Tóm tắt* · Cài đặt · Chat (*Tóm tắt chỉ hiện khi có vùng chọn chờ) — chừa slot "Tìm trong trang"
- Vùng nội dung (khung trống) + chip trạng thái sync/offline

Suy ra: trạng thái active tab, thứ tự focus, panel bị kéo rộng qua ngưỡng (~560px → chuyển landscape).

### W03 · Khung cửa sổ landscape + Thư viện split-view — Task 2.7
**Mẫu chuẩn split-view — mọi màn landscape suy ra từ đây.**
- Cửa sổ ~1000×760: header (giống panel) + điều hướng (tab ngang hoặc rail dọc — người vẽ đề xuất, chọn 1 dùng lại cho tất cả)
- Cột trái: danh sách ghi chú (NoteCard compact)
- Cột phải: reader/editor ghi chú đang mở (tiêu đề, nội dung, thư mục, Lưu) — **thay modal**
- Deep-link `#/note/:id` mở đúng vào cột phải

Suy ra: landscape của Search (kết quả ↔ xem trước), Summary (nguồn ↔ preview), Chat (hội thoại rộng), Settings (giữ 1 cột).

### W04 · Đăng nhập (AuthGate) — Task 2.1/2.2
- Logo + giới thiệu 1–2 dòng + nút "Đăng nhập bằng Google" + ghi chú privacy (dữ liệu gửi đi đâu)
- Trạng thái lỗi: thông báo + nút "Thử lại"

Suy ra: bản compact trong popup (W01 signed-out).

### W05 · Thư viện — danh sách ghi chú — Task 2.3
Màn dày nhất; mọi pattern danh sách suy ra từ đây.
- Banner "N ghi chú chưa gửi được": Xem/Ẩn · Gửi lại · Bỏ (xác nhận)
- Hàng filter: Select thư mục + nút Thư mục + ô lọc nhanh (không dấu vẫn được) + Chọn/Xong + ⟳ Đồng bộ
- Chế độ chọn: "Chọn tất cả · Xoá (n)" + hộp thoại xác nhận
- NoteCard: StatusBadge (Đang xử lý / Sẵn sàng tìm kiếm / Bỏ qua (hết quota) / Lỗi xử lý AI) · tiêu đề · nội dung clamp · "Tóm tắt đã lưu" · ngày · thư mục · tên miền · actions (Sửa / Tóm tắt / Xoá)

Suy ra: empty · error (kèm "Thử lại") · loading · offline (hiển thị cache + nhãn).

### W06 · Sửa ghi chú (modal, portrait) — Task 2.3
- Input tiêu đề · textarea nội dung (≤20.000 ký tự + đếm trực tiếp) · Select thư mục · Lưu / Huỷ
- Ghi chú hộp thoại 409 "Xung đột phiên bản": "Xem bản mới nhất" / "Ghi đè bằng bản của tôi" (hộp thoại, không full màn)

Suy ra: ở landscape, form này nhúng thẳng vào cột phải của W03 (không dùng modal).

### W07 · Tìm kiếm — Task 2.4
- Form `role=search`: câu hỏi (≤1000 ký tự, không dấu vẫn được) + lọc thư mục + số kết quả 5/10/20 + nút Tìm
- Item kết quả: thứ hạng · tiêu đề · đoạn khớp · điểm · "Mở trang nguồn ↗" · "Mở ghi chú"

Suy ra: empty ("Không có kết quả" + gợi ý đổi diễn đạt / bỏ lọc / đợi ghi chú READY); 402 → "Xem hạn mức"; 429 → "Chờ N giây".

### W08 · Tóm tắt vùng chọn — Task 2.5
Mẫu pattern "preview → xác nhận → lưu" (dùng chung cho mọi AI preview).
- Thẻ nguồn: title/URL + nội dung vùng chọn
- Cảnh báo >30.000 ký tự (chỉ tóm tắt phần đầu)
- Bản xem trước (tự tạo khi mở tab, CHƯA lưu) + trạng thái đang tạo
- Chọn thư mục (Inbox mặc định) + "Lưu thành ghi chú" / "Sao chép" / "Huỷ"

Suy ra: SummaryPanel "Tóm tắt bằng AI / Tóm tắt lại" trên NoteCard (cùng pattern, nguồn khác); lỗi 402/502/413.

## P2 — cần trong Phase 2, có thể trễ hơn (4 màn)

### W09 · Cài đặt — Task 2.6
- Tài khoản: avatar · tên · email · ngày tham gia
- Hạn mức AI: thanh tiến trình (đã dùng + đặt trước / giới hạn) + nút Làm mới + cảnh báo gần hết
- Thư mục mặc định cho lưu nhanh (Select) · Đăng xuất
- Xoá tài khoản 2 bước (hộp thoại): bước 1 liệt kê hệ quả → bước 2 gõ "XOÁ"

Suy ra: màn "hết hạn mức" mà các module khác link tới (402).

### W10 · Quản lý thư mục (modal) — Task 2.3
- Danh sách thư mục (badge "mặc định" — không sửa/xoá được) · tạo (≤100 ký tự) · đổi tên · xoá (confirm → ghi chú về Inbox)

### W11 · Chat stub — Task 2.6
- Khung hội thoại (vị trí tin nhắn, ô nhập + nút gửi) — **vẽ cho landscape**, vì đây là driver màn rộng
- Trạng thái 501: "Tính năng chưa hỗ trợ" + giải thích ngắn (khi nào có, dữ liệu xử lý thế nào)

Ghi chú: nếu cần cắt phạm vi, hạ cấp thành EmptyState — không chặn Phase 2.

### W12 · Toast trên trang (content script) — nền tảng Task 1.5 / visual Phase 2
- Toast Shadow DOM nổi trên trang bất kỳ: "Đang lưu ghi chú vào …" + đếm ngược 5s + nút "Hoàn tác"
- `role=status`, `aria-live=polite`; tương phản đảm bảo trên nền sáng/tối bất kỳ của trang web
- Giữ nguyên hành vi v1 (5s, undo) — chỉ đổi ngôn ngữ thị giác.

## Bảng suy luận trạng thái (không cần wireframe)

| Trạng thái / màn hình | Suy ra từ |
|---|---|
| Loading · empty · error (kèm `request_id`) của mọi module | Pattern State (Task 0.5) + W05 là mẫu danh sách |
| Hết hạn mức 402 → "Xem hạn mức" | W09 + EmptyState |
| Xung đột phiên bản 409 | W06 (hộp thoại) |
| Xoá hàng loạt + xác nhận | W05 (chế độ chọn) |
| Xoá tài khoản bước 2/2 | W09 (hộp thoại 2 bước) |
| Signed-out / offline / đang flush | W01 + W02 (chip trạng thái) + W04 |
| Lỗi đăng nhập / huỷ Google | W04 |
| Landscape Search / Summary / Chat / Settings | W03 (mẫu split) + W07 / W08 / W11 / W09 |
| Panel kéo rộng qua ngưỡng (~560px) | W03 (cùng layout split, mật độ cozy) |
| Toast "Đã hoàn tác" | W12 |
| Tab "Tìm trong trang" (AutoChunk PageFinder) | Kế hoạch `docs/plan/autochunk/` (T6) — ngoài bộ này |

## Ghi chú cho người thiết kế

- Nếu chỉ làm được một phần: **W01–W08 trước** — đủ để bắt đầu Phase 2; W09–W12 kịp trước checkpoint Phase 2.
- Token dark placeholder — không cần màu hoàn thiện; quan trọng là cấu trúc, mật độ (compact vs cozy) và hierarchy.
- Tại W03, đề xuất và chọn 1 phương án điều hướng landscape (tab ngang vs rail dọc) — tái dùng cho mọi màn landscape.
- Đánh số Wxx dùng tham chiếu trong review PR + tên file wireframe/Figma; sau khi code xong, chụp lại màn thật bằng `ux-screens.spec.ts` như v1.
