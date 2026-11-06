"""P03 — Spike OpenAI: đo latency (p50/p95) và token thực tế cho embedding + tóm tắt tiếng Việt.

Cần API key thật (tốn khoảng < 0,01 USD cho một lần chạy mặc định):
    cd apps/api
    OPENAI_API_KEY=sk-... python scripts/spike_openai.py --runs 5
    # thêm --chat-model gpt-4o-mini --embedding-model text-embedding-3-small nếu muốn đổi
Kết quả: in bảng Markdown + ghi tests/eval/results/spike_openai.json → dán vào docs/ai/spike-openai.md.
Không ghi log nội dung văn bản; chỉ độ dài, token, thời gian.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quickassist.infrastructure.config import Settings  # noqa: E402
from quickassist.infrastructure.openai.openai_client import OpenAIClient  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
DATASET = json.loads((HERE / "tests/eval/dataset_vi.json").read_text(encoding="utf-8"))
# Bảng giá USD / 1 triệu token (developers.openai.com, tra cứu 08/10/2026) — sửa nếu đổi model.
PRICE = {"text-embedding-3-small": (0.02, 0.0), "gpt-4o-mini": (0.15, 0.60)}


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, max(0, round(p * len(xs)) - 1))], 1)


async def main(runs: int, chat_model: str, embedding_model: str) -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Thiếu OPENAI_API_KEY")
    s = Settings(ai_provider="openai", chat_model=chat_model, embedding_model=embedding_model)
    ai = OpenAIClient(s)
    from quickassist.business.summary.prompts import summary_messages

    texts = [n["content"] for n in DATASET["notes"]]
    emb_lat, emb_tok, emb_chars = [], 0, 0
    sum_lat, sum_in, sum_out, sum_chars = [], 0, 0, 0
    try:
        for _ in range(runs):
            for t in texts:
                t0 = time.perf_counter()
                r = await ai.embed([t])
                emb_lat.append((time.perf_counter() - t0) * 1000)
                emb_tok += r.usage.prompt_tokens
                emb_chars += len(t)
        for t in texts[: max(3, len(texts) // 2)]:
            t0 = time.perf_counter()
            r = await ai.complete(summary_messages(t), max_tokens=600)
            sum_lat.append((time.perf_counter() - t0) * 1000)
            sum_in += r.usage.prompt_tokens
            sum_out += r.usage.completion_tokens
            sum_chars += len(t)
        t0 = time.perf_counter()
        await ai.embed(texts)  # 1 request gom 20 văn bản
        batch_ms = (time.perf_counter() - t0) * 1000
    finally:
        await ai.aclose()

    pe, _ = PRICE.get(embedding_model, (0, 0))
    pi, po = PRICE.get(chat_model, (0, 0))
    result = {
        "embedding_model": embedding_model, "chat_model": chat_model, "runs": runs,
        "embed_p50_ms": pct(emb_lat, 0.5), "embed_p95_ms": pct(emb_lat, 0.95),
        "embed_batch_20_ms": round(batch_ms, 1),
        "embed_tokens_per_1000_chars": round(emb_tok / emb_chars * 1000, 1),
        "summary_p50_ms": pct(sum_lat, 0.5), "summary_p95_ms": pct(sum_lat, 0.95),
        "summary_input_tokens_per_1000_chars": round(sum_in / sum_chars * 1000, 1),
        "summary_output_tokens_avg": round(sum_out / len(sum_lat), 1),
        "usd_per_1000_notes_embedded": round(
            emb_tok / emb_chars * statistics.mean(map(len, texts)) * 1000 * pe / 1e6, 5),
        "usd_per_summary_avg": round((sum_in * pi + sum_out * po) / 1e6 / len(sum_lat), 6),
    }
    out = HERE / "tests/eval/results"
    out.mkdir(exist_ok=True)
    (out / "spike_openai.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("| Chỉ số | Giá trị |\n|---|---|")
    for k, v in result.items():
        print(f"| {k} | {v} |")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--chat-model", default="gpt-4o-mini")
    ap.add_argument("--embedding-model", default="text-embedding-3-small")
    a = ap.parse_args()
    asyncio.run(main(a.runs, a.chat_model, a.embedding_model))
