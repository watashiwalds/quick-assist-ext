# SUM-04 — Biên bản kiểm thử tóm tắt

> Ngày chạy: 09/10/2026 · Phần tự động chạy với AI mock; phần chống prompt injection cần **OpenAI thật** (mock chỉ lặp lại đầu vào nên không đánh giá được việc model "nghe lời" trang web).

| # | Ca | Cách kiểm | KQ |
|---|---|---|---|
| 1 | Preview không ghi DB; chỉ lưu khi bấm Lưu | API + E2E `sum-a08` | ✅ |
| 2 | Tóm tắt vùng chọn → tab Tóm tắt → Lưu thành ghi chú mới kèm tóm tắt | E2E | ✅ |
| 3 | Văn bản dài > 30 000 ký tự → 413; rỗng/2 trường/không trường → 400; note người khác → 404 | API | ✅ |
| 4 | Hết quota → 402, **không gọi AI** | API | ✅ |
| 5 | AI lỗi → 502, quota được hoàn (used = reserved = 0) | API | ✅ |
| 6 | Dùng lại Idempotency-Key → 409, không gọi AI miễn phí; user khác trùng key không ảnh hưởng | API | ✅ |
| 7 | Thẻ `</document>` / `<DOCUMENT >` giả trong trang bị vô hiệu hoá; 10 trang mẫu đều được bọc đúng | unit | ✅ |
| 8 | 3 trang injection (chỉ dẫn trực tiếp, thẻ đóng giả, "ghi chú cho AI" chèn link) **không lộ canary / không chèn link lạ** | `python -m tests.eval.summary_injection` với `AI_PROVIDER=openai` | 🔶 chờ API key |

Lệnh chạy ca 8 và cách đọc kết quả: [`docs/specs/summary-spec.md`](../../specs/summary-spec.md) §4. Dán bảng in ra vào đây khi chạy.
