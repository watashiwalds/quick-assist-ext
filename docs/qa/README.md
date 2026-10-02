# Kiểm thử (owner: UI/UX & QA)

| Loại | Vị trí | Chạy |
|---|---|---|
| Kiến trúc (luật tầng L1–L7) | `apps/api/tests/architecture/test_layers.py`, `apps/extension/tests/architecture.test.ts` | `pytest tests/architecture` · `npm test` |
| Unit — Business / Infrastructure | `apps/api/tests/unit/business/`, `apps/api/tests/unit/infrastructure/` | `pytest tests/unit` |
| Integration — API + PostgreSQL/pgvector | `apps/api/tests/integration/api/` | `TEST_DATABASE_URL=… pytest tests/integration` |
| Extension unit | `apps/extension/tests/` | `npm test` |
| E2E / thủ công theo kịch bản | `docs/qa/` (test plan, RTM, biên bản) | — |

Cần bổ sung (theo kế hoạch v2): `test-plan.md` + ma trận truy vết FR (SDS §3.1) → test case (P08); biên bản E2E N07, C05, R05, SUM-04, H05.
