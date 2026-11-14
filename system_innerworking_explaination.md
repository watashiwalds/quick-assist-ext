# QuickAssist — Báo cáo kỹ thuật: Cơ chế hoạt động của các chức năng chính

> Báo cáo mô tả **cách hoạt động bên trong** của các chức năng người dùng chính của hệ thống
> QuickAssist (Chrome extension MV3 + backend FastAPI), kèm **thông số cụ thể** và **giá trị thiết
> lập** ảnh hưởng tới kết quả cuối của từng chức năng.
>
> - Nền tham chiếu: commit `b510adefd97b` (nhánh làm việc hiện tại).
> - Nguồn: mã nguồn `apps/api` (backend) và `apps/extension` (extension); đường dẫn file được ghi
>   rõ tại từng mục để đối chiếu.

---

## Mục lục

1. [Bức tranh chung](#1-bức-tranh-chung)
2. [Đăng nhập và phiên làm việc](#2-đăng-nhập-và-phiên-làm-việc)
3. [Ghi chú nhanh (bôi đen → lưu)](#3-ghi-chú-nhanh-bôi-đen--lưu)
4. [Tóm tắt bằng AI](#4-tóm-tắt-bằng-ai)
5. [Chỉ mục tìm kiếm: chunk → embed (Worker)](#5-chỉ-mục-tìm-kiếm-chunk--embed-worker)
6. [Tìm kiếm ngữ nghĩa](#6-tìm-kiếm-ngữ-nghĩa)
7. [Hỏi đáp trên ghi chú (Chat RAG)](#7-hỏi-đáp-trên-ghi-chú-chat-rag)
8. [AutoChunk — "Tìm trong trang"](#8-autochunk--tìm-trong-trang)
9. [Hạn mức AI (Quota) — cơ chế dùng chung](#9-hạn-mức-ai-quota--cơ-chế-dùng-chung)
10. [Giới hạn tần suất theo người dùng (Rate limit)](#10-giới-hạn-tần-suất-theo-người-dùng-rate-limit)
11. [Đồng bộ và bộ nhớ đệm phía extension](#11-đồng-bộ-và-bộ-nhớ-đệm-phía-extension)
- [Phụ lục A — Bảng tổng hợp thông số theo chức năng](#phụ-lục-a--bảng-tổng-hợp-thông-số-theo-chức-năng)
- [Phụ lục B — Biến môi trường backend](#phụ-lục-b--biến-môi-trường-backend)
- [Phụ lục C — Cấu hình build-time của extension](#phụ-lục-c--cấu-hình-build-time-của-extension)

---

## 1. Bức tranh chung

Hệ thống gồm 3 khối, giao tiếp một chiều như sau:

```
Extension UI (React, popup/side panel)
   │  RPC qua chrome.runtime (shared/messaging/protocol.ts) — UI KHÔNG tự gọi mạng
   ▼
Background service worker (MV3)  ──►  chrome.scripting ──► hàm tiêm vào tab (content/injected.ts)
   │  HTTPS (shared/api/http.ts), token do background giữ
   ▼
Backend API  FastAPI  (uvicorn, prefix /api/v1)          ← tiến trình 1
   presentation → business → data_access → data (+ infrastructure)
   ▼
PostgreSQL 16 + pgvector   (vừa là DB, vừa là hàng đợi job — ADR-0003)
   ▲
Worker  (python -m quickassist.worker)                   ← tiến trình 2: embed, dọn quota
```

- **Extension**: `ui/` chỉ hiển thị và gọi background qua RPC; `background/` là **cửa ngõ mạng duy
  nhất** (gọi API, giữ token, outbox, đồng bộ, chat SSE); `content/` là các hàm tự chứa được tiêm
  qua `chrome.scripting` khi người dùng thao tác (không có content script thường trực).
- **Backend**: modular monolith theo Layered Architecture (SDS Hình 1); cấu hình tập trung tại
  `apps/api/src/quickassist/infrastructure/config.py` — **không module nào đọc biến môi trường trực
  tiếp**. Tất cả thông số backend trong báo cáo này đều là field của `Settings` và đặt được bằng
  biến môi trường (tên in hoa của field, vd `search_top_k` → `SEARCH_TOP_K`).
- **Cấu hình build-time của extension**: `apps/extension/src/shared/config.ts` (nhúng vào bundle,
  không chứa secret).

| Chức năng người dùng | Endpoint backend | Code chính |
|---|---|---|
| Đăng nhập Google | `POST /auth/google/exchange`, `/auth/refresh`, `/auth/logout` | `business/auth/auth_service.py`, `background/auth/google.ts`, `session.ts` |
| Ghi chú nhanh | `POST /notes` (+ Idempotency-Key) | `background/notes/quick-note.ts`, `business/notes/notes_service.py` |
| Tóm tắt AI | `POST /ai/summaries`, `PUT /notes/{id}/summary` | `business/summary/summary_service.py`, `ui/features/summary/*` |
| Tìm kiếm ngữ nghĩa | `POST /search` | `business/semantic_search/semantic_search_service.py` |
| Chat trên ghi chú | `POST /ai/chat` (SSE) | `business/rag/rag_service.py`, `background/chat.ts` |
| Tìm trong trang (AutoChunk) | `POST /ai/page-match` | `business/page_match/page_match_service.py`, `background/page-match.ts` |
| Hạn mức | `GET /me/quota` | `business/quota/quota_service.py` |

---

## 2. Đăng nhập và phiên làm việc

**Luồng** (`background/auth/google.ts` → `business/auth/auth_service.py`):

1. Extension mở Google OAuth bằng **Authorization Code + PKCE** qua
   `chrome.identity.launchWebAuthFlow`; redirect URI là `https://<extension-id>.chromiumapp.org/`.
   Extension chỉ giữ `client_id`; `client_secret` nằm ở server.
2. Server nhận `code` + `code_verifier` + `nonce` → đổi code lấy `id_token`, xác minh chữ ký
   JWKS và `nonce` → upsert user → phát **app session**.
3. App session gồm 2 token:
   - **Access token**: JWT HS256, claim `sub`/`sid`/`iss`/`iat`/`exp`/`typ=access`
     (`infrastructure/security.py`).
   - **Refresh token**: chuỗi ngẫu nhiên `secrets.token_urlsafe(48)`; DB **chỉ lưu SHA-256**.
4. Extension lưu: access token vào `chrome.storage.session` (mất khi đóng trình duyệt), refresh
   token vào `chrome.storage.local` (giữ đăng nhập qua lần mở sau) — `background/auth/session.ts`.
5. Khi gọi API, `getAccessToken()` **chỉ dùng token còn hiệu lực hơn 30 giây**
   (`expiresAt - 30_000 > now`); hết → gọi refresh (single-flight, nhiều request gặp 401 cùng lúc
   chỉ refresh **một lần**). Nếu API vẫn trả `401 TOKEN_EXPIRED`, HTTP client refresh và
   **thử lại đúng 1 lần** (`shared/api/http.ts`, cờ `retried`).
6. **Refresh xoay vòng**: token cũ bị đánh dấu `revoked_at` + `replaced_by`. Nếu token đã xoay mà
   vẫn được gửi lên (dấu hiệu bị đánh cắp) → **revoke toàn bộ session** của user và trả
   `REFRESH_REUSED`.

**Thông số ảnh hưởng kết quả:**

| Thông số | Giá trị mặc định | Ảnh hưởng |
|---|---|---|
| `ACCESS_TOKEN_TTL_SECONDS` | `900` (15 phút) | Thời gian sống access token; càng ngắn càng an toàn, càng nhiều lần refresh |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Sau 30 ngày không hoạt động phải đăng nhập lại |
| Ngưỡng refresh sớm (client) | `30_000` ms | Token còn hiệu lực < 30s sẽ được thay trước khi dùng |
| `ENABLE_DEV_LOGIN` | `false` | Bật đăng nhập thử không cần Google; chỉ có tác dụng khi `APP_ENV ∈ {dev, test}` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | rỗng | Thiếu → không đăng nhập được bằng Google |
| `OAUTH_ALLOWED_REDIRECT_URIS`, `CORS_ORIGINS` | rỗng | Phải chứa redirect URI `https://<ID>.chromiumapp.org/` và origin extension |
| `VITE_EXTENSION_KEY` (build) | rỗng | Khoá công khai cố định Extension ID giữa các máy → redirect URI/CORS khai báo một lần |

Logout: gọi `POST /auth/logout` với refresh token (revoke trên server) rồi xoá cả hai token ở máy.

---

## 3. Ghi chú nhanh (bôi đen → lưu)

**Luồng** (`background/notes/quick-note.ts`, `background/index.ts`):

1. Kích hoạt: phím **Alt+Shift+N** (command `quick-note`) hoặc menu chuột phải
   *"Ghi chú văn bản này"* / *"Ghi chú vào thư mục ▸ \<tên\>"* (tối đa **15** thư mục trong menu —
   `MAX_FOLDERS_IN_MENU`, lấy từ cache nên dựng được cả khi offline).
2. Đọc vùng chọn bằng hàm tiêm `readSelection` (`chrome.scripting.executeScript`, cần quyền
   `activeTab` từ thao tác người dùng). Trang `chrome://`, Web Store… không tiêm được.
3. Kiểm tra: văn bản rỗng → toast lỗi; chưa đăng nhập → toast yêu cầu đăng nhập (ghi chú **không**
   được tạo).
4. Chuẩn hoá: trim; **cắt còn 20 000 ký tự đầu** (`maxNoteChars`, khớp `MAX_NOTE_CHARS` backend —
   vượt sẽ bị backend từ chối `413 NOTE_TOO_LONG`); tiêu đề cắt 500 ký tự; URL chỉ nhận `http(s)`.
5. Chọn thư mục đích: tham số từ menu → nếu không có, lấy `defaultFolderId` trong Cài đặt
   (`background/prefs.ts`, mặc định `null`); thư mục không còn trong cache → bỏ `folder_id` →
   server tự đưa vào **Inbox** (`get_or_create_inbox`).
6. Ghi vào **OUTBOX** (IndexedDB) **ngay**, kèm `notBefore = now + 5 000 ms`; hiện toast đếm
   ngược 5 giây (snippet 140 ký tự, cảnh báo nếu đã cắt). **Hoàn tác (Alt+Shift+Z hoặc nút trên
   toast) = xoá mục khỏi outbox** — chỉ được khi chưa gửi.
7. Sau 5,2 s (hoặc alarm mỗi 1 phút, hoặc lúc khởi động trình duyệt) → `flushOutbox()`:
   `POST /notes` với **Idempotency-Key = id mục outbox** → server chống trùng khi retry
   (`IdempotencyGuard`); tạo note với `index_status = PROCESSING` và phát job đánh chỉ mục.
8. Lỗi khi gửi được phân loại (`classify()`):
   - `retryable` (mạng, 5xx, 429…) và `attempts + 1 < 8` → giữ lại, thử sau với backoff
     `min(2^attempts × 10s, 15 phút)` → 10s, 20s, 40s…
   - `401` / `TOKEN_MISSING` → chuyển sang store **"failed"** (đăng nhập lại rồi "Gửi lại").
   - `FOLDER_NOT_FOUND` → bỏ `folder_id`, gửi lại ngay (ghi chú về Inbox, **không mất**).
   - Hết lượt thử / lỗi không tự khắc phục (413, 422…) → store "failed" để người dùng Gửi lại / Bỏ.
     **Không bao giờ âm thầm xoá ghi chú.**

**Thông số ảnh hưởng kết quả:**

| Thông số | Nơi đặt | Giá trị | Ảnh hưởng |
|---|---|---|---|
| `undoWindowMs` | `shared/config.ts` | `5 000` ms | Thời gian được hoàn tác; cũng là độ trễ gửi tối thiểu |
| `maxNoteChars` = `MAX_NOTE_CHARS` | client + backend | `20 000` ký tự | Vượt → cắt ở máy (+ thông báo) hoặc `413 NOTE_TOO_LONG` ở server |
| Độ dài tiêu đề | `quick-note.ts` | `500` ký tự | Tiêu đề gửi lên bị cắt |
| `MAX_ATTEMPTS` | `quick-note.ts` | `8` | Số lần gửi lại tối đa trước khi sang "failed" |
| `backoffMs` | `quick-note.ts` | `min(2^n × 10s, 15')` | Nhịp thử lại: 10s → 20s → 40s… tối đa 15 phút |
| Alarm flush | `background/index.ts` | `1` phút | Nhịp retry nền khi service worker sống lại |
| `defaultFolderId` | Cài đặt (prefs) | `null` → Inbox | Nơi ghi chú nhanh rơi vào khi không chọn thư mục |
| `MAX_FOLDERS_IN_MENU` | `menus.ts` | `15` | Số thư mục hiển thị trong menu chuột phải |
| `RATE_LIMIT_WRITE_PER_MINUTE` | backend | `120` | Vượt → `429` kèm thời gian chờ |
| Snippet toast / danh sách chờ | `quick-note.ts` | `140` / `160` ký tự | Chỉ hiển thị, không ảnh hưởng dữ liệu |

---

## 4. Tóm tắt bằng AI

**Luồng** (`ui/features/summary/SelectionSummary.tsx` → `business/summary/summary_service.py`):

1. Kích hoạt: bôi đen → chuột phải *"Tóm tắt đoạn văn bản này"* → side panel mở **đồng bộ trong
   user gesture**, vùng chọn lưu vào `chrome.storage.session` (cắt còn **30 000 ký tự**, hạn dùng
   **10 phút** — quá là bỏ, `selection.ts`). Từ trang ghi chú cũng tóm tắt được theo `note_id`.
2. UI tự gọi `summary/preview` → background `POST /ai/summaries` kèm Idempotency-Key.
3. Server kiểm tra: **đúng một** trong hai `text` / `note_id` (sai → `422 SUMMARY_INPUT_INVALID`);
   quá **30 000 ký tự** → `413 SUMMARY_INPUT_TOO_LONG`.
4. Dựng prompt (`summary/prompts.py`): system yêu cầu tóm tắt **tiếng Việt, tối đa 5 gạch đầu
   dòng**, giữ nguyên thuật ngữ/số/tên riêng; nội dung được bọc trong `<document>…</document>`, mọi
   thẻ `<document>` giả bên trong bị vô hiệu hoá (`neutralize`) — **chống prompt injection**; nếu
   phát hiện chỉ dẫn nhắm vào AI trong văn bản, bỏ qua và thêm dòng cảnh báo "⚠ Trang có chứa chỉ
   dẫn lạ dành cho AI (đã bỏ qua)".
5. **Reserve quota** với ước lượng `estimate_tokens(messages) + 600`, rồi gọi
   `ai.complete(max_tokens = 600)`. AI lỗi → `502 AI_UNAVAILABLE` (quota tự hoàn).
6. Trả về **bản xem trước (preview)** — cắt còn 10 000 ký tự, **KHÔNG ghi DB**. Gửi lại cùng
   Idempotency-Key → `409 IDEMPOTENCY_KEY_REUSED` (không gọi AI lần hai "miễn phí").
7. Người dùng xác nhận:
   - *"Lưu thành ghi chú"* → tạo note mới (nội dung + `summary_text`).
   - Hoặc lưu vào note có sẵn: `PUT /notes/{id}/summary` kèm `version` — version lệch →
     `409 NOTE_VERSION_CONFLICT` (đã bị sửa nơi khác). Bản tóm tắt lưu bị giới hạn
     `SUMMARY_MAX_CHARS = 10 000` ký tự.

**Thông số ảnh hưởng kết quả:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `SUMMARY_MAX_OUTPUT_TOKENS` (hằng số) | `600` | Độ dài tối đa bản tóm tắt; cũng dùng để reserve quota |
| `MAX_SUMMARY_INPUT_CHARS` | `30 000` | Đầu vào dài hơn → bị từ chối (client cắt trước ở vùng chọn) |
| `SUMMARY_MAX_CHARS` (hằng số) | `10 000` | Giới hạn `summary_text` khi lưu vào note |
| `AI_PROVIDER` | `mock` \| `openai` \| `gemini` | Chọn engine: mock (không tốn tiền, trả kết quả giả), OpenAI (`CHAT_MODEL`, mặc định `gpt-4o-mini`) hay Gemini (`GEMINI_CHAT_MODEL`, mặc định `gemma-4-31b-it`, `GEMINI_THINKING_LEVEL=minimal`) |
| `AI_TIMEOUT_SECONDS` | `90` s | Timeout mỗi request AI; Gemini có thể chậm hơn 30s — đặt thấp sẽ biến yêu cầu hợp lệ thành `AI_UNAVAILABLE` |
| `AI_MAX_RETRIES` | `2` | Số lần retry 408/409/429/5xx, backoff `0,5×2^n + jitter ≤ 0,3s` |
| `RATE_LIMIT_AI_PER_MINUTE` | `10` | Chung bucket "ai" với chat; vượt → `429` |
| `summaryRequestTimeoutMs` (client) | `120 000` ms | Timeout riêng cho tóm tắt — nới hơn timeout mặc định 15s |
| `estimate_tokens` | `max(1, len//2 + 1)` | Ước lượng ~2 ký tự/token (đo thực tế tiếng Việt: 2,14–3,44 ký tự/token) — luôn ước lượng **dư**, phần thừa hoàn lại khi commit |
| Prompt system | 5 gạch đầu dòng, tiếng Việt | Quyết định hình thái kết quả; cấm thêm thông tin ngoài văn bản |

---

## 5. Chỉ mục tìm kiếm: chunk → embed (Worker)

Ghi chú **không** được đánh chỉ mục ngay trong request tạo/sửa — chỉ phát job vào hàng đợi
PostgreSQL (`SKIP LOCKED`, outbox pattern: job enqueue **cùng transaction** với thay đổi note; có
`dedupe_key` để không dồn job khi sửa liên tục). Worker (`business/semantic_search/indexing_job.py`):

1. Note đã xoá / không tồn tại → xoá toàn bộ chunk cũ.
2. `content_hash` (SHA-256) không đổi → chỉ cập nhật `folder_id`, đặt `READY` — **không tốn quota**.
3. Chia chunk theo `CHUNKING_STRATEGY`:
   - **v2 (mặc định)** — chia theo **câu tiếng Việt** (`chunking.py`): tách đoạn/gạch đầu dòng;
     tách câu tại `. ! ? …` nhưng **không tách sau viết tắt** (TP., TS., PGS., v.v., Q.1…) hay số
     thập phân (1.5, 3.000); gom câu vào chunk ≤ `CHUNK_SIZE_CHARS`; **overlap theo câu**
     (mang các câu cuối ≤ `CHUNK_OVERLAP_CHARS` sang chunk sau); cắt ở ranh giới đoạn khi chunk đã
     ≥ 60% kích thước; câu dài hơn `size` cắt theo **từ** (không cắt giữa từ, trừ "từ" khổng lồ
     như URL). Bất biến có test: mọi chunk ≤ size, không mất từ, đúng thứ tự.
   - **v1** — cắt cứng theo ký tự + overlap, giữ lại để benchmark (`CHUNKING_STRATEGY=v1`).
   - Overlap bị chặn `≤ size // 2`.
4. **Reserve quota "embed_note"** theo ước lượng các chunk;
   `request_id = embed_note:{note_id}:{index_rev}:{attempt}` — mỗi lần thử một request_id nên lần
   thử sau vẫn bị tính đúng, không "miễn phí".
5. Gọi `ai.embed(pieces)` — client OpenAI **chia batch** theo ngân sách
   `AI_EMBED_BATCH_TOKENS = 16 000` token/request và cap **2048 mục**/request (`_EMBED_MAX_INPUTS`);
   gửi sai số lượng/số chiều → lỗi không retry. Model/m số chiều phải khớp cột pgvector.
6. Ghi chunk mới thay chunk cũ **trong cùng transaction** (không có khoảng trống index), commit,
   sau đó mới chốt quota theo usage thật.

**Bảng quyết định trạng thái index** (hiển thị trong UI ghi chú):

| Tình huống | Trạng thái | Quota |
|---|---|---|
| OK | `READY` | Trừ số token thật |
| Hết quota | `SKIPPED` (error `QUOTA_EXCEEDED`) | Không trừ ("silent skip") |
| AI lỗi tạm thời, còn lượt | giữ `PROCESSING`, job retry backoff `min(2^attempt × 5s, 600s)` | Giữ chỗ được hoàn, lần sau reserve lại |
| AI lỗi vĩnh viễn / hết lượt | `FAILED` (`AI_PROVIDER_ERROR`) → UI "Thử lại" → `POST /notes/{id}/reindex` (`index_rev + 1`) | Không trừ |

**Thông số:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `CHUNK_SIZE_CHARS` | `1200` | Kích thước chunk — càng nhỏ càng chi tiết, càng lớn càng đủ ngữ cảnh |
| `CHUNK_OVERLAP_CHARS` | `150` | Phần lặp giữa 2 chunk liên tiếp — giữ ngữ cảnh khi cắt; bị chặn ≤ size/2 |
| `CHUNKING_STRATEGY` | `v2` | Chọn thuật toán chia (`v1`/`v2`) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model embedding (OpenAI) |
| `EMBEDDING_DIM` | `1536` | Số chiều vector — **phải khớp cột vector trong migration**, lệch là lỗi |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Khi `AI_PROVIDER=gemini` |
| `AI_EMBED_BATCH_TOKENS` | `16 000` | Ngân sách token mỗi request embedding — quá lớn dễ 400 (không retryable) làm chết cả lần quét |
| `JOB_MAX_ATTEMPTS` | `5` | Số lượt thử tối đa của job index trước khi `DEAD` |
| `WORKER_POLL_INTERVAL_SECONDS` | `1.0` | Độ trễ bắt đầu index sau khi tạo/sửa note |

---

## 6. Tìm kiếm ngữ nghĩa

**Luồng** (`ui/features/search/SearchView.tsx` → `semantic_search_service.py` →
`data_access/repositories/note_chunk_repository.py`):

1. UI: câu hỏi (maxLength **1000 ký tự**), lọc thư mục, chọn số kết quả **5/10/20**.
2. `POST /search` → server **embed truy vấn** (reserver quota "search" theo ước lượng query) →
   **hybrid retrieval** trong không gian dữ liệu của **chính user đó**:

```sql
-- Hai nhánh song song, mỗi nhánh lấy SEARCH_CANDIDATE_K = 30 ứng viên:
vec:  ORDER BY embedding <=> :qvec            -- cosine distance, chỉ mục HNSW (pgvector)
kw:   tsv @@ to_tsquery('simple', ...OR...)   -- từ khoá: KHÔNG DẤU (qa_unaccent), OR giữa các từ,
      ORDER BY ts_rank_cd(tsv, q) DESC        -- chunk khớp nhiều từ hơn lên trước
-- Hợp nhất bằng Reciprocal Rank Fusion:
score = Σ 1 / (60 + rank)                     -- RRF, k = 60 — không cần chuẩn hoá thang điểm
```

   - Điều kiện `user_id` nằm **trong từng nhánh** → không thể rò dữ liệu chéo user; `folder_id`
     lọc nếu có.
   - Nhánh từ khoá dùng OR → câu hỏi tự nhiên ("mua quà gì ở đà lạt") không cần chứa đủ mọi từ.
3. Rerank có cờ `SEARCH_RERANK_ENABLED` — mặc định **false** (chưa bật; TODO R02: bật thì rerank,
   timeout thì fallback thứ tự RRF).
4. Lấy `k × 2` dòng, ghép tiêu đề/URL/thư mục qua hợp đồng Notes, **loại note đã xoá**, cắt còn `k`.
5. Điểm trả về là **điểm RRF** (không phải cosine 0–1) — hiển thị ở UI với 3 số lẻ.

**Thông số ảnh hưởng kết quả:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `SEARCH_TOP_K` | `5` | Số kết quả mặc định (UI cho phép 5/10/20 — ghi đè bằng tham số `top_k`) |
| `SEARCH_CANDIDATE_K` | `30` | Số ứng viên mỗi nhánh (vector + từ khoá) trước khi hợp nhất — càng lớn càng bao quát, càng chậm |
| Hằng số RRF `k` | `60` | Trọng số hợp nhất rank của hai nhánh |
| `SEARCH_RERANK_ENABLED` | `false` | Bật/tắt bước rerank sau hợp nhất (hiện chưa triển khai) |
| Thông số chunk/embedding | xem §5 | Chất lượng index quyết định trực tiếp chất lượng tìm kiếm |
| `RATE_LIMIT_SEARCH_PER_MINUTE` | `30` | Vượt → `429` |
| `topK` UI | `5/10/20` | Người dùng chọn số kết quả tối đa |

---

## 7. Hỏi đáp trên ghi chú (Chat RAG)

**Luồng** (`ui/features/chat/*` → `background/chat.ts` → `business/rag/rag_service.py`):

1. UI (`useChat`): mỗi câu hỏi gửi kèm **lịch sử 5 cặp hỏi–đáp hoàn chỉnh gần nhất**
   (`buildHistory`, bỏ lượt trả lời lỗi/rỗng). Server **không lưu nội dung chat** (ADR-0012);
   các phiên hội thoại lưu trên trình duyệt (IndexedDB).
2. UI mở Port `qa-chat` tới background → background `POST /ai/chat` dạng **SSE**, không áp timeout
   tổng; huỷ bằng `AbortSignal` (nút Dừng hoặc đóng panel).
3. Server `prepare()`:
   - Câu hỏi trim; rỗng → `422 CHAT_INPUT_INVALID`; dài hơn **2 000 ký tự** →
     `413 CHAT_INPUT_TOO_LONG`.
   - Gọi `SemanticSearchService.retrieve(top_k = 5, quota_operation = "rag_retrieve")` lấy ngữ cảnh.
   - **Không tìm thấy ghi chú nào** → trả câu cố định `NO_CONTEXT_ANSWER` ("Mình không tìm thấy ghi
     chú nào liên quan…") với `tokens_used = 0`, **không gọi LLM, không trừ quota**.
   - Lịch sử được `clean_history()`: chỉ nhận vai `user`/`assistant`, mỗi thông điệp cắt còn
     **2 000 ký tự**, giữ tối đa **5 cặp**, lượt đầu phải là `user`.
   - Prompt (`rag/prompts.py`): system yêu cầu **chỉ trả lời dựa trên `<notes>`**, trích dẫn nguồn
     `[n]` khớp `note id`, không dùng kiến thức ngoài, không biết thì nói không biết; mỗi đoạn bọc
     `<note id="n" title="…">`, thẻ giả bị neutralize; **câu hỏi đặt trước khối ghi chú** để model
     đọc yêu cầu trước khi gặp dữ liệu không tin cậy.
   - **Reserve quota "chat"** = ước lượng prompt + `CHAT_MAX_OUTPUT_TOKENS`.
4. `stream()` phát sự kiện SSE theo thứ tự: `sources` (danh sách nguồn: index `[n]`, `note_id`,
   `chunk_id`, tiêu đề, URL, **snippet 240 ký tự**) → các `delta` (từng phần câu trả lời) → `done`
   `{tokens_used}` hoặc `error` (`AI_UNAVAILABLE`).
5. **Chốt quota theo phần ĐÃ sinh** (ADR-0009): kết thúc bình thường → trừ usage thật từ provider;
   bị ngắt giữa chừng (bấm Dừng / đóng panel → abort) → nếu provider chưa kịp báo usage thì ước
   lượng = prompt + phần đã sinh; **chưa sinh chữ nào → release (không trừ)**. Việc chốt chạy cả
   khi generator bị huỷ (`CancelScope(shield=True)`).

**Thông số ảnh hưởng kết quả:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `CHAT_CONTEXT_TOP_K` (hằng số) | `5` | Số đoạn ghi chú đưa vào ngữ cảnh — không đổi bằng env |
| `CHAT_MAX_OUTPUT_TOKENS` (hằng số) | `800` | Độ dài tối đa câu trả lời |
| `MAX_QUESTION_CHARS` (hằng số) | `2 000` | Câu hỏi dài hơn → `413 CHAT_INPUT_TOO_LONG` |
| `MAX_HISTORY_PAIRS` (hằng số, cả 2 phía) | `5` | Số lượt hội thoại trước được gửi kèm — ảnh hưởng mạch lạc đa lượt và chi phí token |
| `MAX_HISTORY_MESSAGE_CHARS` (hằng số) | `2 000` | Mỗi thông điệp lịch sử bị cắt |
| `SNIPPET_CHARS` (hằng số) | `240` | Độ dài snippet trong danh sách nguồn |
| `folder_id` (tham số) | `null` | Chat có lọc theo thư mục hay không — ảnh hưởng tập ngữ cảnh retrieve |
| `RATE_LIMIT_AI_PER_MINUTE` | `10` | Chung bucket "ai" với tóm tắt |
| Model / timeout / retry | xem §4 | Kết quả và độ trễ câu trả lời |

---

## 8. AutoChunk — "Tìm trong trang"

Cho phép mô tả điều cần tìm, hệ thống quét **trang đang xem** (hoặc nội dung dán vào), chỉ ra các
đoạn khớp, người dùng chọn rồi lưu thành **một ghi chú gộp** (ADR-0013/0015). Stateless — không ghi
DB, chỉ trả preview.

**Luồng** (`ui/features/page-finder/PageFinderView.tsx` → `background/page-match.ts` →
`page_match_service.py`):

1. **Lấy nguồn**: tab đang xem → hàm tiêm `getRawHtml(pageMatchMaxHtmlBytes)` chụp HTML; trang quá
   lớn (`tooLong`) hoặc `chrome://`/PDF → báo lỗi ngay **không tải lên**. Quyền đọc trang là
   `optional_host_permissions` — xin lúc người dùng bấm "Quét trang", thu hồi được bất cứ lúc nào.
   Nguồn dán thì bỏ qua tab/quyền.
2. `POST /ai/page-match` (`RATE_LIMIT_PAGE_MATCH_PER_MINUTE = 6`): truy vấn 1–**500** ký tự (quá →
   `422 PAGE_MATCH_QUERY_INVALID`).
3. Server **trích khối văn bản**: HTML → **Trafilatura** trong process pool
   (`PAGE_MATCH_EXTRACT_TIMEOUT_SECONDS = 10`, quá giờ → `422 PAGE_NO_CONTENT`); sau đó:
   khối dài hơn `PAGE_MATCH_MAX_BLOCK_CHARS (1 200)` → tách theo câu; tổng khối cắt ở
   `PAGE_MATCH_MAX_CHARS (50 000)` (đánh dấu `truncated`); với nguồn **dán**, khối ngắn hơn
   `PAGE_MATCH_MIN_BLOCK_CHARS (400)` được gộp với khối liền kề.
4. **Lease 1 — embed**: `[query, *blocks]` trong **một batch** (một lease quota).
5. **Sàng theo cosine**: khối có điểm ≥ `PAGE_MATCH_MIN_SCORE (0.35)` vào vòng thẩm định; lấy tối
   đa `PAGE_MATCH_TOP_CANDIDATES (15)` khối điểm cao nhất, trả kết quả theo thứ tự trang.
6. **Lease 2 — LLM thẩm định**: LLM trả JSON xác nhận từng khối có thực sự khớp ý định hay không
   (`max_tokens = PAGE_MATCH_VERIFY_MAX_OUTPUT_TOKENS = 500`, timeout
   `PAGE_MATCH_VERIFY_TIMEOUT_SECONDS = 20`). **Degrade có kiểm soát**: LLM lỗi/quá giờ/JSON hỏng/
   hết quota → trả ứng viên theo điểm với `verified = false` +
   `warning = "VERIFY_UNAVAILABLE"` — tính năng không chết khi AI thẩm định lỗi.
7. **`match_ratio`** = ∑ ký tự đoạn khớp / ∑ ký tự trang (phần ứng viên vượt số được thẩm định được
   ước lượng theo tỉ lệ xác nhận trong nhóm đã thẩm định). `ratio ≥ PAGE_MATCH_FULL_PAGE_RATIO
   (0.6)` → mode **`full_page`**: trả thêm `full_text` (nội dung cả trang) cho nút "Lưu cả trang";
   ngược lại mode **`segments`**.
8. **Lưu**: các đoạn đã chọn gộp theo thứ tự trang thành note; nội dung lớn hơn 20 000 ký tự được
   chia thành **nhiều note** theo biên đoạn (`buildNoteParts`); từ **8 000 ký tự** trở lên UI hỏi
   lại trước khi lưu (`CONFIRM_CHARS`) vì tạo chỉ mục tốn hạn mức AI. Không tự lưu khi người dùng
   chưa bấm. Nguồn dán → note không kèm URL, nút "Xem trên trang" bị khoá.

**Thông số ảnh hưởng kết quả:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `PAGE_MATCH_MAX_HTML_BYTES` | `2 000 000` | HTML vượt → `413 PAGE_TOO_LONG`; client chặn trước khi tải lên |
| `PAGE_MATCH_MAX_CHARS` | `50 000` | Tổng ký tự khối tối đa — bound chi phí embed; dư bị cắt (`truncated`) |
| `PAGE_MATCH_MAX_BLOCK_CHARS` | `1 200` | Khối dài hơn bị tách — ảnh hưởng độ "ngắn gọn" của mỗi kết quả |
| `PAGE_MATCH_MIN_BLOCK_CHARS` | `400` (0 = tắt) | Gộp khối quá ngắn (chỉ nguồn dán) — giảm nhiễu kết quả |
| `PAGE_MATCH_MIN_SCORE` | `0.35` | Ngưỡng cosine vào vòng thẩm định — thấp hơn → nhiều ứng viên, dễ nhiễu |
| `PAGE_MATCH_TOP_CANDIDATES` | `15` | Số khối tối đa đưa LLM thẩm định — chi phí vs. độ phủ |
| `PAGE_MATCH_FULL_PAGE_RATIO` | `0.6` | Ngưỡng chuyển mode `full_page` |
| `PAGE_MATCH_VERIFY_*` | `500` token / `20` s | Ngân sách và thời gian bước thẩm định; quá → `VERIFY_UNAVAILABLE` |
| `PAGE_MATCH_EXTRACT_TIMEOUT_SECONDS` | `10` s | Quá giờ trích HTML → `422 PAGE_NO_CONTENT` |
| `MAX_QUERY_CHARS` (hằng số) | `500` | Truy vấn dài hơn → `422` |
| `pageMatchRequestTimeoutMs` (client) | `45 000` ms | Timeout tổng phía máy người dùng (10s + 20s server + mạng) |
| `RATE_LIMIT_PAGE_MATCH_PER_MINUTE` | `6` | Vượt → `429` |
| `CONFIRM_CHARS` (UI) | `8 000` | Hỏi lại trước khi lưu note lớn |

---

## 9. Hạn mức AI (Quota) — cơ chế dùng chung

Mọi lệnh gọi AI (tóm tắt, tìm kiếm, chat, embed, thẩm định trang) đi qua
`QuotaService` (`business/quota/quota_service.py`) với mô hình **RESERVE → COMMIT/RELEASE**:

1. `reserve(user_id, operation, estimate, request_id)`:
   - `request_id` trùng → trả lại lease cũ (an toàn khi retry), `already_settled` nếu đã chốt.
   - `request_id` thuộc **user khác** → `409 IDEMPOTENCY_KEY_REUSED` (không "mượn" hạn mức).
   - Không còn hạn mức → `QUOTA_EXCEEDED` (UI hiển thị "Bạn đã dùng hết hạn mức AI" + liên kết xem
     hạn mức).
   - Bảng `quota_ledger` ghi từng lần giữ chỗ — quota **bền vững** kể cả khi nghiệp vụ phía sau
     rollback (service chạy trên session DB riêng).
2. Thành công → `commit(lease, actual_tokens)`: trừ số **thật** từ usage provider; phần giữ chỗ
   dư được hoàn lại.
3. Bất kỳ lỗi/huỷ nào trước commit → `release(lease)` (hoàn giữ chỗ) — context manager `leased()`
   tự làm, kể cả khi request bị huỷ giữa chừng (`CancelScope(shield=True)`).
4. **Giữ chỗ treo** (tiến trình chết giữa reserve và commit): worker dọn định kỳ mỗi **300 s**, hoàn
   các giữ chỗ cũ hơn **15 phút** (`release_stale`).

**Thông số:**

| Thông số | Giá trị | Ảnh hưởng |
|---|---|---|
| `QUOTA_DEFAULT_TOKENS` | `200 000` | Hạn mức token ban đầu mỗi user (cộng dồn trọn vòng đời, không reset theo tháng) |
| `estimate_tokens` | `max(1, len//2 + 1)` | Ước lượng giữ chỗ trước gọi AI (luôn dư, hoàn phần thừa khi commit) |
| Chu kỳ dọn giữ chỗ treo | `300` s / ngưỡng `15` phút | Thời gian tối đa một giữ chỗ "ma" chiếm hạn mức |
| `reset_demo` | chỉ dev/test | Hoàn mọi giữ chỗ, đưa used về 0, cấp lại mức mặc định — phục vụ demo |

---

## 10. Giới hạn tần suất theo người dùng (Rate limit)

`infrastructure/rate_limit.py` — **cửa sổ trượt trong bộ nhớ tiến trình** (đủ cho demo 1 instance;
chạy nhiều instance thì mỗi instance đếm riêng, giới hạn thực tế = N × limit). Áp dụng ở tầng
presentation theo **bucket + user** (khoá `"{bucket}:{user_id}"`), cửa sổ **60 giây**, đặt `0` để
tắt; vượt → lỗi `429` kèm `retry_after` (giây).

| Bucket (biến thiết lập) | Giá trị mặc định | Áp dụng cho |
|---|---|---|
| `RATE_LIMIT_SEARCH_PER_MINUTE` | `30` | `POST /search` |
| `RATE_LIMIT_AI_PER_MINUTE` | `10` | `POST /ai/summary`, `POST /ai/chat` |
| `RATE_LIMIT_WRITE_PER_MINUTE` | `120` | tạo/sửa/xoá ghi chú, thư mục |
| `RATE_LIMIT_PAGE_MATCH_PER_MINUTE` | `6` | `POST /ai/page-match` |

---

## 11. Đồng bộ và bộ nhớ đệm phía extension

**Server là nguồn sự thật**; IndexedDB là cache đọc trước ("cache-first").

- **Sync tăng dần** (`background/notes/sync.ts`): `GET /notes?updated_since=<lastSyncAt>&limit=200`
  theo cursor (`base64(updated_at|id)`); phản hồi **bao gồm tombstone** (note đã xoá kèm
  `deleted_at`) để client xoá bản local. `lastSyncAt` lấy theo `updated_at` **lớn nhất** (so sánh
  theo thời gian, không theo chuỗi). Nhiều màn hình cùng yêu cầu sync chỉ chạy **một lượt**
  (single-flight).
- **Ghi có version**: mọi PATCH gửi kèm `version`; server tăng `version` sau mỗi lần sửa, lệch
  version → `409 NOTE_VERSION_CONFLICT` kèm `current_version` → UI hỏi người dùng.
- **Outbox** (mục 3) là hàng đợi ghi offline; cache thư mục cho menu context nằm ở meta store.
- Tuỳ chọn người dùng (`defaultFolderId`, `showSearchTab`) lưu `chrome.storage.local`
  (`background/prefs.ts`), **xoá khi đăng xuất/xoá tài khoản**.
- Chính sách lưu trữ phía server: `RETENTION_INACTIVE_DAYS = 365` — tài khoản không hoạt động 1
  năm nằm trong diện dọn dẹp (`last_active_at` cập nhật mỗi lần refresh).

---

## Phụ lục A — Bảng tổng hợp thông số theo chức năng

| Chức năng | Giới hạn đầu vào | Kết quả đầu ra | Giới hạn vận hành |
|---|---|---|---|
| Ghi chú nhanh | 20 000 ký tự; title 500 | Note trong Inbox/thư mục chọn | Undo 5s; retry ≤ 8 lần, backoff ≤ 15'; write 120/phút |
| Tóm tắt | ≤ 30 000 ký tự; 1 trong text/note_id | Preview ≤ 10 000 ký tự, ≤ 600 token out | ai 10/phút; timeout AI 90s; Idempotency-Key bắt buộc để chống gọi trùng |
| Chỉ mục (worker) | chunk ≤ 1 200 ký tự, overlap ≤ 150 | Embedding 1536 chiều/chunk | Batch ≤ 16k token & 2048 mục; job ≤ 5 lượt, backoff ≤ 10' |
| Tìm kiếm | query UI ≤ 1 000 ký tự | top-k (5/10/20), điểm RRF | Candidate 30/nhánh; search 30/phút |
| Chat | câu hỏi ≤ 2 000; history 5 cặp × 2 000 ký tự | ≤ 800 token out; nguồn `[n]`, snippet 240 | Không có nguồn → không gọi LLM; chốt quota theo phần đã sinh |
| Page match | query ≤ 500; HTML ≤ 2 MB; nội dung ≤ 50k ký tự | ≤ 15 đoạn; mode segments/full_page; verified | cosine ≥ 0.35; LLM thẩm định 500 token/20s; 6/phút |
| Quota | — | limit 200 000 token/user | Giữ chỗ treo hoàn sau 15 phút |
| Auth | — | access 15', refresh 30 ngày | Reuse refresh token → revoke toàn bộ session |

## Phụ lục B — Biến môi trường backend

Toàn bộ khai báo trong `apps/api/src/quickassist/infrastructure/config.py`; mẫu ở
`infra/.env.example`. Chỉ liệt kê các biến **ảnh hưởng kết quả chức năng người dùng**:

| Biến | Mặc định | Vai trò |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` (miễn phí, kết quả giả) / `openai` / `gemini` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | rỗng / `https://api.openai.com/v1` | Trỏ sang endpoint tương thích OpenAI (vLLM, llama.cpp…) mà không đổi code |
| `CHAT_MODEL` | `gpt-4o-mini` | Model chat cho tóm tắt + chat |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | `text-embedding-3-small`, `1536` | Model/số chiều embedding (phải khớp DB) |
| `GEMINI_API_KEY`, `GEMINI_CHAT_MODEL`, `GEMINI_EMBEDDING_MODEL`, `GEMINI_THINKING_LEVEL` | rỗng / `gemma-4-31b-it` / `gemini-embedding-001` / `minimal` | Khi `AI_PROVIDER=gemini`; `""` = không gửi thinkingConfig |
| `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, `AI_EMBED_BATCH_TOKENS` | `90`, `2`, `16 000` | Hành vi gọi provider (xem §4, §5) |
| `CHUNK_SIZE_CHARS`, `CHUNK_OVERLAP_CHARS`, `CHUNKING_STRATEGY` | `1200`, `150`, `v2` | Thuật toán chia chunk (xem §5) |
| `SEARCH_TOP_K`, `SEARCH_CANDIDATE_K`, `SEARCH_RERANK_ENABLED` | `5`, `30`, `false` | Hành vi tìm kiếm (xem §6) |
| `QUOTA_DEFAULT_TOKENS` | `200 000` | Hạn mức user (xem §9) |
| `MAX_NOTE_CHARS`, `MAX_SUMMARY_INPUT_CHARS` | `20 000`, `30 000` | Giới hạn nội dung (xem §3, §4) |
| `PAGE_MATCH_*` | xem §8 | Toàn bộ tham số AutoChunk |
| `RATE_LIMIT_*_PER_MINUTE` | `30/10/120/6` | Rate limit (xem §10); `0` = tắt |
| `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_DAYS` | `900`, `30` | Phiên đăng nhập (xem §2) |
| `JWT_SECRET`, `JWT_ISSUER` | `change-me-in-env`, `quickassist` | Ký/xác minh JWT — **bắt buộc đổi secret ở prod** |
| `ENABLE_DEV_LOGIN`, `APP_ENV` | `false`, `dev` | Dev login chỉ chạy khi `APP_ENV ∈ {dev, test}` |
| `RETENTION_INACTIVE_DAYS` | `365` | Chính sách lưu trữ dữ liệu |
| `DB_POOL_SIZE`, `DATABASE_URL` | `5`, postgres local | Kết nối DB |
| `CORS_ORIGINS`, `OAUTH_ALLOWED_REDIRECT_URIS` | rỗng | Origin extension / redirect URI được phép |

## Phụ lục C — Cấu hình build-time của extension

`apps/extension/src/shared/config.ts` + `manifest.config.ts` — nhúng lúc build, **mọi thứ trong
bundle đều công khai** (không đặt secret):

| Biến / hằng | Giá trị | Ảnh hưởng |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Đích gọi API; cũng quyết định `host_permissions` trong manifest |
| `VITE_GOOGLE_CLIENT_ID` | rỗng | Thiếu → đăng nhập Google báo `OAUTH_NOT_CONFIGURED` |
| `VITE_EXTENSION_KEY` | rỗng | Cố định Extension ID (R-03) — redirect URI OAuth & CORS khai báo một lần |
| `VITE_E2E` | `false` | `true` mới bật đăng nhập thử + hook kiểm thử; bản phát hành loại bỏ khối này khỏi bundle |
| `undoWindowMs` | `5 000` | Cửa sổ hoàn tác ghi chú nhanh |
| `requestTimeoutMs` | `15 000` | Timeout mặc định mọi request |
| `summaryRequestTimeoutMs` | `120 000` | Timeout riêng cho tóm tắt (AI chậm) |
| `pageMatchRequestTimeoutMs` | `45 000` | Timeout riêng cho quét trang |
| `maxNoteChars` / `maxSummaryChars` / `pageMatchMaxHtmlBytes` | `20 000` / `30 000` / `2 000 000` | **Phản chiếu** các giới hạn backend để chặn ở máy, không tải lên rồi mới bị từ chối |
| Permissions trong manifest | `contextMenus, storage, identity, scripting, activeTab, alarms, sidePanel` | Không có content script thường trực, không `<all_urls>`; quyền đọc trang là **optional**, xin khi dùng |
| Phím tắt `quick-note` | `Alt+Shift+N` | Chrome cấm tổ hợp `Ctrl+Alt+…` (trùng AltGr) — sai sẽ khiến extension không nạp được |

---

*Hết báo cáo. Mọi con số trong tài liệu được lấy trực tiếp từ mã nguồn tại commit tham chiếu;
khi đổi cấu hình, cập nhật cả `infra/.env.example`, `apps/extension/.env.example` và báo cáo này.*
