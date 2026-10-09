"""Tạo QuickAssist_KeHoach_PhanCong_v2.xlsx từ bản gốc (giữ nguyên định dạng/bố cục).

Chạy: python scripts/generate_plan_v2.py docs/plan/QuickAssist_KeHoach_PhanCong_GoogleOAuth_CoTen.xlsx docs/plan/QuickAssist_KeHoach_PhanCong_v2.xlsx
"""
import copy
import sys

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SRC, DST = sys.argv[1], sys.argv[2]
wb = openpyxl.load_workbook(SRC)

SON, QUANG, VINH, DUONG = "Lê Đăng Sơn", "Trịnh Mạnh Quang", "Mai Đức Vinh", "Trần Thùy Dương"
NS, DT, DONE = "Chưa bắt đầu", "Đang thực hiện", "Đã hoàn thành"
API = "apps/api/src/quickassist/"
EXT = "apps/extension/src/"

# ID, Giai đoạn, Hạng mục, Task, Owner, Phối hợp, T_BĐ, T_KT, Giờ, Ưu tiên, Phụ thuộc, Deliverable, Nghiệm thu, Trạng thái, %, Thư mục code
B = [
 ("P01","Khởi động","Kiến trúc","Cả nhóm review & chốt kiến trúc phân tầng theo SDS Hình 1 (presentation/business/data_access/data/infrastructure), 9 ADR, luật L1–L7",SON,"Cả nhóm",1,1,4,"P0","","docs/architecture + docs/adr đã duyệt","Mọi thành viên chỉ ra được: tầng + thư mục service mình sở hữu, cách gọi service khác (package public / RPC)",DT,0.8,"docs/"),
 ("P02","Khởi động","API & dữ liệu","Duyệt quy ước API: hợp nhất /notes/quick, /notes/ragged → POST /notes; PATCH theo id; bulk-delete; error contract",QUANG,SON,1,1,4,"P0","P01","docs/api/conventions.md + OpenAPI","Không còn endpoint mâu thuẫn giữa SDS, kịch bản và code",DT,0.7,"docs/api/"),
 ("P03","Khởi động","AI","Spike OpenAI: đo latency/chi phí embedding & tóm tắt cho văn bản tiếng Việt; chốt model, chunk size, hạn mức quota",VINH,QUANG,1,1,6,"P0","P01","Báo cáo spike + giá trị cấu hình .env","Có số liệu p50/p95, token/1000 ký tự, đề xuất QUOTA_DEFAULT_TOKENS",NS,0,API+"infrastructure/openai/"),
 ("P04","Khởi động","UX","User flow + wireframe 6 luồng SDS: đăng nhập, ghi chú nhanh + hoàn tác, thư viện/thư mục, tìm kiếm, tóm tắt, xoá tài khoản",DUONG,SON,1,1,8,"P0","P01","Wireframe + user flow","Bao phủ happy path, loading, empty, error, undo, hết quota",NS,0,"docs/ux/"),
 ("P05","Nền tảng","Extension","Review base code extension (background/content/ui/shared); tạo OAuth client trên Google Cloud; load unpacked chạy được",SON,DUONG,1,2,6,"P0","P01","Extension skeleton chạy được","npm test + build pass; cài được ở developer mode",DT,0.7,EXT+"background, shared, content"),
 ("P06","Nền tảng","Backend","Review base code backend: infrastructure/ (config, logging, jobs, security), data/database, presentation/api (deps, lỗi, middleware); docker-compose; migration 0001",QUANG,VINH,1,2,6,"P0","P01","Backend skeleton chạy được","docker compose up chạy; /health/ready ok; pytest pass",DT,0.7,API+"infrastructure/, data/, presentation/api/; infra/"),
 ("P07","Nền tảng","AI","Review AI adapter (port, mock, openai); thêm test adapter OpenAI bằng HTTP mock (429/5xx/timeout)",VINH,QUANG,1,2,6,"P0","P03","AI adapter + test","Đổi provider qua AI_PROVIDER; retry/backoff có test",DT,0.6,API+"infrastructure/openai/"),
 ("P08","Nền tảng","QA","Test strategy + ma trận truy vết (RTM) từ FR trong SDS → test case; Definition of Done",DUONG,SON,1,2,6,"P0","P04","Test plan + RTM","Mỗi FR Must-have có test case và người chịu trách nhiệm",NS,0,"docs/qa/"),
 ("P09","Nền tảng","Quy trình","Bật branch protection main/dev, điền GitHub username vào CODEOWNERS, CI xanh trên PR đầu tiên",SON,QUANG,1,1,3,"P0","P01","CI + CODEOWNERS hoạt động","PR vi phạm luật kiến trúc bị CI chặn",DT,0.8,".github/"),
 ("D01","Khởi động","Tài liệu","Cập nhật SDS theo docs/architecture/sds-review.md (11 điểm): bỏ chữ microservice ở §5.2, vẽ lại Hình 1 có QuotaService + repositories + AI adapter, thiết kế dữ liệu §6, trade-off",SON,VINH,1,2,4,"P0","P01","SDS v1.1","SDS, kiến trúc và code thống nhất",NS,0,"docs/specs/"),
 ("A01","Nền tảng","Dữ liệu","Review data/models + migration 0001, vẽ ERD (khớp SDS §6); quy ước migration theo service",QUANG,VINH,2,2,4,"P0","P06","ERD + migration","alembic upgrade/downgrade/check pass trên CI",DT,0.6,"apps/api/migrations/"),
 ("A02","Nền tảng","Tài khoản","Hoàn thiện Google OAuth backend: exchange code, verify id_token (JWKS), refresh xoay vòng, test với id_token giả lập",QUANG,SON,2,3,8,"P0","A01,P02","Auth API + test","Validate state/nonce/iss/aud/exp/email_verified; reuse refresh → thu hồi mọi phiên",DT,0.5,API+"business/auth/, infrastructure/google_oauth/, controllers/auth_controller.py"),
 ("A03","Nền tảng","Tài khoản","Google OAuth trên extension: launchWebAuthFlow + PKCE, lưu session, refresh single-flight, logout",SON,QUANG,2,3,8,"P0","A02,P05","Login/logout hoạt động","Không có form mật khẩu; không log token; hết phiên xử lý đúng",DT,0.5,EXT+"background/auth/"),
 ("A04","Nền tảng","Quota","Hoàn thiện quota reserve/commit/release, GET /me/quota, test đồng thời (race) và chống trừ trùng",VINH,QUANG,2,3,8,"P0","A01,P03","Quota module + test","Chặn đúng khi hết quota; ledger request_id duy nhất; không âm",DT,0.5,API+"business/quota/, data_access/repositories/quota_repository.py"),
 ("A05","Nền tảng","UI","Design system + app shell: token màu, Button/Spinner/Empty/Error/Toast/Modal, điều hướng bàn phím",DUONG,SON,2,3,8,"P0","P04,P05","UI component set","Mọi màn dùng chung component; đạt tương phản WCAG AA",DT,0.3,EXT+"ui/components, ui/styles.css"),
 ("A06","Nền tảng","Tài khoản","GET /me, DELETE /me: xoá tài khoản + toàn bộ dữ liệu trong 1 transaction (SDS §5.1.5) — task MỚI",QUANG,DUONG,3,3,4,"P0","A01","Accounts API + test cascade","Sau khi xoá: 0 dòng ở mọi bảng của user; lỗi giữa chừng → rollback",DT,0.6,API+"business/auth/account_service.py, controllers/account_controller.py"),
 ("A07","Nền tảng","Vận hành","Log JSON có request_id, che dữ liệu nhạy cảm, log lỗi & hoạt động chính (FR ghi log) — task MỚI",QUANG,VINH,3,3,4,"P0","P06","Logging + test redaction","Không có token/nội dung note trong log; mọi lỗi tra được bằng request_id",DT,0.6,API+"infrastructure/logging.py"),
 ("SUM-01","Nền tảng","Tóm tắt","Đặc tả tóm tắt (thay G01): đầu vào (note/vùng chọn), độ dài, prompt chống injection, quota, xác nhận trước khi lưu",VINH,DUONG,2,2,4,"P0","P04","Đặc tả + acceptance","Chốt input/output/giới hạn; bộ 10 trang mẫu (có trang chứa prompt injection)",NS,0,"docs/specs/"),
 ("N01","MVP Ghi chú","Extension","Bắt vùng chọn: menu chuột phải + Ctrl+Alt+N qua chrome.scripting/activeTab (không content script thường trực)",SON,DUONG,3,3,6,"P0","P05","Selection capture","Lấy text + URL + tiêu đề; chạy trên 5 trang mẫu; trang chrome:// không lỗi",DT,0.6,EXT+"background/index.ts, content/"),
 ("N02","MVP Ghi chú","Extension","Toast đếm ngược 5s + Hoàn tác (nút & Ctrl+Alt+Z), Shadow DOM không vỡ CSS trang (Dương duyệt giao diện)",SON,DUONG,3,4,6,"P0","A05,N01","Undo toast","Hoàn tác huỷ đúng note; hiển thị trạng thái đã gửi/đã hoàn tác",DT,0.5,EXT+"content/injected.ts (renderToast)"),
 ("N03","MVP Ghi chú","Backend","Notes API: POST /notes (Idempotency-Key), thư mục + Inbox mặc định, validation, ownership",QUANG,SON,3,4,8,"P0","A01,A02,P02","Notes API + test","Gửi lại cùng key không tạo trùng; user khác nhận 404; integration test pass",DT,0.6,API+"business/notes/, controllers/notes_controller.py"),
 ("N04","MVP Ghi chú","AI","Chunking v2 (theo ngữ nghĩa/câu tiếng Việt) giữ nguyên chữ ký hàm; đo ảnh hưởng tới chất lượng tìm kiếm",VINH,QUANG,3,4,8,"P0","P07","chunking.py + benchmark","Không mất nội dung; chunk ≤ giới hạn; có số liệu so sánh v1/v2",DT,0.3,API+"business/semantic_search/chunking.py"),
 ("N05","MVP Ghi chú","AI","Job index: embed → pgvector → READY/SKIPPED/FAILED, trừ quota theo usage thật, retry có kiểm soát",VINH,QUANG,4,4,8,"P0","N03,N04,A04","Indexing job + test","Hết quota → SKIPPED không trừ; lỗi AI → retry rồi FAILED; sửa note không kẹt PROCESSING",DT,0.6,API+"business/semantic_search/indexing_job.py"),
 ("N06","MVP Ghi chú","Extension","Outbox IndexedDB + retry alarm + hiển thị note gửi thất bại để gửi lại thủ công",SON,QUANG,4,4,8,"P0","N02,N03","Outbox + trạng thái","Mất mạng không mất note; không trùng khi retry",DT,0.5,EXT+"background/notes/quick-note.ts"),
 ("N07","MVP Ghi chú","QA","E2E ghi chú nhanh: hoàn tác, mất mạng, hết quota, trang đặc biệt",DUONG,SON,4,4,6,"P0","N02,N03,N05,N06","E2E report","Các ca P0 pass; lỗi có bằng chứng + owner",NS,0,"apps/extension/tests, docs/qa/"),
 ("C01","Thư viện note","Backend","Hoàn thiện CRUD: PATCH có version (409), bulk-delete, phân trang cursor, đổi tên/xoá thư mục",QUANG,SON,4,5,8,"P0","N03","CRUD API + test","Ownership bắt buộc; 409 đúng; xoá thư mục → note về Inbox",DT,0.6,API+"business/notes/, data_access/(note|folder)_repository.py, controllers/(notes|folders)_controller.py"),
 ("C02","Thư viện note","Extension","Cache-first IndexedDB + sync tăng dần (updated_since, tombstone)",SON,QUANG,4,5,8,"P0","N06,C01","Cache/sync module","Mở thư viện < 200ms từ cache; xoá ở máy khác → biến mất sau sync",DT,0.5,EXT+"background/notes/sync.ts, shared/storage/"),
 ("C03","Thư viện note","UI","Màn thư viện: danh sách/chi tiết/sửa (xử lý 409)/xoá nhiều/quản lý thư mục",DUONG,SON,4,5,12,"P0","A05,C01","Library UI","Duyệt/sửa/xoá/lọc chạy với cache và server; có empty/error state",DT,0.3,EXT+"ui/features/notes/"),
 ("C04","Thư viện note","Extension","Chọn thư mục khi lưu nhanh (menu con/phím tắt mở hộp chọn) + RPC folders",SON,DUONG,5,6,6,"P0","C02,C03","Folder integration","Ghi chú vào đúng thư mục; không chọn → Inbox",NS,0,EXT+"background/, shared/messaging/"),
 ("C05","Thư viện note","QA","Test CRUD, cache, offline, xung đột version, xoá hàng loạt, IDOR",DUONG,QUANG,5,5,6,"P0","C01,C02,C03","CRUD test report","Mọi nhánh lỗi được xác minh",NS,0,"apps/api/tests/integration, docs/qa/"),
 ("R01","Tìm kiếm","AI","Tinh chỉnh hybrid retrieval (RRF, candidate_k, unaccent tiếng Việt), test cô lập dữ liệu user",VINH,QUANG,5,5,8,"P0","N05","Retrieval + test","Không rò dữ liệu chéo user; top-5 có score; p95 < 3s",DT,0.6,API+"data_access/repositories/note_chunk_repository.py"),
 ("R03","Tìm kiếm","AI","POST /search: lọc thư mục, giới hạn tần suất/user, response kèm tiêu đề/URL nguồn",VINH,QUANG,5,5,5,"P0","R01,A04","Search API","Contract đúng; trừ quota đúng; lọc thư mục pass",DT,0.6,API+"business/semantic_search/, controllers/search_controller.py"),
 ("R04","Tìm kiếm","UI","Màn tìm kiếm: nhập câu hỏi, kết quả kèm nguồn, mở trang/ghi chú gốc",SON,DUONG,5,6,6,"P0","A05,R03","Search UI","Loading/empty/error/kết quả rõ; mở được nguồn",DT,0.4,EXT+"ui/features/search/"),
 ("R05","Tìm kiếm","QA","Nghiệm thu tìm kiếm: bộ câu hỏi mẫu, phân quyền, hết quota",DUONG,VINH,6,7,5,"P0","R03,R04","Acceptance report","Đạt ngưỡng ở H03; không lộ dữ liệu",NS,0,"docs/qa/"),
 ("SUM-02","Tóm tắt","AI","Backend tóm tắt: POST /ai/summaries (preview), PUT /notes/{id}/summary, giới hạn đầu vào, quota",VINH,QUANG,5,6,6,"P0","SUM-01,A04","Summary API + test","Preview không ghi DB; chỉ lưu khi xác nhận; trừ quota theo usage",DT,0.6,API+"business/summary/, controllers/summary_controller.py"),
 ("SUM-03","Tóm tắt","UI","UI tóm tắt: nút trên thẻ note + tóm tắt vùng chọn, xem trước → Lưu/Huỷ",DUONG,SON,6,6,6,"P0","SUM-02,C03","Summary UI","Trạng thái loading/lỗi/hết quota rõ",DT,0.3,EXT+"ui/features/summary/"),
 ("SUM-04","Tóm tắt","QA","Test tóm tắt: trang dài, trang chứa prompt injection, hết quota, lỗi AI",DUONG,VINH,7,7,4,"P0","SUM-02,SUM-03","Test report","Model không làm theo chỉ dẫn trong trang mẫu",NS,0,"docs/qa/"),
 ("A08","Tóm tắt","UI","Màn Cài đặt: thông tin tài khoản, quota còn lại, đăng xuất, xoá tài khoản (xác nhận 2 bước)",DUONG,SON,6,7,4,"P0","A06,A03","Settings UI","Xoá tài khoản xoá cả cache local",NS,0,EXT+"ui/features/account/"),
 ("R02","Mở rộng","AI","Rerank top-k bằng LLM sau cờ SEARCH_RERANK_ENABLED + timeout fallback",VINH,QUANG,6,7,6,"P1","R01","Rerank adapter","Bật/tắt bằng cấu hình; timeout → giữ thứ tự RRF",NS,0,API+"business/semantic_search/semantic_search_service.py"),
 ("X01","Mở rộng","AI","Chat RAG: SSE, 5 cặp hỏi-đáp gần nhất, nguồn trích dẫn, Stop → vẫn trừ quota phần đã sinh",VINH,QUANG,6,7,12,"P1","R03,SUM-02","Chat API","Stream ổn định; Stop dừng trong < 1s",NS,0,API+"business/rag/ (+ data/models, data_access chat), controllers/rag_controller.py"),
 ("X02","Mở rộng","Extension","Chat UI: stream qua chrome.runtime Port, nút Stop, hiển thị nguồn",SON,DUONG,7,7,8,"P1","X01,R04","Chat UI","Nhận token liên tục; Stop hoạt động",NS,0,EXT+"ui/features/chat/, background/"),
 ("X03","Mở rộng","Backend","Gắn thẻ & lọc theo thẻ (bảng tags, note_tags) + UI lọc",QUANG,DUONG,6,7,8,"P1","C01","Tags API + UI","Lọc thẻ đúng, ownership đúng",NS,0,API+"business/notes/, controllers/notes_controller.py"),
 ("RET-01","Mở rộng","Backend","Job dọn dữ liệu tài khoản không hoạt động > 1 năm (NFR lưu trữ) + cảnh báo trước",QUANG,VINH,7,7,4,"P1","A06","Retention job","Chạy được theo lịch; có test",NS,0,API+"business/auth/account_service.py, controllers/account_controller.py"),
 ("H01","Hoàn thiện","Bảo mật","Rà soát extension: permission tối thiểu, CSP, nơi lưu token, không secret trong bundle",SON,QUANG,7,8,5,"P0","A03,C02","Security checklist","Không <all_urls>; không secret/token trong bundle & log",NS,0,EXT),
 ("H02","Hoàn thiện","Bảo mật","Hardening backend: rate limit, CORS đúng extension ID, HTTPS, bộ test IDOR cho mọi endpoint",QUANG,SON,7,8,8,"P0","C01,R03,A02","Hardening + test","Không lộ chi tiết lỗi nội bộ; IDOR test pass",NS,0,API+"presentation/api/, main.py"),
 ("H03","Hoàn thiện","AI","Bộ đánh giá relevance/latency (Recall@5, MRR) + ngưỡng chấp nhận",VINH,DUONG,7,8,8,"P0","R01","Evaluation report","Có số liệu và ngưỡng; dùng để chọn cấu hình chunk/RRF",NS,0,"apps/api/tests/eval/"),
 ("H04","Hoàn thiện","Triển khai","Deploy cloud (API + worker + Postgres/pgvector), secret, backup, runbook",QUANG,VINH,7,8,8,"P0","H02","Deploy + runbook","Triển khai mới từ hướng dẫn trong < 30 phút",NS,0,"infra/, docs/"),
 ("H05","Hoàn thiện","QA","Regression E2E, usability, accessibility, kiểm thử kịch bản demo",DUONG,SON,8,8,10,"P0","N07,C05,R05,SUM-04,H01,H02","Release test report","0 lỗi P0/P1 mở; checklist demo pass",NS,0,"docs/qa/"),
 ("H06","Hoàn thiện","Tích hợp","Tối ưu, sửa lỗi tích hợp extension, đóng gói zip phát hành",SON,DUONG,8,8,8,"P0","R04,H01","Extension RC","Build sạch; luồng P0 ổn định",NS,0,"apps/extension/"),
 ("H07","Hoàn thiện","Tích hợp","Release candidate server: migration, cấu hình demo, smoke test",QUANG,VINH,8,8,5,"P0","H04","Server RC","Smoke test pass trên môi trường demo",NS,0,"apps/api/, infra/"),
 ("H08","Hoàn thiện","Tài liệu","Báo cáo cuối, hướng dẫn sử dụng, kịch bản thuyết trình 10–15'",DUONG,SON,8,8,8,"P0","H05,H06,H07","Report + user guide + demo script","Tài liệu khớp sản phẩm",NS,0,"docs/"),
]

# ---------------- Backlog ----------------
ws = wb["Backlog phân công"]
tmpl = [copy.copy(ws.cell(4, c)._style) for c in range(1, 16)]
hdr_style = copy.copy(ws.cell(3, 15)._style)
for r in range(4, ws.max_row + 1):
    for c in range(1, 17):
        ws.cell(r, c).value = None
ws.cell(3, 16).value = "Thư mục code (phần sở hữu)"
ws.cell(3, 16)._style = hdr_style
ws.column_dimensions["P"].width = 36
for i, row in enumerate(B):
    r = 4 + i
    for c, v in enumerate(row, start=1):
        cell = ws.cell(r, c, v)
        cell._style = copy.copy(tmpl[min(c, 15) - 1])
last = 3 + len(B)
ws.merged_cells.ranges = {m for m in ws.merged_cells.ranges if str(m) != "A1:O1"}
ws.merge_cells("A1:P1")
ws.data_validations.dataValidation = []
dv = DataValidation(type="list", formula1=f'"{NS},{DT},{DONE},Bị chặn"', allow_blank=True)
dv.add(f"N4:N{last}")
ws.add_data_validation(dv)
dvp = DataValidation(type="decimal", operator="between", formula1="0", formula2="1")
dvp.add(f"O4:O{last}")
ws.add_data_validation(dvp)
# Conditional formatting: giữ thang màu %, đổi range
old_cf = ws.conditional_formatting
rules = [(str(cf.sqref), cf.rules) for cf in old_cf]
ws.conditional_formatting = type(old_cf)()
for sq, rl in rules:
    for rule in rl:
        ws.conditional_formatting.add(sq.replace("48", str(last)), rule)
ws.conditional_formatting.add(f"A4:P{last}", FormulaRule(formula=['$J4="P1"'],
                              font=Font(color="FF7F7F7F", italic=True)))

# ---------------- Timeline (công thức tham chiếu Backlog) ----------------
tl = wb["Timeline 8 tuần"]
t_style = [copy.copy(tl.cell(4, c)._style) for c in range(1, 14)]
for r in range(4, tl.max_row + 1):
    for c in range(1, 14):
        tl.cell(r, c).value = None
        tl.cell(r, c)._style = copy.copy(tl.cell(2, 1)._style)
blank_fill = PatternFill(fill_type=None)
for i in range(len(B)):
    r, br = 4 + i, 4 + i
    refs = {1: "A", 2: "D", 3: "E", 4: "J", 5: "I"}
    for c, col in refs.items():
        tl.cell(r, c, f"='Backlog phân công'!{col}{br}")._style = copy.copy(t_style[c - 1])
    for w in range(1, 9):
        cell = tl.cell(r, 5 + w, f"=IF(AND('Backlog phân công'!$G{br}<={w},'Backlog phân công'!$H{br}>={w}),\"■\",\"\")")
        cell._style = copy.copy(t_style[5])
        cell.fill = blank_fill
tl.conditional_formatting = type(tl.conditional_formatting)()
tl.conditional_formatting.add(f"F4:M{last}", FormulaRule(formula=['F4="■"'], fill=PatternFill("solid", fgColor="FFD9EAF7")))
tl.conditional_formatting.add(f"A4:M{last}", FormulaRule(formula=['$D4="P1"'], font=Font(color="FF7F7F7F", italic=True)))
tl["A2"] = "Ô tuần tự tính từ cột Tuần BĐ/Tuần KT của sheet Backlog — sửa ở Backlog, Timeline tự cập nhật."
tl["A2"].font = Font(italic=True, color="FF595959")

# ---------------- Tải công việc: mở rộng range ----------------
tw = wb["Tải công việc"]
for r in range(4, 8):
    for c in range(3, 13):
        v = tw.cell(r, c).value
        if isinstance(v, str):
            tw.cell(r, c).value = v.replace("$48", f"${last}")
roles = {SON: "Tech Lead / Extension core", QUANG: "Backend Lead (presentation, auth, notes, data, infra)",
         VINH: "AI/RAG Lead (semantic_search, summary, rag, quota, OpenAI)", DUONG: "UI/UX & QA Lead (ui/, test, tài liệu)"}
for r in range(4, 8):
    tw.cell(r, 2).value = roles[tw.cell(r, 1).value]
tw.cell(8, 1).value = "Tổng"
tw.cell(8, 1).font = Font(bold=True)
for c in range(3, 13):
    col = openpyxl.utils.get_column_letter(c)
    tw.cell(8, c, f"=SUM({col}4:{col}7)").font = Font(bold=True)
    tw.cell(8, c).number_format = "0"
for r in range(4, 8):
    for c in range(5, 13):
        tw.cell(r, c).number_format = "0.0"
# Tách P0/P1 theo người (cột C-D dòng 12-15)
tw["A12"] = "Giờ theo ưu tiên"
tw["A12"].font = Font(bold=True)
tw["B12"], tw["C12"], tw["D12"] = "P0", "P1", "Ghi chú"
for c in "BCD":
    tw[f"{c}12"].font = Font(bold=True)
for i, name in enumerate([SON, QUANG, VINH, DUONG]):
    r = 13 + i
    tw[f"A{r}"] = name
    tw[f"B{r}"] = f"=SUMIFS('Backlog phân công'!$I$4:$I${last},'Backlog phân công'!$E$4:$E${last},A{r},'Backlog phân công'!$J$4:$J${last},\"P0\")"
    tw[f"C{r}"] = f"=SUMIFS('Backlog phân công'!$I$4:$I${last},'Backlog phân công'!$E$4:$E${last},A{r},'Backlog phân công'!$J$4:$J${last},\"P1\")"
tw["D13"] = "P1 chỉ bắt đầu khi P0 của tuần đó xanh (cổng tuần 6)."

# ---------------- Tổng quan ----------------
ov = wb["Tổng quan"]
ov["A1"] = "QUICKASSIST — PHÂN TÍCH & KẾ HOẠCH NHÓM 4 NGƯỜI (v2 — khớp SDS_Nhomx & kiến trúc phân tầng)"
ov["B3"] = "Extension ghi chú nhanh, tóm tắt AI và tìm kiếm ngữ nghĩa; kiến trúc phân tầng theo SDS (API + worker) — phân công THEO SERVICE/THƯ MỤC."
ov["B4"] = "8 tuần — P0 = toàn bộ Must-have của SDS; P1 (Nice-to-have) chỉ làm sau cổng tuần 6 khi P0 đạt DoD."
ov["B5"] = "Google OAuth + ghi chú nhanh/hoàn tác + thư mục/Inbox + CRUD/cache + tóm tắt AI + tìm kiếm ngữ nghĩa + quota + xoá tài khoản + log."
ov["B6"] = "P1: chat RAG streaming, rerank, gắn thẻ, dọn dữ liệu 1 năm. Bỏ khỏi kế hoạch: Skim trang (không có trong SDS), self-host LLM."
ov["B7"] = "SDS_Nhomx.pdf; Kịch bản chức năng QuickAssist_1.xlsx; System Design Trade_Offs.docx; docs/architecture trong repo."
insights = [
    "Kiến trúc phân tầng đúng SDS Hình 1: presentation → business (auth, notes, quota, semantic_search, summary, rag) → data_access → data, cùng infrastructure (Google OAuth, OpenAI, Logging). Có test kiến trúc tự động trong CI.",
    "Phân công theo QUYỀN SỞ HỮU THƯ MỤC (cột P Backlog + .github/CODEOWNERS): mỗi người làm trọn module của mình từ API tới test, giảm bàn giao chéo.",
    "Đã bổ sung task SDS bắt buộc mà v1 thiếu: xoá tài khoản (A06), log (A07), tóm tắt là Must-have (SUM-01..04), màn Cài đặt (A08), cập nhật SDS (D01).",
    "Đã bỏ Skim trang (S01–S06, ~56 giờ) vì không có trong SDS; dồn thời gian cho tóm tắt và hardening.",
    "Quota chuyển sang Vinh (gắn chặt chi phí AI), Search API (R03) chuyển sang Vinh vì module search thuộc Vinh → giảm nghẽn critical path của Quang ở tuần 2–3.",
    "Base code đã có sẵn cho nhiều task (cột % hoàn thành) — việc của owner là review, hoàn thiện TODO và viết thêm test, không viết lại từ đầu.",
]
for i, t in enumerate(insights):
    ov.cell(10 + i, 2).value = t
resp = {
    SON: "Kiến trúc tổng, CI, extension core: apps/extension/src/background, content, shared; UI tìm kiếm & chat",
    QUANG: "presentation/, business/{auth,notes}, data/, data_access/, infrastructure/ (trừ openai); migrations; infra & deploy",
    VINH: "business/{semantic_search,summary,rag,quota}, infrastructure/openai, repo note_chunk/quota; đánh giá chất lượng",
    DUONG: "apps/extension/src/ui (components, notes, summary, account); test plan/E2E; báo cáo & demo",
}
for r in range(19, 23):
    name = ov.cell(r, 1).value
    ov.cell(r, 2).value = roles[name]
    ov.cell(r, 3).value = resp[name]

# ---------------- Ma trận chức năng ----------------
mt = wb["Ma trận chức năng"]
m_style = [copy.copy(mt.cell(4, c)._style) for c in range(1, 6)]
for r in range(4, mt.max_row + 1):
    for c in range(1, 6):
        mt.cell(r, c).value = None
M = [
    ("Đăng nhập Google OAuth", "SDS FR + §5.1.1", "Chi tiết", "P0", "A02, A03 — Code + PKCE, app session, refresh xoay vòng (ADR-0005)"),
    ("Ghi chú nhanh + hoàn tác 5s", "SDS + Kịch bản #1", "Chi tiết", "P0", "N01–N07 — outbox client, POST /notes idempotent, index nền"),
    ("Thư mục + Inbox mặc định", "SDS FR", "Chi tiết", "P0", "N03, C01, C04 — xoá thư mục chuyển note về Inbox"),
    ("Xem/sửa/xoá note, cache", "SDS + Kịch bản #3, #5", "Chi tiết", "P0", "C01–C05 — PATCH có version, cache-first"),
    ("Chunk + embedding", "SDS §5.1.2", "Chi tiết", "P0", "N04, N05 — job nền, READY/SKIPPED/FAILED"),
    ("Tìm kiếm ngữ nghĩa", "SDS §5.1.3 + Kịch bản #4", "Chi tiết", "P0", "R01, R03–R05 — hybrid vector + full-text (RRF)"),
    ("Tóm tắt bằng AI", "SDS §5.1.4", "Đã đặc tả (SUM-01)", "P0", "SUM-01..04 — preview rồi xác nhận mới lưu (v1 xếp P1 — lệch SDS)"),
    ("Quota AI theo token", "SDS FR", "Chi tiết", "P0", "A04 — reserve/commit/release, ledger chống trừ trùng"),
    ("Xoá tài khoản + dữ liệu", "SDS §5.1.5", "Chi tiết", "P0", "A06, A08 — MỚI (v1 không có task)"),
    ("Ghi log hoạt động/lỗi", "SDS FR", "Chi tiết", "P0", "A07 — MỚI; log JSON, request_id, không log nội dung"),
    ("Chat RAG streaming", "SDS §5.1.6 (Nice-to-have)", "Chi tiết", "P1", "X01, X02 — SSE (ADR-0009)"),
    ("Rerank", "Kịch bản #4", "Một phần", "P1", "R02 — sau cờ cấu hình, có fallback"),
    ("Gắn thẻ / lọc", "SDS (Nice-to-have)", "Một phần", "P1", "X03"),
    ("Lưu dữ liệu tối đa 1 năm", "SDS NFR", "Một phần", "P1", "RET-01"),
    ("Skim trang (Readability)", "Kịch bản #2", "Chi tiết", "Bỏ", "Không có trong SDS → loại khỏi kế hoạch; giữ làm hướng phát triển"),
    ("Tự triển khai / LLM cục bộ", "Báo cáo ý tưởng", "Định hướng", "Bỏ", "SDS: ngoài phạm vi; AI adapter đã cho phép trỏ endpoint tương thích OpenAI"),
]
for i, row in enumerate(M):
    for c, v in enumerate(row, start=1):
        mt.cell(4 + i, c, v)._style = copy.copy(m_style[c - 1])

# ---------------- Rủi ro ----------------
rk = wb["Rủi ro & quyết định"]
r_style = [copy.copy(rk.cell(4, c)._style) for c in range(1, 7)]
for r in range(4, rk.max_row + 1):
    for c in range(1, 7):
        rk.cell(r, c).value = None
R = [
    ("R-01", "Thành viên viết code lấn sang module người khác → conflict, phá ranh giới", "Cao", "Cao", "Test kiến trúc trong CI + CODEOWNERS bắt buộc duyệt; muốn dùng module khác → nhờ owner thêm hàm public", SON),
    ("R-02", "Contract API lệch giữa backend và extension", "Cao", "Trung bình", "OpenAPI là nguồn sự thật; npm run gen:api; PR đổi contract cần 2 owner duyệt", QUANG),
    ("R-03", "Google OAuth: redirect URI/extension ID khác nhau giữa máy dev", "Cao", "Cao", "Cố định extension ID bằng key trong manifest; dev-login cho test API khi chưa có Google", SON),
    ("R-04", "Chi phí/rate limit OpenAI vượt dự kiến khi test", "Trung bình", "Cao", "AI_PROVIDER=mock mặc định ở dev/CI; quota theo token; spike P03 đo chi phí", VINH),
    ("R-05", "Dữ liệu web gửi tới OpenAI (riêng tư) và prompt injection", "Cao", "Trung bình", "Chỉ gửi khi người dùng thao tác; prompt bọc dữ liệu; bộ trang thử SUM-04", VINH),
    ("R-06", "Tìm kiếm tiếng Việt kém chính xác (dấu, từ ghép)", "Trung bình", "Cao", "Hybrid + RRF; đo bằng H03; thử unaccent; tinh chỉnh chunk N04", VINH),
    ("R-07", "Xung đột migration Alembic khi 2 người cùng thêm bảng", "Trung bình", "Trung bình", "Quy ước đặt tên theo module; CI chạy alembic check; xử lý 2 head theo CONTRIBUTING.md", QUANG),
    ("R-08", "Service worker MV3 bị tắt giữa chừng làm mất ghi chú", "Cao", "Trung bình", "Outbox IndexedDB ghi ngay khi thao tác; alarm thử lại mỗi phút", SON),
    ("R-09", "Phạm vi rộng so với 4 người / 8 tuần", "Cao", "Cao", "Đã bỏ Skim; P1 chỉ mở sau cổng tuần 6; base code có sẵn", SON),
    ("R-10", "Dữ liệu cache cũ trên máy dùng chung sau khi đăng xuất", "Trung bình", "Thấp", "Đăng xuất/xoá tài khoản xoá IndexedDB", DUONG),
]
fills = {"Cao": "FFF4CCCC", "Trung bình": "FFFCE4D6", "Thấp": "FFE2EFDA"}
for i, row in enumerate(R):
    for c, v in enumerate(row, start=1):
        cell = rk.cell(4 + i, c, v)
        cell._style = copy.copy(r_style[c - 1])
        if c in (3, 4):
            cell.fill = PatternFill("solid", fgColor=fills[v])

# ---------------- Kế hoạch tuần ----------------
kt = wb["Kế hoạch tuần"]
W = [
    (1, "Chốt kiến trúc, contract, spike AI, UX", "ADR được duyệt, conventions, wireframe, CI + CODEOWNERS", "Cả nhóm chạy được base code trên máy mình", "Cả nhóm", "Không code lệch contract/kiến trúc"),
    (2, "Nền tảng: auth, quota, schema, design system", "ERD, OAuth 2 phía, quota, UI shell, đặc tả tóm tắt", "Đăng nhập Google end-to-end", f"{QUANG}/{SON}", "Chốt SUM-01"),
    (3, "Ghi chú nhanh đầu-cuối (chưa AI)", "Selection + toast + POST /notes + xoá tài khoản + log", "Lưu được note vào Inbox, hoàn tác được", f"{SON}/{QUANG}", "Vertical slice"),
    (4, "Index AI + outbox + thư viện bắt đầu", "Job index, outbox, E2E ghi chú", "N01–N07 pass", f"{VINH}/{DUONG}", "Mốc MVP-1"),
    (5, "Thư viện + tìm kiếm", "CRUD/cache/UI thư viện, hybrid search, Search API", "Tìm thấy note vừa lưu", "Cả nhóm", ""),
    (6, "Tóm tắt + nghiệm thu tìm kiếm + Cài đặt", "Summary 3 lớp, search UI, settings, R05", "Toàn bộ Must-have chạy được", f"{VINH}/{DUONG}", "Mốc MVP-2 — cổng mở P1"),
    (7, "Hardening + P1 (nếu cổng xanh)", "Security, deploy, eval; chat/tags/rerank nếu kịp", "P0 không còn lỗi P0; P1 pass hoặc cắt", f"{QUANG}/{SON}", "Khoá tính năng cuối tuần"),
    (8, "Release & thuyết trình", "Regression, RC extension + server, báo cáo, demo", "0 lỗi P0/P1; demo rehearsal pass", "Cả nhóm", "Không thêm tính năng"),
]
for i, row in enumerate(W):
    for c, v in enumerate(row, start=1):
        kt.cell(4 + i, c).value = v

# ---------------- Sheet mới: Thay đổi v2 ----------------
ch = wb.create_sheet("Thay đổi v2", 1)
ch["A1"] = "THAY ĐỔI SO VỚI KẾ HOẠCH v1 — LÝ DO"
ch["A1"].font = Font(bold=True, size=14, color="FFFFFFFF")
ch["A1"].fill = PatternFill("solid", fgColor="FF17365D")
ch.merge_cells("A1:D1")
hdr = ["Loại", "Task", "Thay đổi", "Lý do"]
for c, h in enumerate(hdr, 1):
    cell = ch.cell(3, c, h)
    cell.font = Font(bold=True, color="FFFFFFFF")
    cell.fill = PatternFill("solid", fgColor="FF2F75B5")
CH = [
    ("Thêm", "A06", "Xoá tài khoản + dữ liệu (backend)", "Must-have trong SDS §5.1.5 nhưng v1 không có task"),
    ("Thêm", "A07", "Logging có request_id, che dữ liệu nhạy cảm", "FR 'ghi log hoạt động và lỗi' chưa có owner"),
    ("Thêm", "A08", "Màn Cài đặt: quota, đăng xuất, xoá tài khoản", "Người dùng cần nơi thao tác xoá tài khoản/xem quota"),
    ("Thêm", "SUM-01..04", "Tóm tắt thành P0 (đặc tả, backend, UI, test)", "SDS xếp tóm tắt là Must-have; v1 để P1 (G01)"),
    ("Thêm", "P09, D01", "CI/CODEOWNERS; cập nhật SDS theo sds-review", "Thực thi 'phần nào ra phần đấy' bằng công cụ; SDS mâu thuẫn microservice/monolith"),
    ("Thêm", "X01–X03, RET-01", "Chat RAG, gắn thẻ, dọn dữ liệu 1 năm (P1)", "Nice-to-have/NFR trong SDS chưa có task"),
    ("Bỏ", "S01–S06", "Skim trang (Readability, /skim/*)", "Không có trong SDS; ~56 giờ; R-10 v1 đã cảnh báo phạm vi rộng"),
    ("Bỏ", "G01", "Thay bằng SUM-01", "Tóm tắt đã được SDS đặc tả"),
    ("Đổi owner", "A04 Quota", f"{QUANG} → {VINH}", "Quota gắn với chi phí AI; giảm tải critical path tuần 2–3 của Quang"),
    ("Đổi owner", "R03 Search API", f"{QUANG} → {VINH}", "Module search thuộc Vinh — 1 người làm trọn từ SQL tới API"),
    ("Đổi owner", "N02 Toast", f"{DUONG} → {SON} (Dương duyệt UI)", "Toast là hàm tiêm trong content/ — thư mục của extension core"),
    ("Đổi ưu tiên", "R02 Rerank", "P0 → P1", "SDS chỉ yêu cầu top-5 tương đồng; rerank là tối ưu"),
    ("Đổi nội dung", "P05–P07, A01–N06…", "Từ 'khởi tạo' → 'review & hoàn thiện base code'", "Base code đã có (cột % hoàn thành)"),
    ("Đổi nội dung", "H04", "Self-host/Dify → Deploy cloud", "SDS: cloud-first, self-host ngoài phạm vi"),
    ("Thêm cột", "Backlog cột P", "Thư mục code (phần sở hữu)", "Mỗi task gắn với thư mục cụ thể, khớp CODEOWNERS"),
    ("Kiến trúc", "Toàn bộ backend", "Thư mục theo tầng SDS Hình 1: presentation / business/<service> / data_access / data / infrastructure", "Code đối chiếu 1–1 với SDS; luật tầng L1–L7 kiểm tra tự động trong CI"),
    ("Đổi cách tính", "Timeline", "Ô tuần tính bằng công thức từ Backlog", "Sửa tuần ở Backlog → Timeline tự cập nhật"),
]
for i, row in enumerate(CH):
    for c, v in enumerate(row, 1):
        cell = ch.cell(4 + i, c, v)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
for col, w in zip("ABCD", (14, 18, 46, 60)):
    ch.column_dimensions[col].width = w
ch.freeze_panes = "A4"

wb.save(DST)
print("rows", len(B), "last", last)

# --- định dạng hậu kỳ: tự xuống dòng cho các ô văn bản dài ---
wb = openpyxl.load_workbook(DST)
ov = wb["Tổng quan"]
for r in list(range(3, 8)) + list(range(10, 16)) + list(range(19, 23)):
    for c in range(1, 7):
        cell = ov.cell(r, c)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ov.row_dimensions[r].height = 34
wb.save(DST)
