# ADR-0017: AutoChunk — SSE cho tiến độ quét trang

- **Trạng thái:** Chấp nhận (18/11/2026) · Liên quan: ADR-0013 (trích nội dung + LLM thẩm định), ADR-0015 (nguồn dán), ADR-0009 (SSE cho chat), ADR-0010 (rate limit/quota)
- **Kế hoạch:** `docs/self_sustained/ux_improvement_plan.md` Phase 3

## Bối cảnh

`POST /ai/page-match` (ADR-0013) trả JSON một lần sau khi embed **mọi** khối và gọi LLM thẩm định.
Trang dài (tới 50 000 ký tự, ~32 khối/lô) mất nhiều giây; UI chỉ có spinner không xác định, người dùng
không biết còn bao lâu, không huỷ được, và dễ tưởng tính năng treo. Quét toàn bộ trang (`scan_all`) còn
lâu hơn. Cần tiến độ từng bước + huỷ giữa chừng mà không đổi kết quả cuối.

## Quyết định

1. **Thêm `POST /ai/page-match/stream` (SSE), giữ `/ai/page-match` JSON để tương thích ngược.**
   Hai endpoint dùng chung `PageMatchService.stream()` / `match()` và cùng schema kết quả.
2. **Ba loại event:**
   - `progress { phase: "extract" | "batch" | "verify", index?, total? }` — `batch` có `index/total`
     để UI vẽ thanh xác định; `extract`/`verify` là thanh không xác định.
   - `done` — toàn bộ `PageMatchOut` như endpoint JSON.
   - `error { code, message, status }` — lỗi phát sinh **sau khi mở stream** (quota, AI, không trích
     được nội dung). Lỗi đồng bộ trước stream (query sai, HTML quá lớn, nội dung dán rỗng) vẫn trả
     JSON + mã HTTP chuẩn (413/422/…) để UI xử lý như cũ.
3. **Một lease quota cho embed, một lease cho verify** như bản JSON. Client đóng kết nối (bấm Huỷ)
   → controller gọi `aclose()` generator nghiệp vụ → `async with` giải phóng lease ngay, không đợi
   `release_stale`. `AbortController` phía extension giữ theo `requestId`.
4. **Batch 32 khối/lần, timeout 30 s/lô** (`PAGE_MATCH_EMBED_BATCH_BLOCKS`,
   `PAGE_MATCH_EMBED_TIMEOUT_SECONDS`); lỗi/timeout một lô → event `error` mã `AI_UNAVAILABLE`.
   Verify lỗi/timeout → vẫn `done` với `warning=VERIFY_UNAVAILABLE`, `verified=false`, giữ fallback
   cosine như ADR-0013.
5. **Proxy phải phục vụ SSE:** Caddy route `/api/v1/ai/page-match` **và** `/api/v1/ai/page-match/stream`
   với `request_body 3MB`, `reverse_proxy` đặt `flush_interval -1`; response có
   `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
6. **Extension:** background đọc SSE bằng parser dùng chung (`shared/api/sse.ts`), phát broadcast
   `pageMatch/progress`; side panel hiện `role="progressbar"` với `aria-valuenow` khi biết tổng, thanh
   không xác định khi `extract/verify`, nút Huỷ gọi `pageMatch/cancel`.

## Phương án đã loại

- **Giữ JSON một lần + spinner không xác định:** đơn giản nhất nhưng không giải quyết cảm giác treo,
  không huỷ được; trang dài vẫn chiếm quota đã reserve dù người dùng đã bỏ đi.
- **Polling job (`POST` tạo job + `GET /jobs/{id}`):** cần lưu trạng thái job ở server/DB, thêm
  endpoint, TTL, dọn job; SSE tái dùng đúng pattern chat (ADR-0009) và không cần bảng mới.
- **WebSocket:** hai chiều không cần thiết; SSE nhẹ hơn, đi qua HTTP/proxy hiện có.
- **Chunked JSON / NDJSON:** tự định nghĩa framing, không có event name; SSE có sẵn parser/chuẩn
  `event:`/`data:` và đã dùng cho chat.
- **Chỉ trả tiến độ ước lượng theo số khối ở client:** client không biết tiến độ embed/verify thật,
  sai khi mạng/AI chậm.

## Hệ quả

- (+) Người dùng thấy tiến độ thật (extract → lô i/n → verify), huỷ được; quota được giải phóng ngay
  khi đóng stream.
- (+) Không đổi kết quả/contract cuối; client cũ vẫn dùng endpoint JSON.
- (+) Tái dùng parser SSE + pattern broadcast của chat, ít code mới.
- (−) Tăng độ phức tạp: hai endpoint, event lỗi sau header, phải test stream/abort/fallback.
- (−) Lỗi sau khi mở stream không thể đổi mã HTTP; UI phải đọc `error.code/status` thay vì chỉ
  `response.ok`.
- (−) Proxy/encoding phải cấu hình đúng, nếu không event bị gom và tiến độ nhảy một cục. Caddy đã
  sửa route + `flush_interval -1`; các triển khai khác cần kiểm tra tương tự.
