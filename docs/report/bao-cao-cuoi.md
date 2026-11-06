# BÁO CÁO CUỐI KỲ — QuickAssist: Trợ lý ghi chú nhanh dựa trên AI

**Nhóm 1** — Lê Đăng Sơn · Trịnh Mạnh Quang · Mai Đức Vinh · Trần Thùy Dương
**Giảng viên hướng dẫn:** TS. Nguyễn Trọng Phúc · **Bản nháp:** 09/10/2026 (nhóm rà soát, bổ sung mục 9 trước khi nộp)

---

## 1. Giới thiệu
Sinh viên đọc nhiều tài liệu trên web nhưng ghi chú bằng cách sao chép–dán sang ứng dụng khác, khó phân loại và khó tìm lại khi không nhớ đúng từ khoá. QuickAssist là tiện ích Chrome cho phép **bôi đen → lưu trong 1 thao tác**, tổ chức theo thư mục, **tóm tắt bằng AI** và **tìm kiếm theo ý nghĩa** (kể cả gõ không dấu).

## 2. Mục tiêu và phạm vi
Phạm vi nghiệm thu là toàn bộ **Must-have** của SDS v1.1 §3.1 (14 yêu cầu chức năng) và các NFR §3.2. Nice-to-have (chat RAG, gắn thẻ, dọn dữ liệu 1 năm, rerank) không thuộc phạm vi P0. Kết quả: **14/14 FR có kiểm thử tự động pass** (ma trận `docs/qa/rtm.md`).

## 3. Kiến trúc
- **Phân tầng** (SDS Hình 1): Presentation (extension + API controller) → Business (auth, notes, quota, semantic_search, summary, rag) → Data Access (repository theo service) → Data (PostgreSQL 16 + pgvector) cùng Infrastructure (Google OAuth, AI adapter, logging, hàng đợi).
- **Monolith 2 tiến trình** (API + worker) dùng chung 1 CSDL: xoá tài khoản là 1 transaction ACID; job index ghi cùng transaction với ghi chú (outbox).
- **Extension MV3**: UI chỉ gọi background qua RPC có kiểu; background là cổng mạng duy nhất (token, outbox, cache IndexedDB); không content script thường trực.
- Luật phụ thuộc giữa các tầng được **kiểm tra tự động trong CI** (7 luật backend, 4 luật extension).
- 11 quyết định kiến trúc có ghi lại phương án đã loại và đánh đổi (`docs/adr/`).

## 4. Các luồng chính
| Luồng | Điểm nhấn kỹ thuật |
|---|---|
| Đăng nhập | Authorization Code + PKCE, server giữ client_secret, app session 15' + refresh xoay vòng, phát hiện tái sử dụng |
| Lưu nhanh | Outbox IndexedDB ghi ngay, hoàn tác 5s, Idempotency-Key, gửi lại có backoff, store "chưa gửi được" (không mất ghi chú) |
| Lập chỉ mục | Worker `SKIP LOCKED`, chia đoạn theo câu tiếng Việt, quota reserve→commit, READY/SKIPPED/FAILED, `index_rev` chống ghi đè |
| Tìm kiếm | Hybrid: vector (HNSW cosine) + từ khoá bỏ dấu (unaccent) gộp **RRF** trong 1 câu SQL, luôn lọc `user_id` |
| Tóm tắt | Xem trước không ghi DB, lưu khi xác nhận kèm kiểm version; dữ liệu bọc `<document>` chống prompt injection |
| Xoá tài khoản | 1 transaction + CASCADE; extension xoá cache, token, tuỳ chọn |

## 5. Công nghệ
Python 3.11 · FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL 16 + pgvector · OpenAI (text-embedding-3-small, gpt-4o-mini) qua adapter (có mock) · TypeScript · React · Vite + CRXJS · IndexedDB · Docker Compose · Caddy · GitHub Actions · pytest · Vitest · Playwright · axe-core.

## 6. Kiểm thử
| Bộ | Số ca | Kết quả |
|---|---|---|
| Backend (kiến trúc, unit, integration với pgvector thật, cổng chất lượng tìm kiếm) | 168 | 100% pass |
| Extension unit (outbox, đồng bộ, phiên, hàm tiêm, UI, tương phản) | 80 | 100% pass |
| E2E extension thật + backend thật (Playwright) | 28 | 100% pass |
| Accessibility (axe WCAG 2.1 AA, 5 màn) | — | 0 vi phạm |
| Smoke test môi trường RC | 11 bước | 11/11 |

Kiểm thử đã phát hiện **12 lỗi** trước khi phát hành, trong đó 1 lỗi P0: manifest dùng phím `Ctrl+Alt+N` (Chrome cấm) khiến **extension không cài được** — chỉ lộ ra khi chạy E2E trên trình duyệt thật. Danh sách đầy đủ: `docs/qa/test-plan.md` §7.

## 7. Đánh giá chất lượng tìm kiếm & chi phí AI
- Bộ đánh giá 46 câu hỏi tiếng Việt (`docs/ai/eval-report.md`): **Recall@5 0.978, MRR 0.929**; câu gõ không dấu **0.77 → 1.0** sau khi thêm unaccent + OR. Chia đoạn theo câu (v2) tốt hơn cửa sổ ký tự (v1) ở mọi chỉ số.
- Độ trễ phần CSDL: p95 ≈ 115 ms trên 30 000 đoạn (ngưỡng SDS: 3 s).
- Spike OpenAI (`docs/ai/spike-openai.md`): tiếng Việt tốn **468 token/1000 ký tự** với tokenizer embedding (cl100k) và 290 với gpt-4o-mini (o200k); 1 500 ghi chú/ngày ≈ **$0,006/ngày** embedding → rủi ro chính là rate limit, không phải chi phí.

## 8. Bảo mật & riêng tư
Checklist 22 mục (`docs/security/checklist.md`): quyền extension tối thiểu, CSP, không secret trong bundle (CI chặn), token chỉ ở background; backend kiểm tra IDOR **tự động trên mọi route có id**, rate limit 429, CORS chỉ extension, header bảo mật, log che token/nội dung, cấu hình prod không an toàn thì từ chối khởi động, container không chạy root.

## 9. Quản lý dự án *(nhóm bổ sung)*
- Kế hoạch 8 tuần, phân công theo **quyền sở hữu thư mục** (CODEOWNERS) — `docs/plan/QuickAssist_KeHoach_PhanCong_v2.xlsx`.
- Tiến độ thực tế, khó khăn, bài học: *…(mỗi thành viên 3–5 dòng)…*
- Đóng góp từng thành viên: *…*

## 10. Hạn chế & hướng phát triển
| Hạn chế | Hướng xử lý |
|---|---|
| Chưa chạy đánh giá với OpenAI thật (mock là bag-of-words) | chạy `run_eval`, `summary_injection` khi có key |
| Rate limit theo từng tiến trình | Redis khi scale ngang (ADR-0010) |
| Không sửa ghi chú khi offline | đồng bộ 2 chiều nếu có nhu cầu |
| Nice-to-have chưa làm | chat RAG streaming (X01/X02), gắn thẻ (X03), dọn dữ liệu 1 năm (RET-01), rerank (R02) |

## Phụ lục
- SDS v1.1 (`docs/specs/`), các thay đổi cần đưa vào v1.2 (`docs/specs/sds-v1.2-changes.md`)
- Kiến trúc, ERD, ADR (`docs/architecture/`, `docs/adr/`) · Contract API (`docs/api/openapi.json`)
- UX: 6 luồng + 17 màn hình thật (`docs/ux/README.md`) · Hướng dẫn sử dụng (`docs/user-guide.md`)
- Kiểm thử: kế hoạch, RTM, biên bản (`docs/qa/`) · Triển khai: runbook (`docs/deploy/runbook.md`)
