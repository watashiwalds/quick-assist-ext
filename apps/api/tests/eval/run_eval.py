"""H03 — bộ đánh giá relevance/latency cho tìm kiếm (Recall@5, MRR, AnswerHit@5, p50/p95).

Chạy TOÀN BỘ pipeline thật (API → worker → pgvector) trên dataset_vi.json:
    cd apps/api
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test \
        python -m tests.eval.run_eval                       # AI_PROVIDER=mock (mặc định)
    AI_PROVIDER=openai OPENAI_API_KEY=sk-... python -m tests.eval.run_eval --configs default
Kết quả in dạng bảng Markdown + ghi JSON vào tests/eval/results/<provider>.json.

Định nghĩa:
  Recall@5    = tỉ lệ truy vấn có ≥1 ghi chú liên quan trong top-5
  MRR         = trung bình 1/hạng của ghi chú liên quan đầu tiên (0 nếu không có trong top-5)
  AnswerHit@5 = tỉ lệ truy vấn có cụm 'answer' nằm TRỌN trong một chunk trả về (đo chất lượng chunking)
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
DATASET = json.loads((HERE / "dataset_vi.json").read_text(encoding="utf-8"))

# Cấu hình so sánh: chunk mặc định (1200) gần như 1 note = 1 chunk; chunk nhỏ (300) làm lộ
# khác biệt giữa chiến lược chia đoạn.
CONFIGS: dict[str, dict[str, Any]] = {
    "default": {},
    "v1-small": {"chunking_strategy": "v1", "chunk_size_chars": 300, "chunk_overlap_chars": 60},
    "v2-small": {"chunking_strategy": "v2", "chunk_size_chars": 300, "chunk_overlap_chars": 60},
    "v2-small-cand10": {"chunking_strategy": "v2", "chunk_size_chars": 300, "chunk_overlap_chars": 60,
                        "search_candidate_k": 10},
}


@dataclass
class Metrics:
    config: str
    provider: str
    queries: int
    recall_at_5: float
    mrr: float
    answer_hit_at_5: float
    by_kind: dict[str, dict[str, float]]
    chunks: int
    p50_ms: float
    p95_ms: float


def _setup_env() -> None:
    db = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db:
        raise SystemExit("Cần TEST_DATABASE_URL (PostgreSQL + pgvector)")
    os.environ.update({"DATABASE_URL": db, "APP_ENV": "test", "ENABLE_DEV_LOGIN": "true",
                       "LOG_LEVEL": "WARNING", "RATE_LIMIT_SEARCH_PER_MINUTE": "0",
                       "QUOTA_DEFAULT_TOKENS": "100000000"})
    os.environ.setdefault("AI_PROVIDER", "mock")
    os.environ.setdefault("JWT_SECRET", "eval-secret-0123456789-0123456789-abcd")


async def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    api = HERE.parents[1]
    cfg = Config(str(api / "alembic.ini"))
    cfg.set_main_option("script_location", str(api / "migrations"))
    cfg.attributes["database_url"] = os.environ["DATABASE_URL"]
    await asyncio.to_thread(command.upgrade, cfg, "head")


async def run_config(name: str, overrides: dict[str, Any]) -> Metrics:
    import httpx
    from sqlalchemy import text

    from quickassist.data.database import dispose_engine, get_engine
    from quickassist.infrastructure.config import get_settings
    from quickassist.infrastructure.jobs import drain
    from quickassist.main import create_app
    from quickassist.worker import load_job_handlers

    s = get_settings()
    overrides = {"rate_limit_search_per_minute": 0, "rate_limit_write_per_minute": 0,
                 "quota_default_tokens": 10**8} | overrides  # đo chất lượng, không đo giới hạn
    saved = {k: getattr(s, k) for k in overrides}
    for k, v in overrides.items():
        setattr(s, k, v)
    load_job_handlers()
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("TRUNCATE users, jobs, idempotency_keys RESTART IDENTITY CASCADE"))
        app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://eval/api/v1", timeout=120) as c:
            tok = (await c.post("/auth/dev-login", json={"email": "eval@x.vn"})).json()["access_token"]
            h = {"Authorization": f"Bearer {tok}"}
            ids: dict[str, str] = {}
            for n in DATASET["notes"]:
                body = {"content": n["content"], "title": n["title"]}
                if n["url"]:
                    body["url"] = n["url"]
                r = await c.post("/notes", json=body, headers=h)
                r.raise_for_status()
                ids[r.json()["id"]] = n["id"]
            while await drain(500):
                pass
            async with get_engine().connect() as conn:
                n_chunks = (await conn.execute(text("SELECT count(*) FROM note_chunks"))).scalar_one()

            hits = rr = ans = 0.0
            per_kind: dict[str, list[tuple[float, float, float]]] = {}
            lat: list[float] = []
            for q in DATASET["queries"]:
                t0 = time.perf_counter()
                r = await c.post("/search", json={"query": q["q"], "top_k": 5}, headers=h)
                lat.append((time.perf_counter() - t0) * 1000)
                r.raise_for_status()
                items = r.json()["items"]
                ranked = [ids.get(i["note_id"]) for i in items]
                rank = next((k + 1 for k, nid in enumerate(ranked) if nid in q["relevant"]), None)
                h1, r1 = (1.0, 1.0 / rank) if rank else (0.0, 0.0)
                a1 = 1.0 if any(q["answer"] in i["text"] for i in items) else 0.0
                hits, rr, ans = hits + h1, rr + r1, ans + a1
                per_kind.setdefault(q["kind"], []).append((h1, r1, a1))
        total = len(DATASET["queries"])
        by_kind = {
            k: {"n": len(v), "recall_at_5": round(sum(x[0] for x in v) / len(v), 3),
                "mrr": round(sum(x[1] for x in v) / len(v), 3),
                "answer_hit_at_5": round(sum(x[2] for x in v) / len(v), 3)}
            for k, v in per_kind.items()
        }
        lat.sort()
        return Metrics(name, s.ai_provider, total, round(hits / total, 3), round(rr / total, 3),
                       round(ans / total, 3), by_kind, n_chunks, round(statistics.median(lat), 1),
                       round(lat[max(0, int(len(lat) * 0.95) - 1)], 1))
    finally:
        for k, v in saved.items():
            setattr(s, k, v)
        await dispose_engine()


def to_markdown(results: list[Metrics]) -> str:
    rows = ["| Cấu hình | Provider | Chunks | Recall@5 | MRR | AnswerHit@5 | keyword R@5 | không dấu R@5 "
            "| paraphrase R@5 | p50 ms | p95 ms |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in results:
        k = m.by_kind
        kinds = " | ".join(str(k.get(x, {}).get("recall_at_5", "-"))
                           for x in ("keyword", "unaccent", "paraphrase"))
        rows.append(f"| {m.config} | {m.provider} | {m.chunks} | {m.recall_at_5} | {m.mrr} "
                    f"| {m.answer_hit_at_5} | {kinds} | {m.p50_ms} | {m.p95_ms} |")
    return "\n".join(rows)


async def main(config_names: list[str]) -> list[Metrics]:
    _setup_env()
    await _migrate()
    results = [await run_config(n, CONFIGS[n]) for n in config_names]
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    provider = results[0].provider if results else "none"
    payload = json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)
    (out / f"{provider}.json").write_text(payload, encoding="utf-8")
    print(to_markdown(results))
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="*", default=list(CONFIGS))
    asyncio.run(main(ap.parse_args().configs))
