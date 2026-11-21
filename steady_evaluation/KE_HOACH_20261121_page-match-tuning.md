# Kế hoạch: Hiệu chỉnh PageMatch + đưa tuỳ chỉnh vào extension

> **Ngày:** 2026-11-21
> **Trạng thái:** Đã chốt hướng, chưa thực thi
> **Phạm vi:** M0 → M1 → Gate 0 → M2–M4
> **Run tham chiếu:**
> - `20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local` (gte-Qwen2)
> - `20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local` (Qwen3-Embedding)
> **Dataset fingerprint:** `ef7c82ca643482ab`
> **Eval code SHA:** `824b467cfefb0aad04036665542cdc1f3d5af9b1607fbed03d4713a2b6417688`
> **Git commit:** `6d09ed9c3565787ac3c88933cd40273970409efc`
> **Embedding:** `Qwen3-Embedding-0.6B-Q8_0.gguf` (1024 chiều, backend zero-pad lên 1536)
> **Chat:** `Ternary-Bonsai-2-9B-PQ2_0-MTP-Q8_0.gguf`, ctx 8192

---

## 1. Mục tiêu

1. Đo lại PageMatch bằng chỉ số khớp với trải nghiệm thật (UI hiển thị tất cả đoạn, auto-select đoạn `verified`).
2. Hiệu chỉnh ngưỡng PageMatch theo phân bố cosine mới của Qwen3-Embedding.
3. Nếu có lợi ích rõ, thêm 3 trường tuỳ chỉnh vào extension:
   - `min_score`
   - `top_candidates`
   - `min_confidence`
4. Không cần migration DB; không mở thêm bề mặt lạm dụng chi phí; giữ khả năng so sánh giữa các run eval.

---

## 2. Bối cảnh và hai đính chính

### 2.1. Metric PageMatch hiện tại đo sai chỗ

`steady_evaluation/steady_metrics.py:509` lấy `items[:top_k]` — tức **5 đoạn đầu theo thứ tự trang**, không phải 5 đoạn tốt nhất theo score. Trong khi đó:

- Server trả `items` theo thứ tự trang (`page_match_service.py`: `candidates = sorted(top)`).
- UI (`apps/extension/src/ui/features/page-finder/PageFinderView.tsx:278-285`) hiển thị **tất cả** items; chỉ sắp xếp lại theo confidence nếu người dùng chọn.
- UI auto-select các đoạn `verified=true` (`PageFinderView.tsx:211`).

Vì vậy `Hit@5` cũ không đo “5 kết quả tốt nhất”, cũng không đo “toàn bộ kết quả người dùng thấy”.

Thêm nữa, khi `full_page_mode_rate` đổi từ 49% xuống 18%, tập ca “segments” đổi từ 19 lên 28 ca dương tính. So sánh `0,7895` với `0,5714` trong báo cáo trước là so **hai cohort khác nhau**, không phải cùng một tập.

### 2.2. Số liệu đo lại trên cùng 38 ca dương tính

| Chỉ số | gte-Qwen2 | Qwen3-Embed | Δ thật |
|---|---:|---:|---:|
| Gold nằm trong **bất kỳ item trả về** (`hit_all`) | 30/38 = **0,7895** | 29/38 = **0,7632** | **−0,0263** |
| Gold nằm trong item **verified** (`verified_recall`) | 29/38 = **0,7632** | 26/38 = **0,6842** | **−0,0789** |
| Verified FPR (trên 11 ca âm) | 7/11 = **0,6364** | 5/11 = **0,4545** | **−0,1818** |
| FPR bất kỳ item (trên 11 ca âm) | 8/11 = 0,7273 | 6/11 = 0,5455 | −0,1818 |
| `precision_all` (fraction item liên quan) | 0,1710 | 0,1626 | −0,0084 |
| `coverage_all` | 0,8257 | 0,7964 | −0,0293 |
| Verified precision (macro) | 0,1882 | 0,1555 | −0,0327 |
| Verified precision (micro) | 0,1068 | 0,1015 | −0,0053 |
| HTML — `hit_all` | 0,9091 | 0,7727 | −0,1364 |
| TXT — `hit_all` | 0,6250 | 0,7500 | **+0,1250** |
| Full-page rate (49 ca) | 48,98% | 18,37% | −30,61 pp |
| `hit_first5_page` (metric cũ) | 25/38 = 0,6579 | 22/38 = 0,5789 | −0,0789 |
| `hit5_by_score` | 24/38 = 0,6316 | 24/38 = 0,6316 | 0 |
| `verify_unavailable` | 2 ca | 5 ca | +3 |

**Đọc đúng:**

- Qwen3 không “sụp” PageMatch. Mức giảm thật ở recall của các đoạn được auto-select là khoảng **−0,08**, không phải **−0,22**.
- Qwen3 đổi cấu trúc: TXT tốt hơn rõ, HTML kém hơn, ít full-page hơn, ít false positive hơn.
- `hit5_by_score` giống hệt nhau (0,6316) → vấn đề không nằm ở việc xếp hạng top-5 theo score.
- Verified precision của cả hai run chỉ khoảng **0,16–0,19** (macro), rất xa mục tiêu 0,85 trong `docs/ai/page-match-eval.md`. Đây là vấn đề định nghĩa “đúng”/prompt thẩm định, không phải chỉnh ngưỡng là giải quyết được.

**Hệ quả:** phải sửa metric trước khi tune. Nếu không, UI sẽ expose các nút tối ưu một chỉ số không khớp với trải nghiệm thật.

### 2.3. `top_candidates = 30–40` không khả thi với context hiện tại

Prompt verify (`apps/api/src/quickassist/business/page_match/prompts.py:38`) gửi **toàn bộ text của từng block**, không cắt. Với block tối đa 1.200 ký tự:

- 15 block × 1.200 = 18.000 ký tự ≈ **7.200–9.000 token** tiếng Việt.
- Chat model đang có `ctx-size = 8192`.
- 30–40 block = 36.000–48.000 ký tự ≈ **15.000–24.000 token** → chắc chắn tràn.

Run hiện tại đã có **5/49 ca `VERIFY_UNAVAILABLE`**. Vì vậy:

- **Giữ `top_candidates` tối đa 15** trong đợt này.
- Chỉ mở lên 20–30 sau khi làm một trong ba việc:
  - cắt mỗi block trong prompt verify (ví dụ 500–600 ký tự),
  - batch verify theo nhóm 8–10 block,
  - tăng ctx của chat model.
- Cả ba đều là việc riêng, không nằm trong “3 trường số”.

### 2.4. Hệ quả về cách hiểu `min_score`

Code hiện tại:

```python
eligible = [i for i, s in enumerate(scores) if s >= cfg.page_match_min_score]
top = sorted(eligible, key=lambda i: scores[i], reverse=True)[: cfg.page_match_top_candidates]
candidates = sorted(top)  # thứ tự trang
```

Nếu đã có ≥15 đoạn vượt `min_score`, hạ `min_score` **không thêm đoạn nào** vào vòng verify. Nó chỉ:

- tăng `eligible_chars` → dễ bật `full_page` hơn;
- thêm candidate khi số đoạn vượt ngưỡng **ít hơn** `top_candidates` (trang nhỏ).

Muốn tăng recall phải tăng `top_candidates` (đang cap 15) hoặc cải thiện embedding/block. Đây là lý do calibration phải đo **candidate recall@15** trước, không chỉ quét `min_score`.

---

## 3. Quyết định thiết kế

| Quyết định | Lý do |
|---|---|
| Lưu tuning cục bộ trong `chrome.storage.local` (prefs), không lưu DB | Không cần migration; chi phí thấp; phù hợp power user |
| 3 trường: `min_score`, `top_candidates`, `min_confidence` | Đủ để điều chỉnh recall/precision/cost mà không mở quá nhiều rủi ro |
| `top_candidates` cap **15** | Giới hạn ctx 8192 + prompt verify không cắt block |
| Server clamp + schema `ge/le` | Chống lạm dụng chi phí; client không được gửi 1000 candidate |
| Card riêng trong “Dịch vụ AI”, ngoài form BYOK | Hiện ở cả chế độ server và endpoint riêng; tránh khối “Nâng cao” hiện chỉ có ở endpoint |
| Eval gửi tuning tường minh, ghi manifest | Run reproducible; `--compare` không trộn run khác ngưỡng |
| Không expose `fallback_min_similarity`, `full_page_ratio`, block sizes, timeout | Tham số vận hành/an ninh, không phải nhu cầu người dùng |

---

## 4. Kế hoạch theo mốc

## M0 — Sửa metric & đính chính báo cáo (0,5–1 ngày)

**Không đụng backend, không cần restart.**

### Việc cần làm

1. `steady_evaluation/steady_metrics.py`
   - Refactor `_score_pagematch_case` để nhận `top_k: int | None` (`None` = toàn bộ items).
   - Thêm các chỉ số:
     - `hit_all`: gold nằm trong bất kỳ item nào.
     - `hit5_page`: metric cũ (5 item đầu theo thứ tự trang).
     - `hit5_score`: 5 item tốt nhất theo `score`.
     - `precision_all`, `coverage_all`, `span_precision_all`.
   - Thêm nhóm `verified`:
     - `verified_recall`: ca dương có ít nhất một item `verified=true` chứa gold.
     - `verified_precision`: tỉ lệ item `verified=true` thật sự chứa gold.
     - `verified_fpr`: ca âm có ít nhất một item `verified=true`.
   - Giữ nguyên key cũ (`hit`, `precision`, `coverage`...) để không vỡ `metrics.json`.
   - Tăng `metrics_version` lên `2`.

2. `steady_evaluation/run_evaluation.py`
   - Render thêm bảng “toàn bộ item / verified” trong `report.md`.
   - `MODEL_COMPARISON.md` dùng `hit_all` + `verified_recall`/`verified_fpr` làm chỉ số chính; vẫn giữ cột cũ để đối chiếu.
   - `--recompute` không cần đổi logic; chỉ cần code mới chạy được trên raw cũ.

3. `docs/ai/page-match-eval.md`
   - Ghi rõ `hit@5` cũ là “5 đoạn đầu theo thứ tự trang”, không phải top-5 theo score.
   - Bổ sung định nghĩa candidate recall, verified recall, verified precision, verified FPR.

4. `steady_evaluation/BAO_CAO_20261121_local_qwenternary-qwen3embed.md`
   - Thêm mục “Đính chính metric PageMatch” với bảng số ở §2.2.
   - Không xoá kết luận cũ; ghi rõ kết luận nào bị thay thế.

### Việc cần chạy

```bash
cd steady_evaluation
python run_evaluation.py --recompute \
  runs/20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local
python run_evaluation.py --recompute \
  runs/20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local
```

Sau đó regenerate `runs/MODEL_COMPARISON.md`.

### Definition of Done

- Bảng mới cho thấy đúng các số:
  - `hit_all`: 30/38 vs 29/38.
  - `verified_recall`: 29/38 vs 26/38.
  - `verified_fpr`: 7/11 vs 5/11.
- `--recompute` vẫn khớp hoàn toàn với metrics cũ (backward compatibility).
- Không sửa `raw_results.jsonl`.
- Báo cáo có mục đính chính, không âm thầm đổi kết luận cũ.
- `MODEL_COMPARISON.md` không trộn run khác cấu hình.

---

## M1 — Calibration thật (1–1,5 ngày)

### Preconditions

- Xác nhận backend đang chạy bằng cách nào:
  - `uvicorn` trên host, hay
  - `docker compose -f infra/docker-compose.yml`.
- Xác nhận file env thực tế API đọc (`infra/.env` hoặc `apps/api/.env`).
- Backup file env trước khi sửa; không log nội dung vì có thể chứa secret.
- Không đụng `local_infer/models-preset.ini` — file đang có thay đổi của người dùng.
- Run calibration chỉ cần API; không cần worker/ingest.

### Env tạm cho calibration

```env
PAGE_MATCH_MIN_SCORE=0
PAGE_MATCH_TOP_CANDIDATES=15
PAGE_MATCH_MIN_CONFIDENCE=0
PAGE_MATCH_FALLBACK_MIN_SIMILARITY=0
PAGE_MATCH_FULL_PAGE_RATIO=1.01
```

Lưu ý:

- `PAGE_MATCH_MIN_CONFIDENCE` và `PAGE_MATCH_FALLBACK_MIN_SIMILARITY` hiện **không có trong `infra/.env`** (chỉ có trong `.env.example`) → phải thêm tạm.
- `MIN_SCORE=0`, `MIN_CONFIDENCE=0` để response trả **toàn bộ top-15** kèm `score` và `confidence` thật.
- `FULL_PAGE_RATIO=1.01` để ép `segments`, tránh `full_text` làm phình raw results; items vẫn được trả.
- Restart API sau khi sửa env; đợi `/health/ready` trả ok.

### Chạy calibration

```bash
cd steady_evaluation
python run_evaluation.py --modules pagematch \
  --model-label local-qwenternary-qwen3embed \
  --embedding-model Qwen3-Embedding-0.6B-Q8_0 \
  --tag lat3-calib --pagematch-top-k 5
```

Không cần `--fresh-notes`/`--cleanup-notes` vì PageMatch stateless.

### Script `steady_evaluation/recalibrate_pagematch.py`

Đọc `raw_results.jsonl` của run calibration:

- Lọc `module == "pagematch"`, bỏ case lỗi.
- Sort `items` theo `score` giảm dần.
- Quét:
  - `min_score` ∈ `{0.00, 0.05, 0.10, ..., 0.50}`
  - `min_confidence` ∈ `{0.0, 0.1, ..., 0.9}`
  - `top_n` ∈ `{5, 8, 10, 12, 15}`

Với mỗi tổ hợp, tính:

- **Candidate recall@N**: gold có trong top-N theo score, **trước** verify.
- **Verified recall**: gold có trong item `verified=true` với `confidence >= ngưỡng`.
- **Verified precision**: tỉ lệ item verified thật sự chứa gold.
- **Verified FPR**: ca âm có ít nhất một item verified vượt ngưỡng.
- `hit_all`, `hit5_page`, `hit5_score`.
- `avg_items`, `avg_chars`.
- `full_page_rate` ước lượng:
  - lower bound = `matched_chars / total_chars`
  - upper bound = `matched_chars / candidate_chars`
  - run xác nhận mới là số thật.

Tách riêng HTML/TXT. Xuất bảng Markdown + CSV, chỉ ra điểm Pareto.

### Run xác nhận

Sau khi chọn điểm Pareto:

- Đặt lại `PAGE_MATCH_FULL_PAGE_RATIO=0.6`.
- Giữ các giá trị `min_score`, `top_candidates`, `min_confidence` đã chọn.
- Chạy lại `--modules pagematch --tag lat3-calib-verify`.
- Đo full-page rate, latency, `verify_unavailable`, FPR thật.

### Nếu Gate 0 đạt

Cập nhật defaults:

- `apps/api/src/quickassist/infrastructure/config.py`
- `infra/.env`
- `infra/.env.example`
- `apps/api/.env.example`

Restart API và chạy lại một run xác nhận cuối.

---

## Gate 0 — Quyết định có làm UI hay không

Chỉ chuyển sang M2–M4 nếu **tất cả** điều kiện sau đạt:

| Điều kiện | Ngưỡng | Nếu không đạt |
|---|---:|---|
| Candidate recall@15 | ≥ 0,90 | Vấn đề embedding/block; tune ngưỡng không cứu được |
| Verified recall | ≥ 0,75 | Verify/threshold không đủ tốt; sửa prompt verify trước |
| Verified FPR | ≤ 0,30 | Ngưỡng chưa lọc đủ; thử tiếp hoặc sửa verify |
| `verify_unavailable_rate` | ≤ 0,15 | Prompt quá dài; cắt block/batch/tăng ctx |

Nếu không đạt:

- **Dừng M2–M4.**
- Chuyển sang một trong các hướng:
  - cắt block trong prompt verify,
  - batch verify,
  - thêm context/heading vào block trước khi embed,
  - thử instruction prefix cho Qwen3,
  - cân nhắc embedding riêng cho PageMatch.
- Ghi rõ kết quả Gate 0 vào báo cáo.

Nếu đạt:

- Ghi lại bộ giá trị defaults + lý do.
- Tiếp tục M2–M4.

---

## M2 — Hợp đồng API (1–1,5 ngày)

### Schema

`apps/api/src/quickassist/presentation/schemas/page_match.py`:

```python
class PageMatchTuningIn(ApiModel):
    min_score: float | None = Field(default=None, ge=0.0, le=0.9)
    top_candidates: int | None = Field(default=None, ge=5, le=15)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PageMatchIn(ApiModel):
    # ... các field cũ ...
    tuning: PageMatchTuningIn | None = None
```

- `ApiModel` có `extra="forbid"` → field lạ trong `tuning` bị 422.
- Không gửi `tuning` → hành vi cũ không đổi.

### Service

`apps/api/src/quickassist/business/page_match/page_match_service.py`:

```python
@dataclass(frozen=True)
class PageMatchTuning:
    min_score: float
    top_candidates: int
    min_confidence: float


def resolve_tuning(cfg, override: PageMatchTuningIn | None) -> PageMatchTuning:
    # clamp lần nữa ở server, kể cả khi service được gọi nội bộ
    ...
```

- `match()` và `stream()` nhận `tuning: PageMatchTuning | None = None`.
- Thay 3 chỗ đọc:
  - `cfg.page_match_min_score` → `t.min_score`
  - `cfg.page_match_top_candidates` → `t.top_candidates`
  - `cfg.page_match_min_confidence` → `t.min_confidence`
- Giữ nguyên `fallback_min_similarity`, `full_page_ratio`, block sizes.
- Log metadata `page_match_done` thêm 3 giá trị tuning (không log nội dung).

### Controller

`apps/api/src/quickassist/presentation/api/v1/controllers/page_match_controller.py`:

- Truyền `body.tuning` cho cả `POST /ai/page-match` và `/stream`.

### Test

- Không gửi tuning → response giống trước.
- `min_confidence=0` → trả cả item confidence thấp.
- `top_candidates=5` → tối đa 5 item.
- Ngoài khoảng → 422.
- Field lạ trong `tuning` → 422.
- Cả JSON và SSE.

### Contract

```bash
cd apps/api
python scripts/export_openapi.py

cd ../extension
npm run gen:api:file
```

CI có check `export_openapi.py --check`; phải cập nhật `docs/api/openapi.json` và `apps/extension/src/shared/api/schema.d.ts`.

---

## M3 — Card trong extension (1,5–2 ngày)

### Vị trí

- `apps/extension/src/ui/features/account/SettingsView.tsx`
- Đặt `<PageMatchTuningCard />` **dưới** `<ProviderCard />`, trong panel “Dịch vụ AI”.
- Ngoài form BYOK → hiện ở cả chế độ “Dùng AI của server” và “Endpoint riêng”.

### Prefs

`apps/extension/src/shared/messaging/protocol.ts`:

```ts
export interface PageMatchTuningPrefs {
  minScore: number
  topCandidates: number
  minConfidence: number
}

export interface Preferences {
  // ...
  pageMatchTuning: PageMatchTuningPrefs | null
}
```

`apps/extension/src/background/prefs.ts`:

- `DEFAULTS` thêm `pageMatchTuning: null`.
- Sanitize/clamp khi đọc:
  - `minScore` ∈ [0.05, 0.9]
  - `topCandidates` ∈ [5, 15], làm tròn
  - `minConfidence` ∈ [0, 1]
  - Giá trị không hợp lệ → `null`
- `clearPrefs` đã xoá toàn bộ khi đăng xuất.

### Gửi request

`apps/extension/src/background/page-match.ts`:

- Đọc prefs trong `streamMatch`.
- Chỉ thêm `tuning` khi `pageMatchTuning != null`.
- Áp dụng cho cả `html` và `text`.

### UI

`apps/extension/src/ui/features/account/PageMatchTuningCard.tsx`:

- Card thu gọn, tiêu đề “Nâng cao — Tìm trong trang”.
- Toggle “Dùng tuỳ chỉnh trên trình duyệt này”.
- 3 ô số:
  - Độ tương đồng tối thiểu (`min_score`): 0,10–0,60.
  - Số đoạn thẩm định tối đa (`top_candidates`): 5–15.
  - Độ tin cậy tối thiểu (`min_confidence`): 0,30–0,90.
- Nút “Khôi phục mặc định máy chủ” → prefs = null.
- Ghi rõ:
  - “Chỉ áp dụng trên trình duyệt này.”
  - “Đoạn fallback do lỗi thẩm định không chịu ngưỡng tin cậy.”
  - “Hạ `min_score` không tự động thêm candidate nếu đã đủ 15 đoạn vượt ngưỡng.”

### Ý nghĩa thật của 3 trường

| Trường | Thực sự điều khiển | Chi phí | UX |
|---|---|---|---|
| `min_score` | Tập eligible + tỉ lệ full-page; **không thêm candidate** nếu đã ≥15 đoạn vượt ngưỡng | Thấp | Full-page vs segments |
| `top_candidates` | Số đoạn gửi LLM verify | Cao (token/latency) | Recall |
| `min_confidence` | Lọc sau verify | Không (đã trả chi phí verify) | Precision / số đoạn auto-select |

### Test

- Card render, validate range, lưu prefs, reset.
- Prefs sanitize với dữ liệu hỏng.
- Request body có `tuning` khi bật, không có khi tắt.
- Cả nhánh `html` và `text`.

---

## M4 — Đưa tuning vào `steady_evaluation` (0,5–1 ngày)

### Backend client

`steady_evaluation/steady_backend.py`:

```python
def page_match(self, query, html=None, text=None, title=None, tuning=None):
    payload = {"query": query, "title": title}
    if tuning:
        payload["tuning"] = tuning
    ...
```

### Flow

`steady_evaluation/steady_flows.py`:

- `run_pagematch(..., tuning=None)`.
- Truyền tuning vào `client.page_match`.

### CLI + manifest

`steady_evaluation/run_evaluation.py`:

- Cờ mới:
  - `--pagematch-min-score`
  - `--pagematch-top-candidates`
  - `--pagematch-min-confidence`
- Mặc định: dùng bộ giá trị đã calibrate (pin trong code) để run reproducible.
- Ghi manifest:

```json
"pagematch_tuning": {
  "min_score": 0.25,
  "top_candidates": 15,
  "min_confidence": 0.55
}
```

- `--recompute` không cần đổi.

### So sánh

`comparison_table()`:

- Thêm tuning vào khóa nhóm hoặc header nhóm.
- Run cũ thiếu field → `"server-default"`.
- Không so trực tiếp run khác tuning.

---

## 5. Chi phí

| Mốc | Nội dung | Chi phí |
|---|---|---:|
| M0 | Sửa metric + recompute + đính chính báo cáo | 0,5–1 ngày |
| M1 | Calibration + chọn defaults + verify run | 1–1,5 ngày |
| **M0+M1** | **Cải thiện PageMatch bằng env, chưa cần UI** | **1,5–2,5 ngày** |
| M2 | API tuning + test + OpenAPI | 1–1,5 ngày |
| M3 | Card extension + prefs + test | 1,5–2 ngày |
| M4 | Eval flags + manifest + compare | 0,5–1 ngày |
| **M2–M4** | **Tính năng chỉnh trong extension** | **3–4,5 ngày** |
| **Tổng** | | **4,5–7 ngày** |

Không cần migration DB. Nếu chỉ muốn sửa chất lượng trước, làm **M0+M1** rồi dừng; UI là phần tối ưu cho power user, không phải điều kiện để cải thiện PageMatch.

---

## 6. Rủi ro / giả định

- **49 cặp là ít** — ngưỡng chọn trên dataset này có thể overfit. Dùng giá trị tròn, kiểm tra riêng HTML/TXT, xác nhận bằng run thứ hai.
- **Verified precision thấp** ở cả hai model; tune ngưỡng chỉ dịch chuyển trên đường cong precision/recall, không sửa gốc. Nếu Gate 0 không đạt, ưu tiên sửa prompt verify/block context thay vì làm UI.
- **`top_candidates` cap 15** do ctx 8192 và prompt không cắt block. Muốn 20–30 phải cắt block/batch verify/tăng ctx — việc riêng.
- **Local prefs chỉ trên trình duyệt này**, mất khi đổi máy; copy phải nói rõ. Không đồng bộ theo tài khoản.
- **Đổi defaults ảnh hưởng mọi user**; khi đổi embedding lần nữa phải calibrate lại. Ghi tuning vào manifest để so sánh.
- **Latency p95 21,8 giây** so với mục tiêu <8 giây trong docs. Giảm `top_candidates` chỉ giảm phần verify; embed toàn bộ TXT dài vẫn là nút thắt — cần việc hiệu năng riêng.
- **`min_score` dễ gây hiểu nhầm**; nếu không giải thích, người dùng sẽ tưởng hạ ngưỡng là tăng recall trong mọi trường hợp.
- **OpenAPI/`schema.d.ts`** phải regen; CI có check `export_openapi.py --check`.
- **Env file có thể chứa secret** — backup/restore, không log nội dung.

---

## 7. Không làm trong đợt này

- Lưu tuning theo tài khoản/DB (cần migration).
- Embedding riêng cho PageMatch.
- Instruction prefix cho Qwen3 (thí nghiệm server-side riêng; có thể tác động search/RAG).
- Hybrid lexical + rerank.
- Tăng `top_candidates` lên 30–40 khi chưa xử lý prompt size.
- Expose `fallback_min_similarity`, `full_page_ratio`, `max_chars`, block sizes, timeout.
- Auto-tuning/feedback loop.

---

## 8. Mapping với 7 đề xuất ban đầu

| Đề xuất | Trong kế hoạch |
|---|---|
| 1. Hiệu chỉnh ngưỡng/candidate | M1; cap 15; sửa cách hiểu `min_score` |
| 2. Instruction prefix Qwen3 | Không làm lần này — thí nghiệm riêng |
| 3. Embedding riêng cho PageMatch | Không làm |
| 4. Block context / truncate | Không làm; cân nhắc nếu candidate recall thấp |
| 5. Hybrid + rerank | Không làm |
| 6. Chẩn đoán tách tầng | **Có — trọng tâm M1** (candidate recall vs verified recall) |
| 7. Vận hành | Manifest tuning, re-embed, khóa ngưỡng, cập nhật báo cáo |

---

## 9. Handoff / thứ tự thực thi

1. **M0 trước, chưa đụng backend.**
2. Recompute 2 run, cập nhật báo cáo + comparison.
3. Dừng lại báo kết quả M0.
4. **M1**: backup env, sửa env tạm, restart API, chạy calibration, viết script sweep, chọn Pareto, chạy verify run.
5. **Gate 0**: nếu không đạt, dừng; nếu đạt, cập nhật defaults.
6. **M2 → M3 → M4**.
7. Cuối cùng: chạy lại full eval 3 module với defaults mới, cập nhật báo cáo.

### Không đụng

- `local_infer/models-preset.ini` (đang có thay đổi của người dùng).
- `steady_evaluation/runs/**/raw_results.jsonl` (chỉ đọc).
- Hai báo cáo `BAO_CAO_20261121_*` chỉ sửa phần đính chính, không xoá lịch sử.

---

## 10. Câu hỏi còn mở

1. M0 nên **thêm mục đính chính** vào báo cáo cũ hay tạo báo cáo mới?  
   → Đề xuất: thêm mục đính chính, giữ nguyên kết luận cũ để truy vết.
2. Card tuning có cần feature flag không?  
   → Đề xuất: không; chỉ cần card thu gọn, copy rõ ràng.
3. Eval có nên luôn gửi tuning tường minh?  
   → Đề xuất: có, để run reproducible; run cũ ghi `server-default`.
4. Thời điểm restart API cho M1 cần người dùng xác nhận vì có thể ảnh hưởng phiên đang dùng.
