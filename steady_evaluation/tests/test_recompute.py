"""Test tái lập: raw_results.jsonl → metrics.json phải khớp (trừ quota/token)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_evaluation import _diff, recompute_metrics
from steady_metrics import (METRICS_VERSION, PageMatchCase, RagCase, SearchCase,
                            aggregate_pagematch, aggregate_rag, aggregate_search,
                            case_to_jsonl)


class TestRecompute(unittest.TestCase):
    def test_roundtrip_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            manifest = {"run_id": "r", "top_k": 5, "pagematch_top_k": 5,
                        "corpus_notes": 1, "metrics_version": METRICS_VERSION}
            (run_dir / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            search_cases = [
                SearchCase(qid="1", query="q", gold_note_id="a", ranked_note_ids=["a"],
                           answer_hit=True, latency_ms=10),
                SearchCase(qid="2", query="q", gold_note_id="b", ranked_note_ids=["a", "b"],
                           answer_hit=False, latency_ms=20),
            ]
            rag_cases = [
                RagCase(qid="1", question="q", answerable=True, gold_text="g",
                        answer="A [1]", n_sources=1, citations_ok=True, citation_count=1),
                RagCase(qid="2", question="q", answerable=False, gold_text="g",
                        answer="Không đề cập", n_sources=0),
            ]
            pm_cases = [
                PageMatchCase(qid="1", source_file="f", answerable=True, gold_text="gold",
                              block_texts=["xx gold yy"], verified=[True]),
                PageMatchCase(qid="2", source_file="f", answerable=False, gold_text="no",
                              block_texts=[], verified=[]),
            ]
            lines = []
            for module, cases in (("search", search_cases), ("rag", rag_cases),
                                  ("pagematch", pm_cases)):
                lines += [json.dumps(case_to_jsonl(module, c), ensure_ascii=False)
                          for c in cases]
            (run_dir / "raw_results.jsonl").write_text("\n".join(lines) + "\n",
                                                       encoding="utf-8")

            expected = {
                "run_id": "r", "metrics_version": METRICS_VERSION, "manifest": manifest,
                "search": aggregate_search(search_cases, 5, 1),
                "rag": aggregate_rag(rag_cases),
                "pagematch": aggregate_pagematch(pm_cases, 5),
            }
            (run_dir / "metrics.json").write_text(
                json.dumps(expected, ensure_ascii=False), encoding="utf-8")

            actual = recompute_metrics(run_dir)
            self.assertEqual(_diff(expected, actual), [])

    def test_old_raw_is_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "run_manifest.json").write_text(
                json.dumps({"run_id": "r", "top_k": 5}), encoding="utf-8")
            old = {"module": "search", "qid": "1", "query": "q", "gold_note_id": "a",
                   "ranked_note_ids": ["a"], "answer_hit": True, "latency_ms": 1,
                   "rank": 1, "rr": 1.0}
            (run_dir / "raw_results.jsonl").write_text(json.dumps(old) + "\n",
                                                       encoding="utf-8")
            out = recompute_metrics(run_dir)
            self.assertEqual(out["metrics_version"], METRICS_VERSION)
            self.assertEqual(out["search"]["recall_at_k"], 1.0)


if __name__ == "__main__":
    unittest.main()