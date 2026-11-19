# Báo cáo triển khai P1 — Truy xuất chung source-first (backend + hợp đồng dùng chung)

> Nguồn: `docs/self_sustained/ux_improvement_plan.md` §4 Phase 1, §5.1, §6.1–6.2, §11 checklist Phase 1  
> Ngày: 17/11/2026 · Nhánh: `son-test-dev`  
> Trạng thái: **Hoàn tất phần code** — 5 commit, toàn bộ unit/architecture test + build xanh; integration/eval/e2e **cần PostgreSQL+pgvector** để chốt (máy dev không có Docker/Postgres server, xem §3.2 và §4).

## 1. Phạm vi đã làm

| # | Hạng mục | Commit | File chính |
|---|---|---|---|
| 1 | Fetch layer trả thêm `similarity` (cosine) + domain/summary của note | `69e1794` | `note_chunk_repository.py`, `notes/contracts.py`, `semantic_search_service.py`, `schemas/search.py` |
| 2 | Module grouping thuần: gom domain, ngưỡng OR, xếp hạng nguồn, top-N | `b82c1dc` | `semantic_search/grouping.py` (mới) + `test_semantic_grouping.py` (10 test) |
| 3 | Contract grouped `/search` + controller + settings + đồng bộ extension | `cf20951` | `search.py`, `search_controller.py`, `config.py`, `contracts.py` (mới), `semantic_search_service.py`, extension: `schema.d.ts`/`types.ts`/`endpoints.ts`/`protocol.ts`/`handlers.ts`/2 view |
| 4 | RAG theo hợp đồng source-first: 5 nguồn × 3 note × 1 chunk, prompt nhóm nguồn, context budget | `a56ff60` | `rag_service.py`, `rag/prompts.py`, `test_rag_prompts.py` (7 test, mới), `test_chat.py`, extension `types.ts` + chat tests |
| 5 | Eval harness đọc contract grouped + metric tỉ lệ rỗng/số nguồn | `b107677` | `tests/eval/run_eval.py` |

Ngoài phạm vi track (file `.gitignore`): `quickassist_ai_evaluation/adapters/rag_adapter.py` đã sửa cục bộ để patch `SemanticSearchService.search_sources` thay cho `retrieve` đã xoá — giữ tool eval RAG dùng được, semantics top-k cosine giữ nguyên (ngưỡng 0/0 trong fake).

## 2. Thay đổi chi tiết

### 2.1. Fetch layer (`69e1794`)

- `_HYBRID_SQL` trả thêm cột `similarity = LEAST(1.0, GREATEST(0.0, 1.0 - (c.embedding <=> :qvec)))` — cosine gốc tính cho **mọi** chunk trong fused (kể cả chunk chỉ vào nhánh từ khoá, vốn không có hạng vector), kẹp [0,1] để so ngưỡng an toàn.
- `ChunkHit`/`SearchResult` thêm `similarity`; `SearchResult` thêm `note_domain`, `note_summary`; `NoteBrief` thêm `summary_text` (từ `Note.summary_text`, không gọi AI).
- Commit này còn additive: `/search` vẫn trả phẳng, chỉ thêm field — an toàn khi bisect.

### 2.2. Grouping source-first (`grouping.py`, `b82c1dc`)

Thuần logic không I/O (unit test không cần DB), thuật toán đúng §5.1 của kế hoạch:

1. **Gom chunk theo note**: `max(similarity)`, `max(RRF)` độc lập nhau; chunk đại diện = max theo `(similarity, score)` (dùng làm snippet/chunk đưa vào prompt).
2. **Ngưỡng OR ở mức note**: đạt nếu `similarity ≥ search_min_similarity (0.5)` **hoặc** `score ≥ search_min_rrf (0.03)` — không AND. RRF một mình loại câu hỏi diễn đạt lại chỉ khớp ngữ nghĩa; cosine một mình loại khớp từ khoá chính xác.
3. **Xếp hạng nguồn**: `max(similarity của các note đạt)` → tie-break `max(RRF)` → tie-break **số note đạt** → tie-break tên domain (deterministic); nhóm "Không rõ nguồn" (`domain = None`) luôn xếp **cuối**.
4. **Top `max_sources` nguồn**, mỗi nguồn sort note theo `(-similarity, -score, note_id)` rồi cắt `notes_per_source`; `note_count` = tổng note đạt **trước** cắt (UI Phase 2 dùng cho "và N ghi chú khác").
5. `snippet` = chunk đại diện chuẩn hoá khoảng trắng, cắt 240 ký tự (khớp `SNIPPET_CHARS` của RAG).

### 2.3. Contract grouped + service + settings (`cf20951`)

- **`SearchIn`**: `top_k` → `max_sources` (số nguồn domain, `ge=1 le=20`, mặc định 5 — mở question 6 của kế hoạch: giữ select, mặc định 5).
- **`SearchOut { sources: SearchSourceOut[] }`**; `SearchSourceOut { domain, label, source_rank, note_count, notes[] }`; `SearchNoteOut { note_id, title, url, summary, snippet, score, similarity }` — đúng §6.1.
- **`SemanticSearchService.search_sources()`** = hợp đồng dùng chung Thư viện + RAG (nguyên tắc 2 của kế hoạch: không hai luồng lọc/nhóm lệch nhau). Độ sâu fetch `k = min(max_sources × notes_per_source × 3, search_candidate_k × 2)` — dư 3× vì một note có thể nhiều chunk. Log `search_grouped` (số nguồn/note) thay cho log phẳng.
- **Settings mới** (`config.py` + `infra/.env.example`): `SEARCH_MIN_SIMILARITY=0.5`, `SEARCH_MIN_RRF=0.03`, `SEARCH_MAX_SOURCES=5`, `SEARCH_NOTES_PER_SOURCE=10`, `RAG_NOTES_PER_SOURCE=3`, `CHAT_CONTEXT_MAX_CHARS=18000` — ngưỡng chỉnh qua env, không sửa code (giảm thiểu rủi ro "ngưỡng làm giảm recall" §12).
- **`contracts.py` mới trong package `semantic_search`** chứa `SearchResult` — phá import vòng `service ↔ grouping` (bị phát hiện khi chạy test; pattern theo `business/notes/contracts.py`).
- **Extension (chuyển tiếp, giữ build xanh)**: `schema.d.ts` regenerate từ `docs/api/openapi.json`; `types.ts` thêm `SearchSource`/`SearchNote` + `SearchHit` thành interface chuyển tiếp (6 field cũ UI đang dùng); `protocol.ts` đổi `topK` → `maxSources`; `handlers.ts` **phẳng hoá** grouped → flat theo hạng nguồn→note cho UI hiện tại; 2 view đổi tên arg RPC + `key={h.note_id}` (mỗi note đúng 1 entry nên key ổn định hơn `chunk_id` cũ).

### 2.4. RAG (`a56ff60`)

- `prepare()` gọi `search_sources(max_sources=CHAT_MAX_SOURCES=5, notes_per_source=cfg.rag_notes_per_source)`; phẳng `(nguồn, note)` theo hạng; **mỗi note 1 chunk tốt nhất** (tối đa 5×3=15 chunk đúng MVP scope).
- **`ChatSource`** thêm `source_index` (1..5, `source_rank` của nguồn) + `source_domain`; `index` vẫn là số trích dẫn `[n]` đánh **liên tục theo note** (1..15) — đúng §6.2, citation vẫn mở đúng ghi chú.
- **Prompt** (`prompts.py`): `<notes>` → `<sources>` gom theo `<source domain="…">` (không rõ nguồn → `<source>` không attr); mọi quy tắc chống prompt injection giữ nguyên (neutralize, câu hỏi trước dữ liệu, system dặn không làm theo chỉ dẫn trong dữ liệu). Mock client vẫn parse `<note id>` nên mock/test không đổi hành vi.
- **`clip_context()`**: trần `chat_context_max_chars` (18.000 ký tự) trên **toàn văn chunk** theo thứ hạng; note hạng cao nhất luôn giữ (chunk ≤ ~1200 ký tự không thể vượt trần một mình); vượt → bỏ cụm note hạng thấp.
- Xoá `SemanticSearchService.retrieve()` (hết caller sau khi RAG chuyển) — tránh dead code; `docs/api/openapi.json` đã đồng bộ.

### 2.5. Eval & tool ngoài (`b107677`)

- `run_eval.py`: gửi `max_sources=5`; **top-5 nghĩa mới** = 5 note đầu theo thứ hạng nguồn rồi note trong nguồn (đối xứng nhất với Recall@5 cũ là top-5 chunk); AnswerHit@5 so trên `snippet`; `Metrics` thêm `empty_rate` (tỉ lệ truy vấn trả 0 nguồn) + `sources_avg` (số nguồn trung bình) để theo dõi khi chỉnh ngưỡng — đúng yêu cầu đo §7.
- Gate chất lượng (`test_eval_gate.py`) giữ nguyên các ngưỡng cũ (recall ≥ 0.93, MRR ≥ 0.85, AnswerHit ≥ 0.9, unaccent ≥ 0.9, p95 < 3s) — sẽ tự kiểm chứng grouping+threshold trong CI có DB.

## 3. Kiểm chứng

### 3.1. Tự động (đã chạy trên máy dev)

| Lệnh | Kết quả |
|---|---|
| `ruff check src tests migrations scripts` (apps/api) | ✅ All checks passed |
| `pytest -q` (apps/api) | ✅ **221 passed**, 148 skipped (integration — skip có chủ ý khi không có DB, xem §3.2) |
| `python scripts/export_openapi.py --check` | ✅ `openapi.json khớp code` (chạy lại export sau mỗi commit đổi contract) |
| `npm run typecheck` (apps/extension) | ✅ không lỗi |
| `npm test` (vitest) | ✅ 17 files, **187/187** tests |
| `npm run build` + `npm run check:bundle` | ✅ build 293ms, bundle đạt rà soát |

Mỗi slice được commit riêng sau khi verify — cây commit luôn ở trạng thái build xanh.

Test mới thêm:

- **Unit grouping (10)**: gom domain + xếp hạng theo max similarity; ngưỡng **OR** (chỉ cosine đạt / chỉ RRF đạt / cả hai dưới ngưỡng); "Không rõ nguồn" cuối dù similarity cao nhất; tie-break RRF → số note; top-5 nguồn + `source_rank` 1..5; `note_count` tổng trước cắt (1 note nhiều chunk chỉ đếm 1 note); rỗng vào → rỗng ra; snippet chuẩn hoá + cắt 240.
- **Unit RAG prompt/clip (7)**: prompt gom `<source domain>` đúng thứ hạng, không rõ nguồn không attr; neutralize thẻ giả bên trong note vẫn hoạt động; `clip_context` giữ note hạng cao trước / luôn giữ note tốt nhất dù vượt trần / rỗng; payload `ChatSource` có `source_index`/`source_domain`.
- **Integration (viết mới/cập nhật, chạy khi có DB)**: contract grouped đúng bộ field; "Không rõ nguồn" cuối với query trùng 3 note; `max_sources=1` chỉ 1 nhóm; `search_notes_per_source=1` (monkeypatch) → `note_count=2` nhưng trả 1 note; query không liên quan → `sources == []` (empty state); isolation chéo user giữ nguyên; RAG: `rag_notes_per_source=2` → đúng 2 note/1 nguồn/1 chunk-note, `[1][2]` liên tục, prompt có đúng 1 `<source>` 2 `<note>`; prompt bọc `<sources>` + count thẻ; sources event có `source_index`/`source_domain`.
- **Extension**: test UI đổi assertion `topK` → `maxSources`; chat test literal sources thêm 2 field mới.

### 3.2. Chưa chạy được trên máy dev (cần PostgreSQL + pgvector)

Máy không có Docker và không có postgres server (`pg_isready` không phản hồi, chỉ có client) → 148 test integration + eval gate + e2e tự skip đúng thiết kế (`conftest.py`). Việc cần chạy khi có môi trường:

```bash
# 1. Integration toàn bộ (gồm test mới cho grouping/threshold/RAG grouped)
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test .venv/bin/python -m pytest -q -m integration

# 2. Eval baseline TRƯỚC khi chốt ngưỡng (§13.3 của kế hoạch)
TEST_DATABASE_URL=... python -m tests.eval.run_eval          # đo empty_rate, sources_avg, Recall@5, MRR
# nếu tỉ lệ rỗng tăng: SEARCH_MIN_SIMILARITY=0.45 chạy lại so sánh (env, không sửa code)

# 3. E2E extension (r05-search / c05-library / x02-chat)
docker compose -f infra/docker-compose.yml up --build
cd apps/extension && npm run test:e2e
```

Đối chiếu checklist Phase 1 (§11) — trạng thái hiện tại:

- [x] *Search trả tối đa 5 nguồn, mỗi nguồn tối đa 3 note (RAG) / 10 note (library response)* — cài đặt trong `search_sources()` + unit/integration test (integration chờ DB).
- [x] *Note chỉ khớp ngữ nghĩa (cosine ≥ 0.5) vẫn xuất hiện dù RRF < 0.03* — unit test `test_note_passes_threshold_with_or_not_and`.
- [x] *Note khớp cả vector + keyword (RRF ≥ 0.03) vẫn xuất hiện dù cosine < 0.5* — cùng test trên.
- [x] *Ghi chú không URL vào nhóm "Không rõ nguồn"* — unit + integration (`test_unknown_source_group_last`).
- [x] *RAG prompt có 5 nguồn, tối đa 3 note/nguồn, 1 chunk/note; không vượt context budget* — unit (`clip_context`, prompt) + integration (cap note/nguồn).
- [ ] *Eval: tỉ lệ rỗng không tăng đáng kể so với baseline* — **chưa đo** (cần DB); harness đã sẵn metric `empty_rate`/`sources_avg`.

## 4. Hạn chế & ghi chú

- **Ngưỡng 0.5/0.03 là giá trị đề xuất của kế hoạch, chưa được đo trên DB thật** — đây là rủi ro số 1 trong §12. Bắt buộc chạy eval baseline (§3.2) trước khi coi Phase 1 "chốt ngưỡng"; hạ xuống 0.45 chỉ cần đặt env, không sửa code.
- **RRF một nhánh không bao giờ đạt 0.03** (max `1/61 ≈ 0.016`): note chỉ khớp từ khoá (không vào nhánh vector) phụ thuộc hoàn toàn vào cosine để qua ngưỡng — đúng chủ ý thiết kế (giảm nhiễu kw-rơ), nhưng là hành vi cần đối chiếu khi eval recall trên thư viện nhỏ (thư viện nhỏ → mọi chunk đều có hạng ở cả 2 nhánh nên RRF nhánh kép dễ đạt ngưỡng).
- **UI chưa grouped (cố ý, chuyển tiếp)**: `handlers.ts` phẳng hoá grouped → flat; UI Thư viện/Tìm kiếm vẫn render phẳng. Phase 2 sẽ đổi 2 view dùng thẳng `SearchSource[]` (component `SourceGroup`) rồi xoá interface `SearchHit` tạm và đoạn flatten.
- **AnswerHit@5 trong eval giờ so trên `snippet` (240 ký tự) thay vì toàn văn chunk** — dataset hiện tại là note ngắn nên an toàn; nếu thêm note dài vào dataset, cân nhắc nới `SNIPPET_CHARS` hoặc đo trên trường khác.
- **`docs/api/openapi.json` + `schema.d.ts` đã đồng bộ theo từng commit** — CI check `--check` không vỡ ở bất kỳ điểm quay lại nào.
- `docs/self_sustained/ux_improvement_plan.md`, `ux_recommendation.md` vẫn là file chưa track của người dùng — không commit kèm.
- Lưu ý cho Phase 4: `ChatSource` mới có `source_index`/`source_domain` đầy đủ — component `Sources` của ChatView có thể nhóm ngay không cần đổi backend.

## 5. Đề xuất tiếp theo

1. Chạy integration + eval baseline trên môi trường có DB (3 lệnh ở §3.2), đối chiếu checklist §11; nếu `empty_rate`/recall xấu → chỉnh env ngưỡng rồi đo lại, ghi kết quả vào report bổ sung.
2. Cập nhật `docs/self_sustained/ux_recommendation.md` sang dạng checklist trạng thái khi Phase 1 nghiệm thu xong (mục 13.4 của kế hoạch).
3. Bắt đầu **Phase 2 (Thư viện)**: nhóm theo nguồn dùng `SearchSource[]` trực tiếp (bỏ flatten ở `handlers.ts`), summary-first, bulk move `notes/move` — dữ liệu Phase 1 cần đã sẵn sàng.
