# Kiểm thử (owner: UI/UX & QA)

| Loại | Vị trí | Chạy |
|---|---|---|
| Kiến trúc (luật tầng L1–L7) | `apps/api/tests/architecture/test_layers.py`, `apps/extension/tests/architecture.test.ts` | `pytest tests/architecture` · `npm test` |
| Unit — Business / Infrastructure | `apps/api/tests/unit/business/`, `apps/api/tests/unit/infrastructure/` | `pytest tests/unit` |
| Integration — API + PostgreSQL/pgvector | `apps/api/tests/integration/api/` | `TEST_DATABASE_URL=… pytest tests/integration` |
| Extension unit | `apps/extension/tests/` | `npm test` |
| E2E / thủ công theo kịch bản | `docs/qa/` (test plan, RTM, biên bản) | — |

| E2E extension thật (Playwright) | `apps/extension/e2e/` | `npm run test:e2e` (cần backend — xem e2e/README.md) |
| Đánh giá tìm kiếm | `apps/api/tests/eval/` | `python -m tests.eval.run_eval` |

Tài liệu:
- [`test-plan.md`](test-plan.md) — chiến lược, môi trường, tiêu chí vào/ra, phân loại lỗi, lỗi đã phát hiện (P08)
- [`rtm.md`](rtm.md) — ma trận truy vết FR/NFR (SDS §3) → ca kiểm thử (P08)
- `reports/` — biên bản: [N07](reports/N07.md) · [C05](reports/C05.md) · [R05](reports/R05.md) · [SUM-04](reports/SUM-04.md) · [H05](reports/H05.md)
