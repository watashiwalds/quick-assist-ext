# Sơ đồ tuần tự — SDS §5.1.1 đến §5.1.9

> Vẽ theo code hiện tại (`apps/api`, `apps/extension`). Ký pháp dựa trên SDS của nhóm 08 (PlantUML, UML 2.5), viết lại bằng Mermaid.
> **Bản giống hệt phong cách nhóm 08 (PlantUML):** [sequence/](sequence/) — mỗi mục một file `5_1_x.puml`, mỗi file tự chứa đủ style và màu (mở được trong VS Code PlantUML lẫn draw.io). Xuất PNG để chèn vào SDS.
> Cần Mermaid **≥ 11.12** để hiển thị lifeline `Database` dạng hình trụ (mermaid.live dùng được; một số trình xem cũ sẽ báo lỗi ở dòng `Database@{ "type" : "database" }`).

## Quy ước ký pháp

| Thành phần | Quy ước |
|---|---|
| Lifeline | `User` là actor (hình người); `Database` là hình trụ, đặt ngoài cùng bên phải; hệ thống bên ngoài có hậu tố `(external service)`. Tên thành phần theo tên trong code (CamelCase). |
| Lời gọi đồng bộ | Nét liền `->>`. Nhãn là tên hàm/endpoint/thông điệp thật kèm tham số: `retrieve(user_id, query)`, `POST /search`, `search/query`. |
| Phản hồi | Nét đứt `-->>`. Nhãn bắt đầu bằng "trả về …", kèm HTTP status và mã lỗi nếu có: `trả về 402 QUOTA_EXCEEDED`. |
| Xử lý nội bộ | Tự gọi (self-message): `SVC->>SVC: compute_match_ratio()`, `UI->>UI: render …`. |
| Thanh kích hoạt | Bật khi nhận lời gọi (`->>+`), tắt khi trả về (`-->>-`). |
| Khung kết hợp | `alt`/`else` cho rẽ nhánh có điều kiện; `opt` cho luồng tuỳ chọn một nhánh; `loop` cho lặp (worker retry, stream). Điều kiện ghi trong `[...]`. |
| Chia phần | Sơ đồ nhiều giai đoạn dùng `Note over` trải ngang toàn bộ lifeline, thay cho `== … ==` của PlantUML. |
| Mô tả kèm sơ đồ | Mỗi sơ đồ có 4 mục: **Công nghệ**, **Kích hoạt**, **Chức năng**, **Luồng hoạt động** (mỗi gạch đầu dòng ứng với một mũi tên, nhánh ghi "Nhánh điều kiện [...]"). |

---

## 5.1.1 Đăng nhập bằng Google OAuth

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as PopupUI
    participant BG as BackgroundWorker
    participant G as GoogleOAuth (external service)
    participant API as AuthController
    participant SVC as AuthService
    participant Database@{ "type" : "database" }

    User->>+UI: bấm "Đăng nhập bằng Google"
    UI->>+BG: auth/login
    BG->>BG: buildGoogleAuthRequest() sinh code_verifier, code_challenge (S256), state, nonce
    BG->>+G: launchWebAuthFlow(authUrl)
    G->>User: hiển thị màn hình chọn tài khoản và đồng ý
    User->>G: đồng ý cấp quyền
    G-->>-BG: trả về redirect URL kèm code, state
    BG->>BG: parseAuthRedirect(url, state)
    alt người dùng huỷ hoặc state không khớp
        BG-->>UI: trả về lỗi OAUTH_CANCELLED
        UI->>UI: render thông báo đăng nhập thất bại
    else state hợp lệ
        BG->>+API: POST /auth/google/exchange(code, code_verifier, redirect_uri, nonce)
        API->>+SVC: login_with_google(code, code_verifier, nonce)
        SVC->>+G: exchange_code(code, code_verifier)
        G-->>-SVC: trả về id_token
        SVC->>+G: lấy JWKS để verify_id_token(id_token, nonce)
        G-->>-SVC: trả về khoá công khai JWKS
        alt Google lỗi hoặc id_token không hợp lệ
            SVC-->>-API: trả về lỗi UpstreamError hoặc Unauthorized
            API-->>-BG: trả về 502 UPSTREAM_ERROR hoặc 401 UNAUTHORIZED
            BG-->>UI: trả về lỗi đăng nhập
            UI->>UI: render thông báo đăng nhập thất bại
        else id_token hợp lệ
            activate SVC
            activate API
            SVC->>+Database: upsert_google_user(sub, email, name)
            Database-->>-SVC: trả về user
            SVC->>+Database: add(AuthSession(refresh_token_hash)) và COMMIT
            Database-->>-SVC: trả về phiên đăng nhập đã lưu
            SVC-->>-API: trả về TokenPair
            API-->>-BG: trả về 200 OK (access_token, refresh_token, expires_in)
            BG->>BG: saveTokens(tokens)
            BG-->>UI: trả về trạng thái đã đăng nhập
            UI->>UI: render giao diện chính
        end
    end
    deactivate BG
    deactivate UI
```

- **Công nghệ:** `chrome.identity.launchWebAuthFlow`, OAuth 2.0 Authorization Code + PKCE (S256), Google OIDC (JWKS), JWT, PostgreSQL (`users`, `auth_sessions`).
- **Kích hoạt:** Người dùng bấm "Đăng nhập bằng Google" trên Popup.
- **Chức năng:** Xác thực bằng Google mà không lưu mật khẩu; server đổi code lấy `id_token`, kiểm chứng chữ ký và `nonce`, rồi phát phiên riêng của ứng dụng (access token ngắn hạn + refresh token xoay vòng).
- **Luồng hoạt động:**
  - User bấm "Đăng nhập bằng Google" trên PopupUI.
  - PopupUI gửi thông điệp `auth/login` tới BackgroundWorker.
  - BackgroundWorker tự sinh `code_verifier`, `code_challenge` (S256), `state`, `nonce` qua `buildGoogleAuthRequest()`.
  - BackgroundWorker gọi `launchWebAuthFlow(authUrl)` tới GoogleOAuth (external service).
  - GoogleOAuth hiển thị màn hình chọn tài khoản; User đồng ý cấp quyền.
  - GoogleOAuth trả về redirect URL kèm `code`, `state` cho BackgroundWorker.
  - BackgroundWorker tự kiểm tra `state` qua `parseAuthRedirect(url, state)`.
  - Nhánh điều kiện [người dùng huỷ hoặc state không khớp]:
    - BackgroundWorker trả về lỗi `OAUTH_CANCELLED` cho PopupUI; PopupUI tự render thông báo thất bại.
  - Nhánh điều kiện [state hợp lệ]:
    - BackgroundWorker gọi `POST /auth/google/exchange` tới AuthController; AuthController gọi `login_with_google()` tới AuthService.
    - AuthService gọi `exchange_code()` tới GoogleOAuth và nhận về `id_token`; sau đó lấy JWKS để `verify_id_token(id_token, nonce)`.
    - Nhánh con [Google lỗi hoặc id_token không hợp lệ]: AuthService trả lỗi; AuthController trả `502 UPSTREAM_ERROR` hoặc `401 UNAUTHORIZED`; PopupUI render thông báo thất bại.
    - Nhánh con [id_token hợp lệ]: AuthService gọi `upsert_google_user()` rồi `add(AuthSession)` và COMMIT vào Database; trả `TokenPair`; AuthController trả `200 OK`; BackgroundWorker tự `saveTokens()`; PopupUI render giao diện chính.

---

## 5.1.2 Lưu ghi chú và tạo embedding

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant Page as WebPage (Toast)
    participant BG as BackgroundWorker
    participant API as NotesController
    participant SVC as NotesService
    participant W as IndexingWorker
    participant Q as QuotaService
    participant AI as AIProvider (external service)
    participant Database@{ "type" : "database" }

    Note over User,Database: Phần 1: Lưu ghi chú nhanh có Hoàn tác (Quick Note)
    User->>+BG: bôi đen văn bản, chọn menu "Ghi chú văn bản này"
    BG->>BG: startQuickNote(tabId, selection, folderId)
    BG->>BG: outbox.put(pendingId, notBefore = now + 5s)
    BG->>+Page: showToast(tabId, "Đã lưu", nút Hoàn tác)
    Page-->>-BG: trả về toast đã hiển thị
    deactivate BG
    alt người dùng bấm Hoàn tác trong 5 giây
        User->>+Page: bấm "Hoàn tác" trên toast
        Page->>+BG: quickNote/undo(pendingId)
        BG->>BG: outbox.remove(pendingId)
        BG-->>-Page: trả về đã huỷ, không gửi lên máy chủ
        Page->>Page: render "Đã hoàn tác"
        deactivate Page
    else hết 5 giây (alarm flush outbox)
        activate BG
        BG->>BG: outbox.due() lấy các mục đến hạn
        BG->>+API: POST /notes(content, url, title, folder_id) với Idempotency-Key = pendingId
        alt vượt giới hạn tần suất "write"
            API-->>-BG: trả về 429 RATE_LIMITED (Retry-After)
            BG->>BG: giữ trong outbox, hẹn thử lại theo backoff
        else trong giới hạn
            activate API
            API->>+SVC: create(user_id, cmd, idempotency_key)
            SVC->>+Database: find(idempotency_key)
            Database-->>-SVC: trả về kết quả tra cứu
            alt key đã dùng với cùng nội dung
                SVC-->>-API: trả về ghi chú đã tạo trước đó
                API-->>-BG: trả về 201 Created (bản cũ, không tạo trùng)
                BG->>BG: outbox.remove(pendingId)
            else key đã dùng với nội dung khác
                activate SVC
                activate API
                SVC-->>-API: trả về lỗi Conflict
                API-->>-BG: trả về 409 IDEMPOTENCY_KEY_REUSED
                BG->>BG: chuyển ghi chú sang mục "chưa gửi được"
            else key mới
                activate SVC
                activate API
                SVC->>+Database: add(note, index_status = PROCESSING)
                Database-->>-SVC: trả về note
                SVC->>+Database: enqueue(index_note) cùng transaction (outbox)
                Database-->>-SVC: trả về job đã xếp hàng
                SVC->>+Database: remember(idempotency_key) và COMMIT
                Database-->>-SVC: trả về xác nhận lưu
                SVC-->>-API: trả về note
                API-->>-BG: trả về 201 Created
                BG->>BG: outbox.remove(pendingId)
            end
        end
        deactivate BG
    end

    Note over User,Database: Phần 2: Tạo embedding bất đồng bộ (tiến trình worker)
    loop đến khi job DONE hoặc hết 5 lượt thử (backoff 10s, 20s, 40s, tối đa 10 phút)
        W->>+Database: claim job (FOR UPDATE SKIP LOCKED), attempts + 1
        Database-->>-W: trả về job index_note
        activate W
        W->>+Database: get_note_for_indexing(note_id)
        Database-->>-W: trả về note và content_hash
        alt note đã bị xoá
            W->>+Database: delete_for_note(note_id)
            Database-->>-W: trả về xác nhận xoá chunk
        else nội dung không đổi
            W->>+Database: set_index_status(READY)
            Database-->>-W: trả về xác nhận cập nhật
        else nội dung mới
            W->>W: chunker(content) chia đoạn theo câu, tối đa 1200 ký tự
            W->>+Q: leased(reserve embed_note)
            alt hết quota
                Q-->>-W: trả về QuotaExceeded
                W->>+Database: set_index_status(SKIPPED)
                Database-->>-W: trả về xác nhận cập nhật
            else đủ quota
                activate Q
                Q-->>-W: trả về QuotaLease
                W->>+AI: embed(chunks)
                alt AI trả kết quả
                    AI-->>-W: trả về vectors và usage
                    W->>+Database: replace_for_note(chunks, embeddings), READY, COMMIT
                    Database-->>-W: trả về xác nhận lưu
                    W->>+Q: commit(lease, usage)
                    Q-->>-W: trả về xác nhận trừ quota
                else AI lỗi tạm thời và còn lượt thử
                    activate AI
                    AI-->>-W: trả về AIProviderError (retryable)
                    W->>+Q: release(lease)
                    Q-->>-W: trả về xác nhận hoàn quota
                    W->>+Database: job QUEUED, run_after = now + backoff
                    Database-->>-W: trả về xác nhận hẹn thử lại
                else AI lỗi vĩnh viễn hoặc hết lượt thử
                    activate AI
                    AI-->>-W: trả về AIProviderError
                    W->>+Q: release(lease)
                    Q-->>-W: trả về xác nhận hoàn quota
                    W->>+Database: set_index_status(FAILED)
                    Database-->>-W: trả về xác nhận cập nhật
                end
            end
        end
        deactivate W
    end
```

- **Công nghệ:** `chrome.contextMenus`, `chrome.alarms`, IndexedDB (outbox), FastAPI, Idempotency-Key, PostgreSQL job queue (`FOR UPDATE SKIP LOCKED`, outbox pattern), pgvector, AI Embedding API.
- **Kích hoạt:** Người dùng bôi đen văn bản và chọn "Ghi chú văn bản này" (menu chuột phải hoặc phím tắt).
- **Chức năng:** Lưu ghi chú ngay ở client với 5 giây để hoàn tác, gửi lên server không bị trùng (Idempotency-Key), rồi tạo embedding bất đồng bộ ở worker có retry và kiểm soát quota.
- **Luồng hoạt động:**
  - **Phần 1:** User chọn menu "Ghi chú văn bản này"; BackgroundWorker tự `startQuickNote()` và `outbox.put()` với hạn gửi sau 5 giây; BackgroundWorker gọi `showToast()` hiện toast có nút Hoàn tác trên WebPage.
  - Nhánh điều kiện [người dùng bấm Hoàn tác trong 5 giây]: WebPage gửi `quickNote/undo` tới BackgroundWorker; BackgroundWorker tự `outbox.remove()` và trả về đã huỷ; WebPage render "Đã hoàn tác".
  - Nhánh điều kiện [hết 5 giây]: BackgroundWorker gọi `POST /notes` kèm Idempotency-Key tới NotesController.
    - Nhánh con [vượt tần suất]: trả `429 RATE_LIMITED`; BackgroundWorker giữ mục trong outbox để thử lại.
    - Nhánh con [trong giới hạn]: NotesController gọi `create()` tới NotesService; NotesService tra `idempotency_key` trong Database.
      - [cùng key, cùng nội dung]: trả `201 Created` với bản đã tạo.
      - [cùng key, khác nội dung]: trả `409 IDEMPOTENCY_KEY_REUSED`; BackgroundWorker chuyển ghi chú sang mục "chưa gửi được".
      - [key mới]: NotesService ghi note (`PROCESSING`), job `index_note` và idempotency key trong cùng một transaction rồi COMMIT; trả `201 Created`; BackgroundWorker tự xoá mục khỏi outbox.
  - **Phần 2 (khung loop):** IndexingWorker claim job từ Database, đọc note và `content_hash`.
    - [note đã bị xoá]: xoá chunk. [nội dung không đổi]: đặt `READY`, không tốn quota.
    - [nội dung mới]: IndexingWorker tự chia đoạn, gọi `leased()` tới QuotaService.
      - [hết quota]: đặt `SKIPPED`.
      - [đủ quota]: gọi `embed(chunks)` tới AIProvider. [thành công]: ghi chunk + embedding, `READY`, `commit()` quota. [lỗi tạm thời, còn lượt]: `release()` quota, job quay về `QUEUED` với backoff. [lỗi vĩnh viễn hoặc hết lượt]: `release()` quota, đặt `FAILED`.

---

## 5.1.3 Tìm kiếm ngữ nghĩa

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as SidePanelUI
    participant BG as BackgroundWorker
    participant API as SearchController
    participant SVC as SemanticSearchService
    participant Q as QuotaService
    participant AI as AIProvider (external service)
    participant Database@{ "type" : "database" }

    User->>+UI: nhập câu truy vấn tìm kiếm
    UI->>+BG: search/query(query, folder_id)
    BG->>+API: POST /search(query, folder_id)
    alt vượt giới hạn tần suất "search"
        API-->>-BG: trả về 429 RATE_LIMITED (Retry-After)
    else trong giới hạn
        activate API
        API->>+SVC: retrieve(user_id, query, folder_id)
        SVC->>+Q: leased(reserve search, estimate)
        alt hết quota
            Q-->>-SVC: trả về QuotaExceeded
            SVC-->>-API: trả về lỗi QuotaExceeded
            API-->>-BG: trả về 402 QUOTA_EXCEEDED
        else đủ quota
            activate Q
            activate SVC
            activate API
            Q-->>-SVC: trả về QuotaLease
            SVC->>+AI: embed([query])
            alt AI lỗi
                AI-->>-SVC: trả về AIProviderError
                SVC->>+Q: release(lease)
                Q-->>-SVC: trả về xác nhận hoàn quota
                SVC-->>-API: trả về lỗi UpstreamError
                API-->>-BG: trả về 502 AI_UNAVAILABLE
            else AI trả vector
                activate AI
                activate SVC
                activate API
                AI-->>-SVC: trả về vector truy vấn và usage
                SVC->>+Q: commit(lease, usage)
                Q-->>-SVC: trả về xác nhận trừ quota
                SVC->>+Database: hybrid_search(vector, query) pgvector + full-text unaccent, RRF
                Database-->>-SVC: trả về các chunk khớp
                SVC->>+Database: get_briefs(user_id, note_ids)
                Database-->>-SVC: trả về tiêu đề, URL ghi chú (đã loại ghi chú bị xoá)
                SVC-->>-API: trả về danh sách kết quả đã xếp hạng
                API-->>-BG: trả về 200 OK (results)
            end
        end
    end
    BG-->>-UI: trả về kết quả hoặc lỗi
    UI->>UI: render danh sách kết quả hoặc thông báo lỗi
    deactivate UI
```

- **Công nghệ:** AI Embedding API, PostgreSQL + pgvector (cosine), full-text search có `unaccent`, Reciprocal Rank Fusion (RRF).
- **Kích hoạt:** Người dùng nhập truy vấn trong ô tìm kiếm của Side Panel.
- **Chức năng:** Tìm ghi chú theo ý nghĩa (kể cả gõ không dấu), kết hợp tìm vector và tìm từ khoá, trừ quota theo token thực tế.
- **Luồng hoạt động:**
  - User nhập truy vấn trên SidePanelUI; SidePanelUI gửi `search/query` tới BackgroundWorker; BackgroundWorker gọi `POST /search` tới SearchController.
  - Nhánh điều kiện [vượt tần suất]: SearchController trả `429 RATE_LIMITED`.
  - Nhánh điều kiện [trong giới hạn]: SearchController gọi `retrieve()` tới SemanticSearchService; SemanticSearchService gọi `leased()` tới QuotaService.
    - Nhánh con [hết quota]: trả `402 QUOTA_EXCEEDED`.
    - Nhánh con [đủ quota]: SemanticSearchService gọi `embed([query])` tới AIProvider.
      - [AI lỗi]: `release()` quota; trả `502 AI_UNAVAILABLE`.
      - [AI trả vector]: `commit()` quota; gọi `hybrid_search()` rồi `get_briefs()` tới Database; trả `200 OK` kèm kết quả đã xếp hạng.
  - BackgroundWorker trả kết quả cho SidePanelUI; SidePanelUI tự render danh sách hoặc thông báo lỗi.

---

## 5.1.4 Tóm tắt nội dung bằng AI

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as SidePanelUI
    participant BG as BackgroundWorker
    participant API as SummaryController
    participant SVC as SummaryService
    participant Q as QuotaService
    participant AI as AIProvider (external service)
    participant NAPI as NotesController
    participant Database@{ "type" : "database" }

    User->>+UI: chọn "Tóm tắt" văn bản hoặc ghi chú
    UI->>+BG: summary/preview(text hoặc note_id)
    BG->>+API: POST /ai/summaries(text hoặc note_id) với Idempotency-Key
    alt vượt giới hạn tần suất "ai"
        API-->>-BG: trả về 429 RATE_LIMITED (Retry-After)
    else trong giới hạn
        activate API
        API->>+SVC: summarize(user_id, text, note_id, request_id)
        opt tóm tắt từ note_id
            SVC->>+Database: get_note_content(user_id, note_id)
            Database-->>-SVC: trả về nội dung ghi chú
        end
        SVC->>SVC: làm sạch và kiểm tra độ dài nội dung
        alt nội dung rỗng hoặc quá dài
            SVC-->>-API: trả về lỗi AppError hoặc PayloadTooLarge
            API-->>-BG: trả về 400 SUMMARY_INPUT_INVALID hoặc 413 SUMMARY_INPUT_TOO_LONG
        else nội dung hợp lệ
            activate SVC
            activate API
            SVC->>+Q: leased(reserve summary, prompt + 600 token đầu ra)
            alt hết quota
                Q-->>-SVC: trả về QuotaExceeded
                SVC-->>-API: trả về lỗi QuotaExceeded
                API-->>-BG: trả về 402 QUOTA_EXCEEDED
            else Idempotency-Key đã được dùng
                activate Q
                activate SVC
                activate API
                Q-->>-SVC: trả về QuotaLease (is_new = false)
                SVC-->>-API: trả về lỗi Conflict
                API-->>-BG: trả về 409 IDEMPOTENCY_KEY_REUSED
            else đủ quota
                activate Q
                activate SVC
                activate API
                Q-->>-SVC: trả về QuotaLease (is_new = true)
                SVC->>+AI: complete(prompt tóm tắt)
                alt AI lỗi
                    AI-->>-SVC: trả về AIProviderError
                    SVC->>+Q: release(lease)
                    Q-->>-SVC: trả về xác nhận hoàn quota
                    SVC-->>-API: trả về lỗi UpstreamError
                    API-->>-BG: trả về 502 AI_UNAVAILABLE
                else AI trả bản tóm tắt
                    activate AI
                    activate SVC
                    activate API
                    AI-->>-SVC: trả về bản tóm tắt và usage
                    SVC->>+Q: commit(lease, usage)
                    Q-->>-SVC: trả về xác nhận trừ quota
                    SVC-->>-API: trả về SummaryPreview
                    API-->>-BG: trả về 200 OK (summary, tokens_used)
                end
            end
        end
    end
    BG-->>-UI: trả về bản xem trước hoặc lỗi
    UI->>UI: render bản tóm tắt xem trước (chưa lưu)
    opt người dùng bấm "Lưu tóm tắt"
        User->>UI: bấm "Lưu tóm tắt"
        UI->>+BG: summary/save(note_id, summary)
        BG->>+NAPI: PUT /notes/{id}/summary
        NAPI->>+Database: cập nhật summary_text qua NotesService
        Database-->>-NAPI: trả về ghi chú đã cập nhật
        NAPI-->>-BG: trả về 200 OK
        BG-->>-UI: trả về ghi chú đã lưu
        UI->>UI: render thông báo đã lưu tóm tắt
    end
    deactivate UI
```

- **Công nghệ:** AI Chat Completion API, prompt có rào chắn nội dung không tin cậy, Idempotency-Key, quota giữ chỗ/chốt.
- **Kích hoạt:** Người dùng chọn "Tóm tắt" (menu chuột phải trên văn bản hoặc nút trên ghi chú).
- **Chức năng:** Sinh bản tóm tắt xem trước (không ghi DB); chỉ lưu vào ghi chú khi người dùng xác nhận.
- **Luồng hoạt động:**
  - User chọn "Tóm tắt"; SidePanelUI gửi `summary/preview` tới BackgroundWorker; BackgroundWorker gọi `POST /ai/summaries` tới SummaryController.
  - Nhánh điều kiện [vượt tần suất]: trả `429 RATE_LIMITED`.
  - Nhánh điều kiện [trong giới hạn]: SummaryController gọi `summarize()` tới SummaryService.
    - Nhánh tuỳ chọn [tóm tắt từ note_id]: SummaryService đọc nội dung ghi chú từ Database.
    - SummaryService tự làm sạch và kiểm tra độ dài. [rỗng hoặc quá dài]: trả `400` hoặc `413`.
    - [nội dung hợp lệ]: SummaryService gọi `leased()` tới QuotaService.
      - [hết quota]: trả `402 QUOTA_EXCEEDED`. [Idempotency-Key đã dùng]: trả `409 IDEMPOTENCY_KEY_REUSED`.
      - [đủ quota]: gọi `complete()` tới AIProvider. [AI lỗi]: `release()` quota, trả `502 AI_UNAVAILABLE`. [AI trả kết quả]: `commit()` quota, trả `200 OK` kèm bản tóm tắt.
  - SidePanelUI render bản xem trước.
  - Nhánh tuỳ chọn [người dùng bấm "Lưu tóm tắt"]: SidePanelUI gửi `summary/save`; BackgroundWorker gọi `PUT /notes/{id}/summary` tới NotesController; NotesController cập nhật `summary_text` trong Database; trả `200 OK`; SidePanelUI render thông báo đã lưu.

---

## 5.1.5 Xoá tài khoản và dữ liệu

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as SettingsUI
    participant BG as BackgroundWorker
    participant API as AccountController
    participant SVC as AccountService
    participant Database@{ "type" : "database" }

    User->>+UI: bấm "Xoá tài khoản"
    UI->>UI: render hộp thoại xác nhận xoá
    User->>UI: xác nhận xoá tài khoản
    UI->>+BG: account/delete
    BG->>+API: DELETE /me (Bearer access token)
    API->>+SVC: delete_account(user_id)
    SVC->>+Database: DELETE users WHERE id (ON DELETE CASCADE)
    alt không tìm thấy tài khoản
        Database-->>-SVC: trả về 0 dòng
        SVC->>+Database: ROLLBACK
        Database-->>-SVC: trả về xác nhận huỷ giao dịch
        SVC-->>-API: trả về lỗi NotFound
        API-->>-BG: trả về 404 USER_NOT_FOUND
        BG-->>UI: trả về lỗi xoá tài khoản
        UI->>UI: render thông báo lỗi
    else lỗi giữa chừng
        activate Database
        activate SVC
        activate API
        Database-->>-SVC: trả về lỗi cơ sở dữ liệu
        SVC->>+Database: ROLLBACK toàn bộ
        Database-->>-SVC: trả về xác nhận huỷ giao dịch
        SVC-->>-API: trả về Exception
        API-->>-BG: trả về 500 INTERNAL_ERROR
        BG-->>UI: trả về lỗi xoá tài khoản
        UI->>UI: render thông báo lỗi
    else xoá thành công
        activate Database
        activate SVC
        activate API
        Database-->>-SVC: trả về 1 dòng (xoá dây chuyền sessions, folders, notes, chunks, quota)
        SVC->>+Database: COMMIT
        Database-->>-SVC: trả về xác nhận ghi nhận
        SVC-->>-API: trả về hoàn tất
        API-->>-BG: trả về 204 No Content
        BG->>BG: clearTokens()
        BG-->>UI: trả về trạng thái đã đăng xuất
        UI->>UI: render màn hình đăng nhập
    end
    deactivate BG
    deactivate UI
```

- **Công nghệ:** PostgreSQL (khoá ngoại `ON DELETE CASCADE`, một transaction), `chrome.storage`.
- **Kích hoạt:** Người dùng bấm "Xoá tài khoản" trong trang Cài đặt và xác nhận.
- **Chức năng:** Xoá vĩnh viễn tài khoản và toàn bộ dữ liệu liên quan (phiên, thư mục, ghi chú, chunk/vector, quota) trong một transaction; lỗi giữa chừng thì rollback toàn bộ.
- **Luồng hoạt động:**
  - User bấm "Xoá tài khoản"; SettingsUI tự render hộp thoại xác nhận; User xác nhận.
  - SettingsUI gửi `account/delete` tới BackgroundWorker; BackgroundWorker gọi `DELETE /me` tới AccountController; AccountController gọi `delete_account()` tới AccountService; AccountService gửi `DELETE users` tới Database.
  - Nhánh điều kiện [không tìm thấy tài khoản]: ROLLBACK; trả `404 USER_NOT_FOUND`; SettingsUI render lỗi.
  - Nhánh điều kiện [lỗi giữa chừng]: ROLLBACK toàn bộ; trả `500 INTERNAL_ERROR`; SettingsUI render lỗi.
  - Nhánh điều kiện [xoá thành công]: COMMIT; trả `204 No Content`; BackgroundWorker tự `clearTokens()`; SettingsUI render màn hình đăng nhập.

---

## 5.1.6 Hỏi đáp AI dựa trên ghi chú cá nhân (RAG)

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as SidePanelUI (Chat)
    participant BG as BackgroundWorker
    participant API as RagController
    participant RAG as RAGService
    participant SS as SemanticSearchService
    participant Q as QuotaService
    participant AI as AIProvider (external service)

    User->>+UI: nhập câu hỏi
    UI->>+BG: Port qa-chat: ask(question, history, folderId)
    BG->>+API: POST /ai/chat(question, history, folder_id)
    alt vượt giới hạn tần suất "ai"
        API-->>-BG: trả về 429 RATE_LIMITED (Retry-After)
        BG-->>UI: trả về lỗi
    else trong giới hạn
        activate API
        API->>+RAG: prepare(user_id, question, history)
        RAG->>+SS: retrieve(question, top_k, "rag_retrieve")
        Note over SS,AI: Tham chiếu §5.1.3: giữ quota, embed truy vấn, hybrid search (có thể trả 402 hoặc 502)
        SS-->>-RAG: trả về các chunk ngữ cảnh
        alt không có ngữ cảnh phù hợp
            RAG-->>-API: trả về PreparedChat (không giữ quota)
            API-->>-BG: trả về 200 SSE (sources rỗng, câu trả lời mặc định, done)
            BG-->>UI: trả về câu trả lời mặc định
        else có ngữ cảnh
            activate RAG
            activate API
            RAG->>RAG: chat_messages(question, history, chunks)
            RAG->>+Q: reserve(chat, prompt + token đầu ra tối đa)
            alt hết quota
                Q-->>-RAG: trả về QuotaExceeded
                RAG-->>-API: trả về lỗi QuotaExceeded
                API-->>-BG: trả về 402 QUOTA_EXCEEDED
                BG-->>UI: trả về lỗi hết quota
            else đủ quota
                activate Q
                activate RAG
                activate API
                Q-->>-RAG: trả về QuotaLease
                RAG-->>-API: trả về PreparedChat
                API-->>BG: trả về 200 OK (text/event-stream)
                API->>+RAG: stream(prepared)
                RAG-->>API: trả về event sources
                API-->>BG: trả về SSE sources (trích dẫn)
                BG-->>UI: trả về danh sách nguồn
                RAG->>+AI: stream(messages)
                loop mỗi đoạn văn bản được sinh ra
                    AI-->>RAG: trả về delta
                    RAG-->>API: trả về event delta
                    API-->>BG: trả về SSE delta
                    BG-->>UI: trả về đoạn câu trả lời
                    UI->>UI: render nối tiếp câu trả lời
                end
                alt sinh xong
                    AI-->>-RAG: trả về usage
                    RAG->>+Q: commit(lease, usage)
                    Q-->>-RAG: trả về xác nhận trừ quota
                    RAG-->>-API: trả về event done
                    API-->>-BG: trả về SSE done (tokens_used)
                else AI lỗi giữa chừng
                    activate AI
                    activate RAG
                    activate API
                    AI-->>-RAG: trả về AIProviderError
                    RAG->>+Q: commit phần đã sinh (chưa sinh thì release)
                    Q-->>-RAG: trả về xác nhận quyết toán quota
                    RAG-->>-API: trả về event error
                    API-->>-BG: trả về SSE error AI_UNAVAILABLE
                else người dùng bấm Dừng
                    activate AI
                    activate RAG
                    activate API
                    User->>UI: bấm "Dừng"
                    UI->>BG: Port qa-chat: stop
                    BG->>API: AbortController.abort() ngắt kết nối SSE
                    API->>RAG: aclose() generator
                    RAG->>AI: huỷ luồng sinh
                    deactivate AI
                    RAG->>+Q: commit phần ước lượng hoặc release (CancelScope shield)
                    Q-->>-RAG: trả về xác nhận quyết toán quota
                    deactivate RAG
                    deactivate API
                end
            end
        end
    end
    BG-->>-UI: trả về kết thúc phiên hỏi đáp
    UI->>UI: render trạng thái hoàn tất
    deactivate UI
```

- **Công nghệ:** Server-Sent Events (SSE), `chrome.runtime.Port`, AbortController, AI Chat Completion (streaming), hybrid search §5.1.3, AnyIO `CancelScope(shield=True)`.
- **Kích hoạt:** Người dùng gửi câu hỏi trong tab Chat của Side Panel.
- **Chức năng:** Trả lời câu hỏi dựa trên ghi chú của chính người dùng, có trích dẫn nguồn, hiển thị dần từng đoạn; dừng giữa chừng thì chỉ trừ phần đã sinh.
- **Luồng hoạt động:**
  - User nhập câu hỏi; SidePanelUI gửi `ask` qua Port `qa-chat` tới BackgroundWorker; BackgroundWorker gọi `POST /ai/chat` tới RagController.
  - Nhánh điều kiện [vượt tần suất]: trả `429 RATE_LIMITED`.
  - Nhánh điều kiện [trong giới hạn]: RagController gọi `prepare()` tới RAGService; RAGService gọi `retrieve()` tới SemanticSearchService (như §5.1.3).
    - [không có ngữ cảnh]: trả câu trả lời mặc định, không giữ quota.
    - [có ngữ cảnh]: RAGService tự dựng prompt, gọi `reserve()` tới QuotaService. [hết quota]: trả `402`. [đủ quota]: RagController mở luồng SSE, gửi `sources`; RAGService gọi `stream()` tới AIProvider.
      - Khung loop [mỗi đoạn được sinh]: delta đi qua RagController, BackgroundWorker tới SidePanelUI; SidePanelUI render nối tiếp.
      - [sinh xong]: `commit()` theo usage thật; gửi `done`. [AI lỗi giữa chừng]: quyết toán phần đã sinh; gửi `error AI_UNAVAILABLE`. [người dùng bấm Dừng]: SidePanelUI gửi `stop`; BackgroundWorker abort kết nối; RAGService đóng generator và quyết toán quota trong vùng được shield.

---

## 5.1.7 Tìm đoạn khớp truy vấn trên trang (PageMatch / AutoChunk)

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    actor User
    participant UI as SidePanelUI (PageFinder)
    participant BG as BackgroundWorker
    participant Page as WebPage (external)
    participant API as PageMatchController
    participant SVC as PageMatchService
    participant EX as TrafilaturaExtractor
    participant Q as QuotaService
    participant AI as AIProvider (external service)

    User->>+UI: nhập truy vấn cần tìm trên trang
    UI->>+BG: pageMatch/run(query)
    BG->>+Page: executeScript(getRawHtml)
    Page-->>-BG: trả về HTML trang hiện tại
    BG->>+API: POST /ai/page-match(query, html, url)
    alt vượt giới hạn tần suất "page_match"
        API-->>-BG: trả về 429 RATE_LIMITED (Retry-After)
    else trong giới hạn
        activate API
        API->>+SVC: match(user_id, query, html, url)
        SVC->>SVC: chuẩn hoá truy vấn, kiểm tra kích thước HTML
        alt truy vấn không hợp lệ hoặc HTML quá lớn
            SVC-->>-API: trả về lỗi Unprocessable hoặc PayloadTooLarge
            API-->>-BG: trả về 422 PAGE_MATCH_QUERY_INVALID hoặc 413 PAGE_TOO_LONG
        else đầu vào hợp lệ
            activate SVC
            activate API
            SVC->>+EX: extract_blocks(html) trong tiến trình riêng, có timeout
            alt không trích được nội dung
                EX-->>-SVC: trả về ExtractError
                SVC-->>-API: trả về lỗi Unprocessable
                API-->>-BG: trả về 422 PAGE_NO_CONTENT
            else trích được nội dung
                activate EX
                activate SVC
                activate API
                EX-->>-SVC: trả về danh sách khối văn bản
                SVC->>+Q: leased(reserve page_match_embed)
                alt hết quota
                    Q-->>-SVC: trả về QuotaExceeded
                    SVC-->>-API: trả về lỗi QuotaExceeded
                    API-->>-BG: trả về 402 QUOTA_EXCEEDED
                else đủ quota
                    activate Q
                    activate SVC
                    activate API
                    Q-->>-SVC: trả về QuotaLease
                    SVC->>+AI: embed([query, các khối])
                    alt AI lỗi
                        AI-->>-SVC: trả về AIProviderError
                        SVC->>+Q: release(lease)
                        Q-->>-SVC: trả về xác nhận hoàn quota
                        SVC-->>-API: trả về lỗi UpstreamError
                        API-->>-BG: trả về 502 AI_UNAVAILABLE
                    else AI trả vector
                        activate AI
                        activate SVC
                        activate API
                        AI-->>-SVC: trả về vectors và usage
                        SVC->>+Q: commit(lease, usage)
                        Q-->>-SVC: trả về xác nhận trừ quota
                        SVC->>SVC: cosine(), lọc theo ngưỡng điểm, chọn top ứng viên
                        opt có ứng viên vượt ngưỡng (LLM xác minh)
                            SVC->>+Q: leased(reserve page_match_verify)
                            alt hết quota
                                Q-->>-SVC: trả về QuotaExceeded
                                SVC->>SVC: bỏ qua xác minh, gắn warning VERIFY_UNAVAILABLE
                            else đủ quota
                                activate Q
                                Q-->>-SVC: trả về QuotaLease
                                SVC->>+AI: complete(prompt xác minh) có timeout
                                alt AI không khả dụng hoặc quá thời gian
                                    AI-->>-SVC: trả về AIProviderError hoặc TimeoutError
                                    SVC->>+Q: release(lease)
                                    Q-->>-SVC: trả về xác nhận hoàn quota
                                    SVC->>SVC: gắn warning VERIFY_UNAVAILABLE, giữ ứng viên theo điểm
                                else AI khả dụng
                                    activate AI
                                    AI-->>-SVC: trả về các đoạn được xác nhận và usage
                                    SVC->>+Q: commit(lease, usage)
                                    Q-->>-SVC: trả về xác nhận trừ quota
                                    SVC->>SVC: parse_verdicts() lọc đoạn được xác nhận
                                end
                            end
                        end
                        SVC->>SVC: compute_match_ratio(), chọn mode segments hoặc full_page
                        SVC-->>-API: trả về PageMatchResult
                        API-->>-BG: trả về 200 OK (mode, items, warning)
                    end
                end
            end
        end
    end
    BG-->>-UI: trả về kết quả hoặc lỗi
    UI->>UI: render danh sách đoạn khớp
    opt người dùng bấm "Tô sáng trên trang"
        User->>UI: bấm "Tô sáng trên trang"
        UI->>+BG: pageMatch/highlight(tabId, items)
        BG->>+Page: executeScript(highlightBlocksByText, items)
        Page-->>-BG: trả về số đoạn đã tô sáng
        BG-->>-UI: trả về HighlightResult
        UI->>UI: render số đoạn đã tô sáng
    end
    deactivate UI
```

- **Công nghệ:** `chrome.scripting.executeScript`, Trafilatura (process pool, có timeout), AI Embedding API, cosine similarity, AI Chat Completion (thẩm định), quota hai lượt (embed + verify).
- **Kích hoạt:** Người dùng nhập truy vấn trong Page Finder của Side Panel khi đang mở một trang web.
- **Chức năng:** Trích nội dung chính của trang, tìm các đoạn liên quan đến truy vấn bằng embedding, xác minh lại bằng LLM khi có thể, rồi tô sáng trên trang để người dùng lưu thành ghi chú.
- **Luồng hoạt động:**
  - User nhập truy vấn; SidePanelUI gửi `pageMatch/run`; BackgroundWorker gọi `executeScript(getRawHtml)` lấy HTML từ WebPage; BackgroundWorker gọi `POST /ai/page-match` tới PageMatchController.
  - Nhánh điều kiện [vượt tần suất]: trả `429 RATE_LIMITED`.
  - Nhánh điều kiện [trong giới hạn]: PageMatchController gọi `match()` tới PageMatchService; PageMatchService tự kiểm tra đầu vào.
    - [không hợp lệ]: trả `422` hoặc `413`.
    - [hợp lệ]: gọi `extract_blocks()` tới TrafilaturaExtractor. [không trích được]: trả `422 PAGE_NO_CONTENT`. [trích được]: gọi `leased()` tới QuotaService.
      - [hết quota]: trả `402`. [đủ quota]: gọi `embed()` tới AIProvider. [AI lỗi]: `release()`, trả `502`. [AI trả vector]: `commit()`; tự tính cosine và chọn ứng viên.
      - Nhánh tuỳ chọn [có ứng viên vượt ngưỡng]: giữ quota lượt 2 và gọi `complete()` xác minh. [hết quota] hoặc [AI không khả dụng/quá thời gian]: gắn warning `VERIFY_UNAVAILABLE`, dùng thứ tự theo điểm. [AI khả dụng]: `commit()` và lọc đoạn được xác nhận.
      - PageMatchService tự tính `match_ratio`, chọn `segments` hoặc `full_page`; trả `200 OK`.
  - SidePanelUI render danh sách đoạn khớp.
  - Nhánh tuỳ chọn [người dùng bấm "Tô sáng trên trang"]: SidePanelUI gửi `pageMatch/highlight`; BackgroundWorker gọi `executeScript(highlightBlocksByText)`; WebPage trả số đoạn đã tô sáng.

---

## 5.1.8 Làm mới phiên đăng nhập (xoay vòng refresh token)

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    participant BG as BackgroundWorker
    participant API as QuickAssistAPI
    participant AC as AuthController
    participant SVC as AuthService
    participant Database@{ "type" : "database" }

    activate BG
    BG->>+API: request bất kỳ (Bearer access token)
    API-->>-BG: trả về 401 TOKEN_EXPIRED
    BG->>+AC: POST /auth/refresh(refresh_token)
    AC->>+SVC: refresh(refresh_token, user_agent)
    SVC->>+Database: get_by_hash_for_update(hash(refresh_token))
    Database-->>-SVC: trả về phiên đăng nhập hoặc rỗng
    alt không tồn tại
        SVC-->>-AC: trả về lỗi Unauthorized
        AC-->>-BG: trả về 401 REFRESH_INVALID
        BG->>BG: clearTokens(), yêu cầu đăng nhập lại
    else phiên đã bị xoay hoặc thu hồi (nghi bị đánh cắp)
        activate SVC
        activate AC
        SVC->>+Database: revoke_all_for_user(user_id) và COMMIT
        Database-->>-SVC: trả về xác nhận thu hồi
        SVC-->>-AC: trả về lỗi Unauthorized
        AC-->>-BG: trả về 401 REFRESH_REUSED
        BG->>BG: clearTokens(), yêu cầu đăng nhập lại
    else phiên hết hạn
        activate SVC
        activate AC
        SVC-->>-AC: trả về lỗi Unauthorized
        AC-->>-BG: trả về 401 REFRESH_EXPIRED
        BG->>BG: clearTokens(), yêu cầu đăng nhập lại
    else phiên hợp lệ
        activate SVC
        activate AC
        SVC->>+Database: add(AuthSession mới), phiên cũ revoked_at và replaced_by
        Database-->>-SVC: trả về phiên mới
        SVC->>+Database: touch(last_active_at) và COMMIT
        Database-->>-SVC: trả về xác nhận ghi nhận
        SVC-->>-AC: trả về TokenPair mới
        AC-->>-BG: trả về 200 OK (access_token, refresh_token)
        BG->>BG: saveTokens(tokens)
        BG->>+API: gửi lại request ban đầu (thử lại 1 lần)
        API-->>-BG: trả về kết quả của request
    end
    deactivate BG
```

- **Công nghệ:** JWT access token ngắn hạn, refresh token lưu dạng hash, xoay vòng (rotation) + phát hiện tái sử dụng, `SELECT … FOR UPDATE`.
- **Kích hoạt:** Bất kỳ request nào của BackgroundWorker nhận `401 TOKEN_EXPIRED`.
- **Chức năng:** Cấp cặp token mới mà người dùng không phải đăng nhập lại; nếu refresh token cũ bị dùng lại (dấu hiệu bị đánh cắp) thì thu hồi mọi phiên của user.
- **Luồng hoạt động:**
  - BackgroundWorker gửi request kèm access token tới QuickAssistAPI và nhận `401 TOKEN_EXPIRED`.
  - BackgroundWorker gọi `POST /auth/refresh` tới AuthController; AuthController gọi `refresh()` tới AuthService; AuthService khoá và đọc phiên theo hash trong Database.
  - Nhánh điều kiện [không tồn tại]: trả `401 REFRESH_INVALID`; BackgroundWorker tự xoá token.
  - Nhánh điều kiện [đã bị xoay hoặc thu hồi]: AuthService thu hồi mọi phiên của user và COMMIT; trả `401 REFRESH_REUSED`; BackgroundWorker tự xoá token.
  - Nhánh điều kiện [hết hạn]: trả `401 REFRESH_EXPIRED`; BackgroundWorker tự xoá token.
  - Nhánh điều kiện [hợp lệ]: AuthService tạo phiên mới, đánh dấu phiên cũ đã thay thế, cập nhật `last_active_at` và COMMIT; trả `200 OK`; BackgroundWorker tự `saveTokens()` rồi gửi lại request ban đầu một lần.

---

## 5.1.9 Vòng đời quota AI (giữ chỗ, chốt hoặc hoàn, dọn giữ chỗ treo)

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#FFFFFF", "primaryBorderColor": "#000000", "primaryTextColor": "#000000", "lineColor": "#2C3E50", "actorBkg": "#FFFFFF", "actorBorder": "#000000", "actorLineColor": "#2C3E50", "signalColor": "#2C3E50", "signalTextColor": "#000000", "activationBkgColor": "#E3E9F0", "activationBorderColor": "#2C3E50", "labelBoxBkgColor": "#FFFFFF", "labelBoxBorderColor": "#000000", "loopTextColor": "#000000", "noteBkgColor": "#FFFFFF", "noteBorderColor": "#000000", "fontFamily": "Arial"}, "sequence": {"mirrorActors": false, "messageAlign": "left"}}}%%
sequenceDiagram
    participant S as AIFeatureService
    participant Q as QuotaService
    participant AI as AIProvider (external service)
    participant W as HousekeepingWorker
    participant Database@{ "type" : "database" }

    Note over S,Database: Phần 1: Giữ chỗ, chốt hoặc hoàn quota cho một lệnh gọi AI
    activate S
    S->>+Q: leased(user_id, operation, estimate, request_id)
    Q->>+Database: ensure_account(user_id, default_limit)
    Database-->>-Q: trả về tài khoản quota
    Q->>+Database: find_ledger(request_id)
    Database-->>-Q: trả về ledger hoặc rỗng
    alt request_id đã có trong ledger
        Q-->>-S: trả về QuotaLease (is_new = false)
    else request_id mới
        activate Q
        Q->>+Database: try_reserve(user_id, estimate) UPDATE có điều kiện
        Database-->>-Q: trả về số dòng cập nhật
        alt không đủ hạn mức
            Q->>+Database: ROLLBACK
            Database-->>-Q: trả về xác nhận huỷ
            Q-->>-S: trả về QuotaExceeded (ánh xạ 402)
        else đủ hạn mức
            activate Q
            Q->>+Database: add_ledger(RESERVED) và COMMIT
            Database-->>-Q: trả về xác nhận giữ chỗ
            Q-->>-S: trả về QuotaLease (is_new = true)
            S->>+AI: gọi AI (embed, complete hoặc stream)
            alt AI thành công
                AI-->>-S: trả về kết quả và usage
                S->>+Q: commit(lease, usage)
                Q->>+Database: settle_ledger(RESERVED sang COMMITTED)
                Database-->>-Q: trả về 1 dòng
                Q->>+Database: apply_settlement(reserved, actual) và COMMIT
                Database-->>-Q: trả về xác nhận quyết toán
                Q-->>-S: trả về hoàn tất
            else lỗi bất kỳ hoặc request bị huỷ
                activate AI
                AI-->>-S: trả về lỗi hoặc CancelledError
                S->>+Q: release(lease) trong CancelScope(shield)
                Q->>+Database: settle_ledger(RESERVED sang RELEASED)
                Database-->>-Q: trả về 1 dòng
                Q->>+Database: apply_settlement(reserved, 0) và COMMIT
                Database-->>-Q: trả về xác nhận hoàn quota
                Q-->>-S: trả về hoàn tất
            end
        end
    end
    deactivate S

    Note over S,Database: Phần 2: Dọn giữ chỗ bị treo (tiến trình worker)
    loop mỗi 5 phút, đến khi worker dừng
        activate W
        W->>+Q: release_stale(older_than_minutes = 15)
        Q->>+Database: release_stale_ledgers(cutoff) RETURNING
        Database-->>-Q: trả về danh sách giữ chỗ bị treo
        loop mỗi giữ chỗ bị treo
            Q->>+Database: apply_settlement(reserved, 0)
            Database-->>-Q: trả về xác nhận hoàn quota
        end
        Q->>+Database: COMMIT
        Database-->>-Q: trả về xác nhận ghi nhận
        Q-->>-W: trả về số giữ chỗ đã hoàn
        deactivate W
    end
```

- **Công nghệ:** PostgreSQL (`quota_accounts`, `quota_ledger`), UPDATE có điều kiện (nguyên tử, không race), AnyIO `CancelScope(shield=True)`, tiến trình worker định kỳ.
- **Kích hoạt:** Mọi dịch vụ gọi AI (Summary, Search, RAG, PageMatch, Indexing) trước mỗi lệnh gọi; worker chạy dọn dẹp mỗi 5 phút.
- **Chức năng:** Không bao giờ vượt hạn mức kể cả khi nhiều request song song; chỉ trừ token thực tế; hoàn quota khi lỗi hoặc bị huỷ; tự hoàn giữ chỗ bị treo khi tiến trình chết giữa chừng.
- **Luồng hoạt động:**
  - **Phần 1:** AIFeatureService gọi `leased()` tới QuotaService; QuotaService đảm bảo có tài khoản quota và tra `request_id` trong ledger.
  - Nhánh điều kiện [request_id đã có]: trả `QuotaLease (is_new = false)`, caller tự quyết định (vd summary trả `409`).
  - Nhánh điều kiện [request_id mới]: QuotaService gọi `try_reserve()` (UPDATE có điều kiện).
    - [không đủ hạn mức]: ROLLBACK; trả `QuotaExceeded` (ánh xạ `402`).
    - [đủ hạn mức]: ghi ledger `RESERVED` và COMMIT; AIFeatureService gọi AI.
      - [AI thành công]: `commit()`: ledger sang `COMMITTED`, trừ token thực tế, trả phần dư.
      - [lỗi bất kỳ hoặc bị huỷ]: `release()` trong vùng shield: ledger sang `RELEASED`, hoàn toàn bộ giữ chỗ.
  - **Phần 2 (khung loop):** HousekeepingWorker gọi `release_stale()` mỗi 5 phút; QuotaService chuyển các ledger `RESERVED` quá 15 phút sang `RELEASED`; khung loop con hoàn `reserved_tokens` cho từng giữ chỗ; COMMIT; trả số giữ chỗ đã hoàn.
