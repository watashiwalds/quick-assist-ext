"""Test report không crash với mọi tổ hợp module (đặc biệt PageMatch-only)."""

from __future__ import annotations

import unittest

from run_evaluation import build_report_md
from steady_metrics import (PageMatchCase, RagCase, SearchCase, aggregate_pagematch,
                            aggregate_rag, aggregate_search)


def _manifest(modules):
    return {
        "run_id": "r", "model_label": "m", "api_base_url": "u",
        "dataset_fingerprint": "f", "git_commit": "c", "eval_code_sha256": "e",
        "date_utc": "d", "evidence_type": "smoke", "modules": modules,
        "top_k": 5, "included_pairs": 6, "excluded_rows": 0,
        "dataset_stats": {"qa_pairs": 6},
    }


class TestReport(unittest.TestCase):
    def test_every_module_combination(self):
        search = aggregate_search([
            SearchCase(qid="1", query="q", gold_note_id="a", ranked_note_ids=["a"],
                       answer_hit=True, latency_ms=10)], 5, 2)
        rag = aggregate_rag([
            RagCase(qid="1", question="q", answerable=True, gold_text="g", answer="A [1]",
                    n_sources=1, citations_ok=True, citation_count=1)])
        pm = aggregate_pagematch([
            PageMatchCase(qid="1", source_file="f", answerable=True, gold_text="gold",
                          block_texts=["xx gold yy"], verified=[True])], 5)
        combos = [
            (["search"], {"search": search}),
            (["rag"], {"rag": rag}),
            (["pagematch"], {"pagematch": pm}),
            (["search", "rag"], {"search": search, "rag": rag}),
            (["search", "rag", "pagematch"], {"search": search, "rag": rag, "pagematch": pm}),
            ([], {}),
        ]
        for modules, metrics in combos:
            with self.subTest(modules=modules):
                md = build_report_md(_manifest(modules), metrics)
                self.assertIn("# Báo cáo", md)
                self.assertIn("smoke", md)

    def test_old_metrics_shape_still_renders(self):
        old = {
            "ingest": {"files": 2, "by_status": {"READY": 2}, "create_ms_p50": 1,
                       "wait_index_ms_p50": 0, "wait_index_ms_p95": 0},
            "search": {"queries": 4, "recall_at_k": 1.0, "mrr": 1.0,
                       "answer_hit_rate": 1.0, "latency_ms_p50": 1, "latency_ms_p95": 2,
                       "random_floor": 1.0, "corpus_notes": 2},
            "rag": {"answerable": {"questions": 4, "answer_f1_gold_avg": 0.4,
                                   "citation_valid_rate": 1.0, "number_violation_rate": 0.75,
                                   "tokens_used_avg": 10, "total_ms_p50": 1},
                    "unanswerable": {"questions": 2, "refusal_rate": 0.5,
                                     "false_answer_rate": 0.5}},
            "pagematch": {"positive": {"cases": 4, "hit_rate": 1.0, "precision_avg": 1.0,
                                       "coverage_avg": 1.0},
                          "negative": {"cases": 2, "fpr": 0.5},
                          "full_page_mode_rate": 0.0, "latency_ms_p50": 1},
        }
        md = build_report_md(_manifest(["search", "rag", "pagematch"]), old)
        self.assertIn("PageMatch", md)

    def test_no_ingest_does_not_crash(self):
        md = build_report_md(_manifest(["pagematch"]), {"pagematch": {}})
        self.assertNotIn("## 2. Ingest", md)


if __name__ == "__main__":
    unittest.main()