"""Test cô lập lỗi từng ca và ghi raw ngay (không cần backend)."""

from __future__ import annotations

import unittest

from steady_backend import SteadyConfig, StreamResult
from steady_dataset import DatasetBundle, QAPair
from steady_flows import (_flatten_sources, _idempotency_key, not_ready_files,
                          run_rag, run_search)


class FakeClient:
    def search(self, query, max_sources=5, folder_id=None):
        if query == "bad":
            raise RuntimeError("boom")
        return [{
            "domain": "example.com", "label": "example.com", "source_rank": 1,
            "note_count": 1,
            "notes": [{"note_id": "n1", "title": "t", "url": "https://example.com/a",
                       "summary": None, "snippet": "gold text", "score": 0.9,
                       "similarity": 0.8}],
        }], 12.0

    def chat_sse(self, question, folder_id=None):
        if question == "bad":
            raise RuntimeError("boom")
        return StreamResult([
            ("sources", [{"index": 1, "note_id": "n1", "chunk_id": "c1",
                          "snippet": "snippet"}]),
            ("delta", {"text": "Khoảng 285 độ C [1]."}),
            ("done", {"tokens_used": 7}),
        ], first_event_ms=10.0, total_ms=50.0)

    def get_note(self, note_id):
        return {"content": "Nhiệt độ nấu chảy khoảng 285 độ C."}, 3.0


def _bundle():
    pairs = [
        QAPair(qid="QA-001", source_file="a.txt", question="Nhiệt độ?",
               gold_text="gold text", answerable=True),
        QAPair(qid="QA-002", source_file="a.txt", question="bad",
               gold_text="gold text", answerable=True),
    ]
    return DatasetBundle(pairs=pairs)


class FakeLongGoldClient(FakeClient):
    """Snippet không chứa gold; full note (GET /notes/{id}) mới chứa."""

    def __init__(self, note_ids, gold_note_id, gold_text):
        self.note_ids = note_ids
        self.gold_note_id = gold_note_id
        self.gold_text = gold_text
        self.fetched: list[str] = []

    def search(self, query, max_sources=5, folder_id=None):
        return [{
            "domain": "example.com", "label": "example.com", "source_rank": 1,
            "note_count": len(self.note_ids),
            "notes": [{"note_id": nid, "title": "t", "url": None, "summary": None,
                       "snippet": "snippet khong chua dap an", "score": 0.9,
                       "similarity": 0.8} for nid in self.note_ids],
        }], 9.0

    def get_note(self, note_id):
        self.fetched.append(note_id)
        content = self.gold_text if note_id == self.gold_note_id else "noi dung khac"
        return {"content": content}, 3.0


def _one_pair():
    return DatasetBundle(pairs=[
        QAPair(qid="QA-001", source_file="a.txt", question="q",
               gold_text="doan dap an nguyen van dai hon snippet", answerable=True)])


class TestFlowsResilience(unittest.TestCase):
    def test_flatten_sources_keeps_source_then_note_order(self):
        sources = [
            {"source_rank": 1, "domain": "a.vn", "label": "A",
             "notes": [{"note_id": "n1"}, {"note_id": "n2"}]},
            {"source_rank": 2, "domain": None, "label": "Không rõ nguồn",
             "notes": [{"note_id": "n3"}]},
        ]
        notes = _flatten_sources(sources)
        self.assertEqual([n["note_id"] for n in notes], ["n1", "n2", "n3"])
        self.assertEqual([n["source_rank"] for n in notes], [1, 1, 2])
        self.assertEqual(notes[2]["source_domain"], None)

    def test_search_continues_after_one_error(self):
        emitted = []
        cases = run_search(FakeClient(), _bundle(), {"a.txt": "n1"}, 5, 5,
                           emit=lambda module, case: emitted.append((module, case.qid)))
        self.assertEqual(len(cases), 2)
        self.assertTrue(cases[0].error is None)
        self.assertTrue(cases[1].error)
        self.assertEqual(cases[0].n_sources, 1)
        self.assertEqual(cases[0].ranked_note_ids, ["n1"])
        self.assertTrue(cases[0].answer_hit)
        self.assertEqual(emitted, [("search", "QA-001"), ("search", "QA-002")])

    def test_search_answer_hit_fetches_full_note_when_snippet_misses(self):
        client = FakeLongGoldClient(["n1", "n2"], "n2",
                                    "doan dap an nguyen van dai hon snippet")
        cases = run_search(client, _one_pair(), {"a.txt": "n2"}, 5, 5)
        self.assertTrue(cases[0].answer_hit)
        self.assertIn("n2", client.fetched)

    def test_search_answer_hit_ignores_notes_beyond_top_k(self):
        client = FakeLongGoldClient(["n1", "n2", "n3", "n4", "n5", "n6"], "n6",
                                    "doan dap an nguyen van dai hon snippet")
        cases = run_search(client, _one_pair(), {"a.txt": "n6"}, 5, 5)
        self.assertEqual(cases[0].ranked_note_ids[-1], "n6")
        self.assertFalse(cases[0].answer_hit)  # n6 nằm ngoài top-5 note
        self.assertNotIn("n6", client.fetched)

    def test_rag_continues_after_one_error_and_uses_full_note_context(self):
        emitted = []
        cases = run_rag(FakeClient(), _bundle(),
                        emit=lambda module, case: emitted.append((module, case.qid)))
        self.assertEqual(len(cases), 2)
        ok, failed = cases
        self.assertIsNone(ok.error)
        self.assertEqual(ok.number_violations, [])
        self.assertTrue(ok.citations_ok)
        self.assertEqual(ok.citation_count, 1)
        self.assertFalse(ok.no_context)
        self.assertGreater(ok.context_chars, 0)
        self.assertTrue(failed.error)
        self.assertEqual(emitted, [("rag", "QA-001"), ("rag", "QA-002")])

    def test_idempotency_key_fits_backend_header_limit(self):
        # run_id dài (nhãn model dài) từng làm key 112 ký tự → backend 422.
        cfg = SteadyConfig(folder_mode="run", fresh_notes=True)
        long_scope = "20261119_045531_300530_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local"
        key = _idempotency_key(cfg, long_scope, "nội dung")
        self.assertLessEqual(len(key), 100)
        self.assertEqual(key, _idempotency_key(cfg, long_scope, "nội dung"))
        self.assertNotEqual(key, _idempotency_key(cfg, long_scope + "-2", "nội dung"))
        self.assertNotEqual(key, _idempotency_key(cfg, long_scope, "khác"))

    def test_idempotency_key_short_scope_keeps_readable_form(self):
        cfg = SteadyConfig(folder_mode="run")
        key = _idempotency_key(cfg, "run-1", "nội dung")
        self.assertEqual(key, f"steady-run-1-{key.rsplit('-', 1)[1]}")
        self.assertLessEqual(len(key), 100)

    def test_not_ready_files(self):
        from steady_metrics import IngestCase
        cases = [IngestCase(file="a", note_id="1", index_status="READY", content_chars=1,
                            truncated=False, create_ms=1, wait_index_ms=0),
                 IngestCase(file="b", note_id="2", index_status="FAILED", content_chars=1,
                            truncated=False, create_ms=1, wait_index_ms=0)]
        self.assertEqual(not_ready_files(cases), ["b"])


if __name__ == "__main__":
    unittest.main()