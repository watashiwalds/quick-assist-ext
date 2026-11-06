# P08 — Ma trận truy vết yêu cầu (RTM): SDS v1.1 → ca kiểm thử

> Trạng thái tại commit cuối ngày 09/10/2026. ✅ = tự động, pass trong CI · 🔶 = cần môi trường thật (Google/OpenAI) · Đường dẫn: `api/` = `apps/api/tests/`, `ext/` = `apps/extension/`.

## Chức năng bắt buộc (SDS §3.1)
| ID | Yêu cầu | Task | Ca kiểm thử | Owner | KQ |
|---|---|---|---|---|---|
| FR-01 | Đăng nhập/đăng xuất Google OAuth | A02, A03 | `api/unit/infrastructure/test_google_oidc.py` (chữ ký, iss, aud, exp, nonce, email_verified, redirect); `api/integration/api/test_auth_google.py` (đổi code, user mới/cũ, 502, logout); `test_notes_flow::test_refresh_rotation_and_reuse_detection`; `ext/tests/pkce.test.ts`, `sync-session.test.ts` (refresh single-flight) | Quang, Sơn | ✅ · 🔶 Google thật |
| FR-02 | Bôi đen → menu / phím tắt → lưu, hoàn tác 5s | N01, N02 | `ext/e2e/n07-quick-note.spec.ts` (lưu nhanh, hoàn tác Alt+Shift+Z, textarea, chrome://); `ext/tests/quick-note.test.ts`; `ext/tests/injected.test.ts` | Sơn | ✅ |
| FR-03 | Lưu nội dung, tiêu đề, URL, tên miền, thời gian | N03 | `test_notes_flow::test_create_note_goes_to_inbox_and_is_idempotent` (domain); `n07 › lưu nhanh…` (url, title, domain) | Quang | ✅ |
| FR-04 | Xem / sửa / xoá ghi chú của mình | C01, C03 | `api/integration/api/test_notes_crud.py`; `test_notes_flow::test_optimistic_concurrency`; `ext/e2e/c05-library.spec.ts` (sửa 409, xoá 1/nhiều); `ext/tests/ui/ui.test.tsx` | Quang, Dương | ✅ |
| FR-05 | Tạo thư mục, xếp ghi chú vào thư mục | C01, C04 | `test_notes_crud::test_folder_rules`, `test_move_note_between_folders`; `c05 › quản lý thư mục…`; `n07 › chọn thư mục khi lưu nhanh` | Quang, Sơn | ✅ |
| FR-06 | Không chọn thư mục → Inbox | N03 | `test_notes_flow::test_create_note_goes_to_inbox…`; `n07 › lưu nhanh…` (folder = Inbox) | Quang | ✅ |
| FR-07 | Chia đoạn + embedding | N04, N05 | `api/unit/business/test_chunking.py` (45 ca, bất biến); `api/integration/business/test_indexing_job.py` | Vinh | ✅ |
| FR-08 | Tìm kiếm theo ngữ nghĩa | R01, R03, R04 | `api/integration/api/test_search.py`; `api/eval/test_eval_gate.py`; `ext/e2e/r05-search.spec.ts` | Vinh, Sơn | ✅ · 🔶 OpenAI |
| FR-09 | Kết quả kèm tiêu đề + URL nguồn | R03, R04 | `test_search::test_result_contract_and_scores_sorted`; `r05 › kết quả có nguồn…` | Vinh | ✅ |
| FR-10 | Tóm tắt, chỉ lưu khi xác nhận | SUM-01..04 | `api/integration/api/test_summary.py`; `test_notes_flow::test_summary_preview_then_confirm`; `ext/e2e/sum-a08.spec.ts`; `tests.eval.summary_injection` | Vinh, Dương | ✅ · 🔶 injection với OpenAI |
| FR-11 | Kiểm tra quota trước khi gọi OpenAI | A04 | `api/integration/business/test_quota.py` (race, không vượt hạn mức); `test_summary::test_quota_exhausted_is_402_and_no_ai_call`; `n07 › hết quota…`; `r05 › hết quota…` | Vinh | ✅ |
| FR-12 | Ghi nhận token đã dùng | A04 | `test_quota::test_reserve_commit_release_math`, `test_settle_is_idempotent_per_request_id`; `test_search::test_each_search_charges_quota` | Vinh | ✅ |
| FR-13 | Xoá tài khoản + toàn bộ dữ liệu | A06, A08 | `api/integration/api/test_account.py` (rollback); `test_notes_flow::test_delete_account_removes_everything`; `sum-a08 › … xoá tài khoản 2 bước` (xoá cả IndexedDB/storage) | Quang, Dương | ✅ |
| FR-14 | Ghi log hoạt động & lỗi | A07 | `api/unit/infrastructure/test_logging.py` (request_id, che token/nội dung) | Quang | ✅ |

## Phi chức năng (SDS §3.2)
| ID | Yêu cầu | Ca kiểm thử / bằng chứng | KQ |
|---|---|---|---|
| NFR-01a | Lưu ghi chú < 2 s | `scripts/smoke_test.py` (41 ms trên dev); 201 trả ngay, AI chạy nền | ✅ |
| NFR-01b | Tìm kiếm < 3 s | `test_eval_gate` (p95 < 3 s); đo 30 000 chunk: p95 ≈ 115 ms (`docs/ai/eval-report.md` §4) | ✅ · 🔶 + latency OpenAI |
| NFR-01c | Mở thư viện từ cache < 200 ms | cache-first (`handlers.ts notes/list`); `c05 › … mất mạng vẫn mở được từ cache` | ✅ |
| NFR-02 | HTTPS, OAuth PKCE, chỉ truy cập dữ liệu của mình | `test_security.py` (mọi endpoint cần token, **IDOR mọi route có id**, CORS, header bảo mật); `r05 › … không thấy dữ liệu người khác`; Caddy HTTPS (`infra/`) | ✅ |
| NFR-03 | Không lộ token/khoá/nội dung trong mã nguồn & log | `test_logging.py`; `ext/scripts/check-bundle.mjs` (CI); `.gitignore` env | ✅ |
| NFR-04 | Ghi chú lưu dù AI lỗi; không trùng | `test_indexing_job.py` (FAILED, thử lại); idempotency (`test_notes_flow`, `n07 › mất mạng…`); outbox failed store (`quick-note.test.ts`) | ✅ |
| NFR-05 | Stateless, worker riêng, cấu hình qua env | JWT stateless; worker `SKIP LOCKED`; `config.py`; `test_prod_config_guard` | ✅ |
| NFR-06 | Thông báo rõ trạng thái | `ext/tests/ui/ui.test.tsx`; `docs/ux/README.md` ma trận trạng thái; axe `h05-a11y.spec.ts` | ✅ |
| NFR-07 | Giới hạn quota/token/độ dài | 413 `NOTE_TOO_LONG`, `SUMMARY_INPUT_TOO_LONG`; 429 `RATE_LIMITED` (`test_security`); cắt 20 000 ký tự ở extension (`quick-note.test.ts`) | ✅ |
| NFR-08 | Lưu trữ tối đa 1 năm | RET-01 (P1 — chưa làm, ngoài phạm vi P0) | ⏸ |
