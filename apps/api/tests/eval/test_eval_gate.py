"""H03 — cổng chất lượng: chạy bộ đánh giá trên AI mock trong CI; tụt dưới ngưỡng là đỏ.

Ngưỡng chọn từ kết quả đo ngày 08/10/2026 (docs/ai/eval-report.md), chừa biên ~5%.
Với OpenAI thật dùng `python -m tests.eval.run_eval` (không chạy trong CI vì tốn tiền).
"""

import pytest

from tests.eval.run_eval import CONFIGS, run_config

pytestmark = pytest.mark.integration


async def test_search_quality_gate(_migrated) -> None:  # type: ignore[no-untyped-def]
    m = await run_config("default", CONFIGS["default"])
    assert m.recall_at_5 >= 0.93, m
    assert m.mrr >= 0.85, m
    assert m.answer_hit_at_5 >= 0.9, m
    assert m.by_kind["unaccent"]["recall_at_5"] >= 0.9, m  # R01: gõ không dấu vẫn tìm được
    assert m.p95_ms < 3000, m  # NFR: tìm kiếm < 3 giây


async def test_v2_chunking_not_worse_than_v1(_migrated) -> None:  # type: ignore[no-untyped-def]
    v1 = await run_config("v1-small", CONFIGS["v1-small"])
    v2 = await run_config("v2-small", CONFIGS["v2-small"])
    assert v2.recall_at_5 >= v1.recall_at_5 and v2.answer_hit_at_5 >= v1.answer_hit_at_5, (v1, v2)
