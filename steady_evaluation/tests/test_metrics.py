"""Test thuần (stdlib unittest) cho cách chấm — không gọi mạng."""

from __future__ import annotations

import unittest

from steady_metrics import (PageMatchCase, RagCase, SearchCase, _pct, aggregate_pagematch,
                            aggregate_rag, aggregate_search, case_from_dict, case_to_jsonl,
                            citation_indices, looks_like_refusal, normalize_text,
                            numbers_of, token_f1)


class TestNumbers(unittest.TestCase):
    def test_citation_is_not_a_number(self):
        self.assertEqual(numbers_of("khoảng 285 độ C [1]"), {"285"})
        self.assertEqual(numbers_of("A [12] và B [3,4]"), set())

    def test_question_numbers_are_numbers(self):
        self.assertIn("200", numbers_of("tủ đông 200 lít"))

    def test_vietnamese_decimals(self):
        self.assertEqual(numbers_of("1,5 tấn"), {"1.5"})
        self.assertEqual(numbers_of("3,2 tấn CO2"), {"3.2"})
        self.assertEqual(numbers_of("4 đến 12 tháng"), {"4", "12"})

    def test_thousands_and_negative(self):
        self.assertEqual(numbers_of("1.000 kg"), {"1000"})
        self.assertEqual(numbers_of("1,000,000"), {"1000000"})
        self.assertEqual(numbers_of("âm 18 độ C"), {"-18"})
        self.assertEqual(numbers_of("-18°C"), {"-18"})

    def test_chemical_formula_ignored(self):
        self.assertEqual(numbers_of("khí CO2 và H2O"), set())

    def test_token_attached_unit_does_not_become_fake_number(self):
        self.assertEqual(numbers_of("5kg"), set())

    def test_citation_indices_multi(self):
        self.assertEqual(citation_indices("x [1] y [2, 3] z [4;5]"), [1, 2, 3, 4, 5])


class TestRefusalAndTokens(unittest.TestCase):
    def test_refusal_variants(self):
        self.assertTrue(looks_like_refusal("Tài liệu không đề cập đến giá bán."))
        self.assertTrue(looks_like_refusal("Tài liệu không được đề cập đến giá bán."))
        self.assertTrue(looks_like_refusal("Chưa có thông tin về vấn đề này."))
        self.assertTrue(looks_like_refusal(
            "Mình không tìm thấy ghi chú nào liên quan tới câu hỏi này, nên không trả lời."))
        self.assertFalse(looks_like_refusal("Giá là 5 triệu. Tài liệu không đề cập thêm."))
        self.assertFalse(looks_like_refusal(""))

    def test_token_f1_is_multiset(self):
        # set-intersection sẽ cho 1.0; đa tập đúng là 2/3.
        self.assertAlmostEqual(token_f1("a a b", "a b b"), 2 / 3, places=6)

    def test_token_f1_empty(self):
        self.assertEqual(token_f1("", "gold"), 0.0)
        self.assertEqual(token_f1("gold", ""), 0.0)


class TestPercentile(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(_pct([1, 2, 3, 4], 0.5), 2)
        self.assertEqual(_pct(list(range(1, 11)), 0.5), 5)
        self.assertEqual(_pct(list(range(1, 21)), 0.95), 19)
        self.assertEqual(_pct([7], 0.95), 7)
        self.assertEqual(_pct([], 0.5), 0.0)

    def test_small_n(self):
        self.assertEqual(_pct([1, 2], 0.5), 1)
        self.assertEqual(_pct([1, 2, 3], 0.5), 2)
        self.assertEqual(_pct(list(range(1, 47)), 0.95), 44)


class TestAggregateRag(unittest.TestCase):
    def _case(self, **kwargs):
        base = dict(qid="1", question="q", answerable=True, gold_text="gold", answer="A",
                    n_sources=1)
        base.update(kwargs)
        return RagCase(**base)

    def test_uncited_counts_in_denominator(self):
        cases = [
            self._case(citations_ok=True, citation_count=1),
            self._case(qid="2", answer="B", citations_ok=None, citation_count=0),
        ]
        out = aggregate_rag(cases)["answerable"]
        self.assertEqual(out["citation_valid_rate"], 0.5)
        self.assertEqual(out["citation_presence_rate"], 0.5)
        self.assertEqual(out["no_citation_rate"], 0.5)

    def test_error_excluded_from_quality_denominator(self):
        cases = [
            self._case(answer="A", citations_ok=False, citation_count=0),
            self._case(qid="2", answer="", error="timeout"),
        ]
        out = aggregate_rag(cases)["answerable"]
        self.assertEqual(out["completed"], 1)
        self.assertEqual(out["errors"], 1)
        self.assertEqual(out["citation_valid_rate"], 0.0)
        self.assertEqual(out["error_rate"], 0.5)

    def test_error_is_not_false_answer(self):
        cases = [
            self._case(qid="1", answerable=False, answer="Không đề cập", n_sources=0),
            self._case(qid="2", answerable=False, answer="", error="timeout"),
        ]
        out = aggregate_rag(cases)["unanswerable"]
        self.assertEqual(out["completed"], 1)
        self.assertEqual(out["refusal_rate"], 1.0)
        self.assertEqual(out["false_answer_rate"], 0.0)
        self.assertEqual(out["errors"], 1)

    def test_number_violation_uses_case_field(self):
        cases = [self._case(number_violations=["999"])]
        self.assertEqual(aggregate_rag(cases)["answerable"]["number_violation_rate"], 1.0)


class TestAggregateSearch(unittest.TestCase):
    def test_errors_excluded(self):
        cases = [
            SearchCase(qid="1", query="q", gold_note_id="a", ranked_note_ids=["a"],
                       answer_hit=True, answer_hit_document=True, latency_ms=10, n_sources=1,
                       items=[{"note_id": "a"}]),
            SearchCase(qid="2", query="q", gold_note_id="a", ranked_note_ids=[],
                       answer_hit=False, latency_ms=0, error="timeout"),
        ]
        out = aggregate_search(cases, 5, 2)
        self.assertEqual(out["completed"], 1)
        self.assertEqual(out["errors"], 1)
        self.assertEqual(out["recall_at_k"], 1.0)
        self.assertEqual(out["answer_hit_rate"], 1.0)
        self.assertEqual(out["corpus_notes"], 2)
        self.assertEqual(out["sources_avg"], 1.0)
        self.assertEqual(out["notes_returned_avg"], 1.0)
        self.assertEqual(out["empty_rate"], 0.0)

    def test_gold_beyond_top_k_is_not_a_hit(self):
        # API nhóm theo nguồn có thể trả nhiều note hơn top_k; note thứ 6 không
        # được tính vào Recall@5.
        cases = [SearchCase(qid="1", query="q", gold_note_id="f",
                            ranked_note_ids=["a", "b", "c", "d", "e", "f"],
                            answer_hit=False, latency_ms=10, n_sources=2,
                            items=[{"note_id": x} for x in "abcdef"])]
        out = aggregate_search(cases, 5, 10)
        self.assertEqual(out["recall_at_k"], 0.0)
        self.assertEqual(out["mrr"], 0.0)
        self.assertEqual(out["notes_returned_avg"], 6.0)

    def test_gold_is_hit_within_top_k(self):
        cases = [SearchCase(qid="1", query="q", gold_note_id="e",
                            ranked_note_ids=["a", "b", "c", "d", "e", "f"],
                            answer_hit=True, answer_hit_document=True, latency_ms=10,
                            n_sources=2, items=[{"note_id": x} for x in "abcdef"])]
        out = aggregate_search(cases, 5, 10)
        self.assertEqual(out["recall_at_k"], 1.0)
        self.assertAlmostEqual(out["mrr"], 0.2)

    def test_document_is_one_unit_for_recall_and_mrr(self):
        # 6 part cùng document_id: tài liệu lọt top-k ngay từ part đầu.
        cases = [SearchCase(
            qid="1", query="q", gold_note_id="p3", gold_part_id="p3",
            gold_part_index=3, gold_document_id="doc-1",
            ranked_note_ids=["p0", "p1", "p2", "p3"],
            ranked_document_ids=["doc-1"], answer_hit=False,
            answer_hit_document=True, latency_ms=10, n_sources=1,
            items=[{"note_id": f"p{i}", "document_id": "doc-1"} for i in range(4)])]
        out = aggregate_search(cases, 5, 4, corpus_documents=1)
        self.assertEqual(out["recall_at_k"], 1.0)
        self.assertEqual(out["mrr"], 1.0)
        self.assertEqual(out["answer_hit_rate"], 1.0)
        self.assertEqual(out["answer_hit_note_rate"], 0.0)
        self.assertEqual(out["corpus_documents"], 1)
        self.assertEqual(out["random_floor"], 1.0)  # k ≥ số tài liệu → chặn trần

    def test_document_rank_comes_from_first_part(self):
        cases = [SearchCase(
            qid="1", query="q", gold_note_id="p0", gold_part_id="p0",
            gold_document_id="doc-1", ranked_note_ids=["x0", "p0"],
            ranked_document_ids=["doc-x", "doc-1"], answer_hit_document=True,
            latency_ms=10, items=[{"note_id": "x0"}, {"note_id": "p0"}])]
        self.assertAlmostEqual(aggregate_search(cases, 5, 2, 2)["mrr"], 0.5)

    def test_gold_part_missing_and_spans_parts_are_reported(self):
        cases = [SearchCase(
            qid="1", query="q", gold_note_id="p0", gold_part_id="p0",
            gold_part_index=-1, gold_document_id="doc-1", gold_note_ids=["p0", "p1"],
            gold_spans_parts=True, ranked_note_ids=["p0"], ranked_document_ids=["doc-1"],
            answer_hit_document=False, latency_ms=1)]
        out = aggregate_search(cases, 5, 2, 1)
        self.assertEqual(out["gold_part_missing"], 1)
        self.assertEqual(out["gold_spans_parts"], 1)
        self.assertEqual(out["recall_part_at_k"], 0.0)
        self.assertEqual(out["recall_at_k"], 1.0)

    def test_max_sources_is_respected_and_reported(self):
        cases = [SearchCase(qid="1", query="q", gold_note_id="a",
                            ranked_note_ids=["a"], ranked_document_ids=["a"],
                            n_sources=5, max_sources=5, latency_ms=1,
                            items=[{"note_id": "a"}])]
        out = aggregate_search(cases, 5, 1, 1)
        self.assertTrue(out["max_sources_ok"])
        self.assertEqual(out["max_sources_observed"], 5)
        self.assertEqual(out["sources_at_cap_rate"], 1.0)


class TestAggregatePageMatch(unittest.TestCase):
    def _case(self, **kwargs):
        base = dict(qid="1", source_file="f.txt", answerable=True, gold_text="đoạn gold")
        base.update(kwargs)
        return PageMatchCase(**base)

    def test_quality_and_fallback_are_separated(self):
        cases = [
            self._case(block_texts=["xx đoạn gold yy"], verified=[True]),
            self._case(qid="2", block_texts=["xx đoạn gold yy"], verified=[False],
                       warning="VERIFY_UNAVAILABLE"),
        ]
        out = aggregate_pagematch(cases, 5)
        self.assertEqual(out["quality"]["positive"]["cases"], 1)
        self.assertEqual(out["fallback"]["positive"]["cases"], 1)
        self.assertEqual(out["quality"]["positive"]["hit_rate"], 1.0)
        self.assertEqual(out["verify_unavailable_rate"], 0.5)

    def test_top_k_limits_blocks(self):
        blocks = ["nhiễu"] * 5 + ["đoạn gold"]
        case = self._case(block_texts=blocks, verified=[True] * 6)
        self.assertEqual(aggregate_pagematch([case], 5)["quality"]["positive"]["hit_rate"], 0.0)
        self.assertEqual(aggregate_pagematch([case], 6)["quality"]["positive"]["hit_rate"], 1.0)

    def test_full_page_case_has_no_quality_reward_for_one_big_block(self):
        case = self._case(block_texts=["đoạn gold " + "nhiễu " * 100], verified=[True],
                          mode="full_page", full_text="đoạn gold", source_text="đoạn gold")
        out = aggregate_pagematch([case], 5)
        # Full-page không nằm trong metric segments chính.
        self.assertEqual(out["quality"]["positive"]["cases"], 0)
        score = out["quality"]["full_page"]["positive"]
        self.assertEqual(score["cases"], 1)
        self.assertLess(score["span_precision_avg"], 0.1)
        self.assertEqual(score["full_page_f1_avg"], 1.0)

    def test_gold_split_across_blocks_counts_as_hit(self):
        case = self._case(block_texts=["đoạn", "gold"], verified=[True, True])
        out = aggregate_pagematch([case], 5)["quality"]["positive"]
        self.assertEqual(out["hit_rate"], 1.0)
        self.assertEqual(out["span_coverage_avg"], 1.0)

    def test_negative_fpr(self):
        cases = [self._case(answerable=False, block_texts=["x"], verified=[True])]
        out = aggregate_pagematch(cases, 5)["quality"]["negative"]
        self.assertEqual(out["fpr"], 1.0)
        self.assertEqual(out["verified_fpr"], 1.0)

    def test_overall_measures_all_items_not_page_top5(self):
        items = [{"text": f"nhiễu {i}", "score": 0.9 - i * 0.01, "verified": False}
                 for i in range(5)]
        items.append({"text": "đoạn gold", "score": 0.95, "verified": True})
        case = self._case(items=items)
        out = aggregate_pagematch([case], 5)
        # Metric cũ chỉ thấy 5 item đầu theo thứ tự trang.
        self.assertEqual(out["quality"]["positive"]["hit_rate"], 0.0)
        ov = out["overall"]["positive"]
        self.assertEqual(ov["hit_all"], 1.0)
        self.assertEqual(ov["hit_all_count"], 1)
        self.assertEqual(ov["hit5_page"], 0.0)
        self.assertEqual(ov["hit5_score"], 1.0)
        self.assertEqual(ov["verified_recall"], 1.0)
        self.assertEqual(ov["verified_precision_macro"], 1.0)
        self.assertEqual(ov["verified_precision_micro"], 1.0)
        self.assertEqual(ov["precision_all_avg"], round(1 / 6, 4))

    def test_overall_verified_fpr_includes_quality_and_fallback(self):
        cases = [
            self._case(answerable=False, items=[{"text": "x", "verified": True}]),
            self._case(qid="2", answerable=False,
                       items=[{"text": "y", "verified": True}],
                       warning="VERIFY_UNAVAILABLE"),
        ]
        out = aggregate_pagematch(cases, 5)
        self.assertEqual(out["quality"]["negative"]["verified_fpr"], 1.0)
        self.assertEqual(out["fallback"]["negative"]["verified_fpr"], 1.0)
        ov = out["overall"]["negative"]
        self.assertEqual(ov["cases"], 2)
        self.assertEqual(ov["verified_fpr_count"], 2)
        self.assertEqual(ov["verified_fpr"], 1.0)

    def test_verified_precision_macro_skips_cases_without_verified(self):
        cases = [
            self._case(qid="1", items=[
                {"text": "đoạn gold", "verified": True},
                {"text": "nhiễu", "verified": True},
            ]),
            # Ca không có item verified không được tính vào mẫu số macro.
            self._case(qid="2", items=[{"text": "nhiễu", "verified": False}]),
        ]
        ov = aggregate_pagematch(cases, 5)["overall"]["positive"]
        self.assertEqual(ov["verified_cases"], 1)
        self.assertEqual(ov["verified_items"], 2)
        self.assertEqual(ov["verified_precision_macro"], 0.5)
        self.assertEqual(ov["verified_precision_micro"], 0.5)


class TestSerialization(unittest.TestCase):
    def test_roundtrip_filters_derived_keys(self):
        case = SearchCase(qid="1", query="q", gold_note_id="a", ranked_note_ids=["a"],
                          answer_hit=True, latency_ms=1)
        data = case_to_jsonl("search", case)
        data["rank"] = 1  # khóa dẫn xuất của bản cũ
        restored = case_from_dict(SearchCase, data)
        self.assertEqual(restored.qid, "1")
        self.assertFalse(hasattr(restored, "rank"))

    def test_normalize(self):
        self.assertEqual(normalize_text("Đông lạnh  ở  -18°C"), "dong lanh o -18°c")


if __name__ == "__main__":
    unittest.main()