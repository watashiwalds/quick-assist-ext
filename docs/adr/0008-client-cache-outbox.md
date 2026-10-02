# ADR-0008: Cache-first khi đọc, outbox khi ghi, server là nguồn sự thật

**Bối cảnh.** Kịch bản #3 yêu cầu cache-first bằng IndexedDB; kịch bản #1 yêu cầu hoàn tác 5s và không mất ghi chú khi mất mạng. Đồng bộ hai chiều đầy đủ (offline edit + merge) quá tốn cho 8 tuần.

**Quyết định.**
- **Đọc:** trả cache ngay, đồng bộ tăng dần `GET /notes?updated_since=` (kèm tombstone `deleted_at`) rồi phát `notes/changed`.
- **Tạo note:** outbox IndexedDB (`notBefore` = +5s cho hoàn tác), Idempotency-Key = id mục outbox, retry backoff qua `chrome.alarms`.
- **Sửa/xoá:** chỉ khi online; `PATCH` kèm `version`, lệch → 409 `NOTE_VERSION_CONFLICT` → UI cho chọn tải bản mới.

**Phương án đã loại.** Offline-first đầy đủ (CRDT/merge — vượt phạm vi); không cache (chậm, mất kịch bản #3).

**Hệ quả.** (+) Không mất ghi chú; logic xung đột đơn giản, đúng. (−) Không sửa được khi offline; cache có thể cũ vài giây (eventual).
