# ADR-0018: Nguồn chi tiết cho ghi chú — định danh theo raw URL (bỏ query/hash), domain vẫn là đơn vị truy xuất

- **Trạng thái:** Chấp nhận (20/11/2026) · Kế hoạch: `docs/self_sustained/source-attribution-plan.md` · Liên quan: ADR-0015 (nguồn dán), ADR-0013 (AutoChunk), ADR-0006 (hybrid search), ADR-0008 (cache/outbox)

## Bối cảnh

Ghi chú hiện gắn nguồn ở hai mức: `url` đầy đủ + `domain` suy ra. Nhưng trải nghiệm chỉ phản ánh mức **domain**:
Thư viện gom nhóm theo `document_id ?? domain`, Tìm kiếm/Hỏi AI nhận nhóm nguồn theo domain từ backend. Hệ quả:
hai bài báo khác nhau cùng `vnexpress.net` rơi vào một nhóm "vnexpress.net" — người dùng không mở lại được đúng
bài gốc mà phải dò từng ghi chú.

Thêm nữa, ghi chú tạo từ **nội dung dán** (ADR-0015) luôn có `url = null` — dù phần lớn thời điểm dán, người dùng
đang đọc bài ở tab bên cạnh. Ghi chú đó rơi vào "Không rõ nguồn".

Ràng buộc: không thêm permission (`tabs`), không migration, không đổi prompt/RAG/`source_index`, giữ đa dạng
nguồn (domain-level) khi xếp hạng tìm kiếm.

## Quyết định

1. **Định danh nguồn chi tiết = raw URL bỏ `?query` và `#hash`** (`origin + pathname`, giữ scheme/host/path
   nguyên trạng — không strip `www.`, không AMP/mobile, không sort query, không danh sách tracking param).
   Utility dùng chung `apps/extension/src/shared/source.ts` (`sourceKey/sourceDomain/sourceLabel/groupByPage`),
   hàm thuần, chỉ ở client. Hệ quả chấp nhận: `?id=123` gộp nhầm theo path; `www./không-www` và trailing slash
   tách nhóm — xử lý sau nếu dữ liệu thực tế đòi hỏi.
2. **Thư viện** gom theo trang (mặc định) với toggle **"Trang / Trang web"** nhớ trong `Preferences.groupNotesBy`;
   tài liệu nhiều part vẫn một nhóm; "Không rõ nguồn" luôn cuối; header nhóm trang có link "Mở trang nguồn".
3. **Tìm kiếm & Hỏi AI** giữ nhóm domain của backend, thêm **nhóm con theo trang** ở client trong từng domain
   (Tìm kiếm: trong danh sách; Hỏi AI: trong "Chi tiết nguồn"; chip vẫn gọn theo domain). Chỉ hiện header trang
   khi domain có > 1 trang trong dữ liệu đã tải.
4. **Backend giữ nguyên domain-level grouping**: `source_index`, prompt `<source>`, diversity cap, API contract,
   chat history cũ — không đổi. Trang là tầng **hiển thị** ở client; note-level `url` (`Note`, `SearchNoteOut`,
   `ChatSource.url`) đã đủ dữ liệu.
5. **Nguồn khi dán (bổ sung ADR-0015)**: vào chế độ dán → extension tự lấy tab đang mở làm **nguồn tham chiếu**
   (URL + tiêu đề) qua RPC `pageMatch/source` (chỉ đọc metadata tab bằng quyền hiện có); chip cho **Lấy lại tab /
   Bỏ / Nhập URL tay**; quét gửi `url`/`title` qua `pageMatch/run` (backend `PageMatchIn` đã có, chỉ metadata);
   lưu ghi chú với URL đó. Nhãn "nguồn tham chiếu" — không khẳng định văn bản được copy từ tab đó.
6. **Không thêm quyền, không đọc clipboard, không migration**: note cũ không URL tự fallback theo domain
   (hoặc "Không rõ nguồn"); permission giữ `activeTab` + optional host.

## Phương án đã loại

- **Backend gom nhóm theo trang** (đổi `source_index`/`source_url`, cap trang/domain, sửa prompt và chat history):
  chính xác hơn nhưng đụng API contract, prompt RAG, ranking và dữ liệu cũ — rủi ro cao hơn giá trị MVP; để phase sau.
- **Canonicalize đầy đủ** (strip `www.`, tracking param, AMP, trailing slash, sort query): chuẩn hoá tốt hơn nhưng
  thêm bảng quy tắc phải bảo trì và dễ "gộp oan" hai trang thật sự khác nhau; MVP chọn raw URL, thêm rule sau khi
  có dữ liệu thực tế.
- **Thêm quyền `tabs`** để luôn đọc được URL mọi tab: trái nguyên tắc quyền tối thiểu; `activeTab` + optional host
  đủ cho luồng chính, thiếu thì nhập tay.
- **Tự đọc clipboard (`clipboardRead`)**: không cần — Ctrl+V là thao tác chủ động (ADR-0015).
- **Thêm cột `source_title`**: nhãn nhóm dùng host + path là đủ đọc; tiêu đề bài để phase sau nếu cần migration.

## Hệ quả

- (+) Mở lại đúng bài gốc từ Thư viện/Tìm kiếm/Hỏi AI; ghi chú dán thoát "Không rõ nguồn" trong đa số ca sử dụng.
- (+) Không đổi backend/prompt/API/permission/migration — rủi ro triển khai thấp, rollback dễ (thuần client).
- (+) Một utility duy nhất cho 3 màn hình → quy tắc URL nhất quán, test được độc lập.
- (−) URL dạng `?id=123`/`?p=` gộp nhầm nhiều bài vào một nhóm (đã chấp nhận, ghi trong rủi ro của kế hoạch).
- (−) `www.` khác không-`www.`, trailing slash khác nhau → tách nhóm; chấp nhận theo raw URL.
- (−) Nguồn tham chiếu có thể sai (tab không phải nơi copy); giảm thiểu bằng nhãn "tham chiếu" + sửa/bỏ/nhập tay.
- (−) Tìm kiếm/Hỏi AI chỉ nhóm trang trên dữ liệu đã tải (tối đa 10 note/domain) — count domain vẫn đúng backend.
