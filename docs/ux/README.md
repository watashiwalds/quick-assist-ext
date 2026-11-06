# P04 — User flow & màn hình (6 luồng SDS)

> Owner: Trần Thùy Dương · Phối hợp: Lê Đăng Sơn · Cập nhật 09/10/2026
> Ảnh dưới đây là **màn hình thật** của extension (không phải phác thảo), chụp tự động bằng
> `UX_SCREENS=1 npx playwright test e2e/ux-screens.spec.ts` (apps/extension) — chạy lại khi đổi giao diện.
> Kích thước side panel thiết kế: rộng 360–420 px.

## Nguyên tắc chung
- Mỗi màn có đủ 5 trạng thái: **đang tải · trống · có dữ liệu · lỗi (kèm mã lỗi `request_id`) · hết quota**.
- Thao tác nguy hiểm luôn xác nhận; xoá tài khoản xác nhận **2 bước** + gõ "XOÁ".
- Không chặn người dùng chờ AI: ghi chú lưu ngay, nhãn trạng thái `Đang xử lý → Sẵn sàng tìm kiếm / Bỏ qua (hết quota) / Lỗi xử lý AI`.
- Bàn phím: Tab/Shift+Tab, mũi tên giữa các tab, Esc đóng hộp thoại (focus trở về nút đã mở). Màu đạt WCAG AA (test tự động).

## Luồng 1 — Đăng nhập (SDS §5.1.1)
```mermaid
flowchart LR
  A[Mở popup / side panel] -->|chưa có phiên| B[Màn đăng nhập]
  B -->|Đăng nhập bằng Google| C{launchWebAuthFlow + PKCE}
  C -->|huỷ| B
  C -->|lỗi Google / mạng| E[Thông báo lỗi + Thử lại]
  C -->|thành công| D[Thư viện]
  D -->|phiên hết hạn, refresh lỗi| B
```
![Popup chưa đăng nhập](screens/01-popup.png)

## Luồng 2 — Ghi chú nhanh + hoàn tác (SDS §5.1.2, kịch bản #1)
```mermaid
flowchart LR
  S[Bôi đen văn bản] --> M{Chuột phải / Alt+Shift+N}
  M -->|"Ghi chú văn bản này"| O[Lưu vào outbox + toast 5s]
  M -->|"Ghi chú vào thư mục ▸ X"| O
  O -->|Hoàn tác / Alt+Shift+Z| U[“Đã hoàn tác” — không gửi]
  O -->|hết 5s| P[Gửi POST /notes + Idempotency-Key]
  P -->|201| R[Thư viện: Đang xử lý → Sẵn sàng tìm kiếm]
  P -->|mất mạng / 5xx| Q[Giữ trong outbox, tự gửi lại]
  P -->|lỗi không tự khắc phục| F[“N ghi chú chưa gửi được” → Gửi lại / Bỏ]
  S -->|không bôi đen / trang chrome://| X[Toast lỗi / bỏ qua an toàn]
```
| Toast trên trang (CSS trang cố tình phá — vẫn hiển thị đúng) | Sau khi hoàn tác |
|---|---|
| ![](screens/13-toast-tren-trang.png) | ![](screens/14-toast-hoan-tac.png) |

## Luồng 3 — Thư viện & thư mục (kịch bản #3, #5)
```mermaid
flowchart TD
  L[Thư viện: đọc cache ngay] --> S[Đồng bộ nền updated_since]
  L --> F[Lọc thư mục / từ khoá]
  L --> E[Sửa] -->|409| C[Chọn: xem bản mới / ghi đè]
  L --> D[Xoá 1 hoặc Chọn → Xoá nhiều] --> K[Xác nhận]
  L --> T[Thư mục: tạo / đổi tên / xoá → note về Inbox]
```
| Trống | Có dữ liệu + ghi chú chưa gửi | Danh sách chưa gửi |
|---|---|---|
| ![](screens/02-thu-vien-trong.png) | ![](screens/03-thu-vien.png) | ![](screens/04-ghi-chu-chua-gui.png) |

| Sửa | Xung đột 409 | Thư mục | Chọn nhiều |
|---|---|---|---|
| ![](screens/05-sua-ghi-chu.png) | ![](screens/06-xung-dot-409.png) | ![](screens/07-quan-ly-thu-muc.png) | ![](screens/08-chon-nhieu.png) |

## Luồng 4 — Tìm kiếm ngữ nghĩa (SDS §5.1.3, kịch bản #4)
```mermaid
flowchart LR
  Q[Nhập câu hỏi, có thể không dấu] --> F[Lọc thư mục tuỳ chọn] --> R{POST /search}
  R -->|có kết quả| H[Top 5 đoạn + tiêu đề + nguồn → Mở ghi chú / Mở trang nguồn]
  R -->|rỗng| E[“Không có kết quả phù hợp” + gợi ý]
  R -->|402| Z[Hết hạn mức → nút Xem hạn mức]
  R -->|429| W[Chờ N giây]
```
| Kết quả (gõ không dấu) | Không có kết quả | Hết quota |
|---|---|---|
| ![](screens/10-tim-kiem.png) | ![](screens/11-tim-kiem-khong-co-ket-qua.png) | ![](screens/17-het-quota.png) |

## Luồng 5 — Tóm tắt (SDS §5.1.4, đặc tả SUM-01)
```mermaid
flowchart LR
  A[Nút “Tóm tắt bằng AI” trên ghi chú] --> P[Xem trước — chưa lưu]
  B[Chuột phải “Tóm tắt đoạn văn bản này”] --> SP[Side panel mở tab Tóm tắt] --> P
  P -->|Lưu| S[Ghi vào ghi chú / tạo ghi chú mới kèm tóm tắt]
  P -->|Huỷ| X[Không lưu gì]
  P -->|402 / 502 / 413| E[Thông báo + hướng xử lý]
```
| Trên thẻ ghi chú | Vùng chọn |
|---|---|
| ![](screens/09-tom-tat-xem-truoc.png) | ![](screens/12-tom-tat-vung-chon.png) |

*(Ảnh chụp với AI mock nên nội dung tóm tắt là chuỗi lặp lại đầu vào.)*

## Luồng 6 — Cài đặt & xoá tài khoản (SDS §5.1.5)
```mermaid
flowchart LR
  S[Cài đặt] --> Q[Xem hạn mức] & D[Thư mục mặc định khi lưu nhanh] & O[Đăng xuất → xoá cache máy]
  S --> X[Xoá tài khoản…] --> X1[Bước 1: liệt kê hậu quả] --> X2[Bước 2: gõ XOÁ] --> R[DELETE /me → xoá cache, token → màn đăng nhập]
```
| Cài đặt (gần hết quota) | Xoá tài khoản bước 2 |
|---|---|
| ![](screens/15-cai-dat.png) | ![](screens/16-xoa-tai-khoan-buoc-2.png) |

## Ma trận trạng thái đã bao phủ
| Màn | Loading | Empty | Error | Undo | Hết quota | Offline |
|---|---|---|---|---|---|---|
| Lưu nhanh (toast) | — | toast "hãy bôi đen" | toast lỗi / failed store | ✅ | SKIPPED, vẫn lưu | outbox |
| Thư viện | ✅ | ✅ | ✅ (Thử lại) | — | nhãn "Bỏ qua (hết quota)" + Thử lại AI | ✅ cache |
| Tìm kiếm | ✅ | ✅ | ✅ | — | ✅ + link Cài đặt | thông báo mạng |
| Tóm tắt | ✅ | ✅ | ✅ | Huỷ | ✅ + link Cài đặt | thông báo mạng |
| Cài đặt | ✅ | — | ✅ | 2 bước | thanh hạn mức + cảnh báo | hồ sơ từ cache |
