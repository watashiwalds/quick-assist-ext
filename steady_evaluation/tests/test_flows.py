"""Test cô lập lỗi từng ca và ghi raw ngay (không cần backend)."""

from __future__ import annotations

import unittest

from steady_backend import SteadyConfig, StreamResult
from steady_dataset import DatasetBundle, QAPair
from steady_flows import (IngestedDocument, _flatten_sources, _idempotency_key,
                          ingest_sources, not_ready_files, run_rag, run_search)


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

    def __init__(self, note_ids, gold_note_id, gold_text, document_id=None):
        self.note_ids = note_ids
        self.gold_note_id = gold_note_id
        self.gold_text = gold_text
        self.document_id = document_id
        self.fetched: list[str] = []

    def search(self, query, max_sources=5, folder_id=None):
        return [{
            "domain": "example.com", "label": "example.com", "source_rank": 1,
            "note_count": len(self.note_ids),
            "notes": [{"note_id": nid, "document_id": self.document_id,
                       "title": "t", "url": None, "summary": None,
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


def _legacy_doc(note_id: str, text: str = "gold text") -> IngestedDocument:
    return IngestedDocument(file="a.txt", document_id="", part_ids=[note_id],
                            part_texts=[text], note_id=note_id)


def _document(part_ids: list[str], texts: list[str],
              document_id: str = "doc-1") -> IngestedDocument:
    return IngestedDocument(file="a.txt", document_id=document_id,
                            part_ids=part_ids, part_texts=texts, note_id=part_ids[0])


class TestIngestDocument(unittest.TestCase):
    class Client:
        def __init__(self, statuses=None):
            self.created: list[dict] = []
            self.statuses = statuses or {}
            self.part_count = 1

        def create_note(self, content=None, title=None, idempotency_key=None,
                        folder_id=None, parts=None, document_id=None):
            self.created.append({"content": content, "parts": parts,
                                 "document_id": document_id, "title": title})
            texts = parts if parts is not None else [content]
            stored = [t.strip() for t in texts]
            ids = [f"p{i}" for i in range(len(texts))]
            self.part_count = len(ids)
            self.texts = stored
            note = {
                "id": ids[0], "document_id": document_id, "part_ids": ids,
                "part_count": len(ids),
                "original_chars": sum(len(t) for t in stored),
                "index_status": "READY", "content": stored[0],
            }
            return 201, note, 5.0

        def list_document_parts(self, document_id):
            return [{"id": f"p{i}", "part_index": i,
                     "content": self.texts[i],
                     "index_status": self.statuses.get(i, "READY")}
                    for i in range(self.part_count)], 1.0

        def get_note(self, note_id):
            return {"id": note_id, "index_status": "READY", "content": "x" * 10}, 1.0

    def _bundle(self, text: str):
        from pathlib import Path

        from steady_dataset import SourceFile
        src = SourceFile(name="a.txt", path=Path("a.txt"), kind="text", raw=text, plain=text)
        return DatasetBundle(sources=[src])

    def test_long_source_is_split_not_truncated(self):
        text = ("câu ngắn. " * 400)  # ~4.000 ký tự
        client = self.Client()
        cfg = SteadyConfig(split_chars=1_000)
        cases, documents = ingest_sources(client, self._bundle(text), cfg, "run-1")
        case = cases[0]
        self.assertFalse(case.truncated)
        self.assertGreater(case.part_count, 1)
        self.assertEqual(case.part_count, len(client.created[0]["parts"]))
        self.assertEqual(len(client.created[0]["document_id"]), 36)
        self.assertEqual(case.indexed_chars, case.content_chars)
        self.assertEqual(case.ready_parts, case.part_count)
        self.assertLessEqual(case.max_part_chars, 1_000)
        self.assertEqual(case.source_chars, len(text))
        self.assertEqual(documents["a.txt"].document_id, client.created[0]["document_id"])
        self.assertGreater(len(documents["a.txt"].part_texts), 1)

    def test_short_source_uses_single_part_document(self):
        client = self.Client()
        cfg = SteadyConfig()
        cases, documents = ingest_sources(client, self._bundle("ngắn"), cfg, "run-1")
        self.assertEqual(len(client.created[0]["document_id"]), 36)
        self.assertEqual(client.created[0]["parts"], ["ngắn"])
        self.assertEqual(cases[0].part_count, 1)
        self.assertEqual(cases[0].document_id, client.created[0]["document_id"])
        self.assertEqual(cases[0].indexed_chars, cases[0].content_chars)
        self.assertEqual(documents["a.txt"].part_ids, ["p0"])

    def test_truncate_long_flag_reproduces_baseline(self):
        client = self.Client()
        cfg = SteadyConfig(max_note_chars=100, truncate_long=True)
        cases, _ = ingest_sources(client, self._bundle("y" * 250), cfg, "run-1")
        self.assertTrue(cases[0].truncated)
        self.assertEqual(len(client.created[0]["content"]), 100)
        self.assertEqual(cases[0].part_count, 1)

    def test_one_failed_part_marks_document_not_ready(self):
        client = self.Client(statuses={1: "FAILED"})
        cfg = SteadyConfig(split_chars=1_000)
        text = ("câu ngắn. " * 400)
        cases, _ = ingest_sources(client, self._bundle(text), cfg, "run-1")
        self.assertEqual(cases[0].index_status, "FAILED")
        self.assertEqual(cases[0].ready_parts, cases[0].part_count - 1)
        self.assertEqual(not_ready_files(cases), ["a.txt"])


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

    def test_flatten_sources_inherits_document_id_from_source(self):
        # API nhóm note theo tài liệu và chỉ trả document_id ở cấp nguồn.
        sources = [{"source_rank": 1, "source_type": "document", "document_id": "doc-1",
                    "label": "dài", "notes": [{"note_id": "p0"}, {"note_id": "p1"}]}]
        notes = _flatten_sources(sources)
        self.assertEqual([n["document_id"] for n in notes], ["doc-1", "doc-1"])
        self.assertEqual(notes[0]["source_type"], "document")

    def test_search_continues_after_one_error(self):
        emitted = []
        cases = run_search(FakeClient(), _bundle(), {"a.txt": _legacy_doc("n1")}, 5, 5,
                           emit=lambda module, case: emitted.append((module, case.qid)))
        self.assertEqual(len(cases), 2)
        self.assertTrue(cases[0].error is None)
        self.assertTrue(cases[1].error)
        self.assertEqual(cases[0].n_sources, 1)
        self.assertEqual(cases[0].ranked_note_ids, ["n1"])
        self.assertTrue(cases[0].answer_hit)
        self.assertTrue(cases[0].answer_hit_document)
        self.assertEqual(emitted, [("search", "QA-001"), ("search", "QA-002")])

    def test_search_answer_hit_fetches_full_note_when_snippet_misses(self):
        client = FakeLongGoldClient(["n1", "n2"], "n2",
                                    "doan dap an nguyen van dai hon snippet")
        cases = run_search(client, _one_pair(), {"a.txt": _legacy_doc("n2")}, 5, 5)
        self.assertTrue(cases[0].answer_hit)
        self.assertIn("n2", client.fetched)

    def test_search_answer_hit_ignores_documents_beyond_top_k(self):
        client = FakeLongGoldClient(["n1", "n2", "n3", "n4", "n5", "n6"], "n6",
                                    "doan dap an nguyen van dai hon snippet")
        cases = run_search(client, _one_pair(), {"a.txt": _legacy_doc("n6")}, 5, 5)
        self.assertEqual(cases[0].ranked_note_ids[-1], "n6")
        self.assertFalse(cases[0].answer_hit)  # n6 nằm ngoài top-5 note
        self.assertFalse(cases[0].answer_hit_document)
        self.assertNotIn("n6", client.fetched)

    def test_search_answer_hit_checks_all_parts_of_retrieved_document(self):
        # Tài liệu 6 part lọt top-5 nhờ part 0..4; gold nằm ở part 5 (ngoài top-5 note).
        client = FakeLongGoldClient(["p0", "p1", "p2", "p3", "p4"], "p5",
                                    "doan dap an nguyen van dai hon snippet",
                                    document_id="doc-1")
        doc = _document([f"p{i}" for i in range(6)],
                        ["noi dung khac"] * 5 + ["doan dap an nguyen van dai hon snippet"])
        cases = run_search(client, _one_pair(), {"a.txt": doc}, 5, 5)
        self.assertEqual(cases[0].gold_part_index, 5)
        self.assertFalse(cases[0].answer_hit)          # top-k note không chứa gold
        self.assertTrue(cases[0].answer_hit_document)  # nhưng toàn tài liệu thì có
        self.assertIn("p5", client.fetched)

    def test_gold_part_index_detects_boundary_split(self):
        doc = _document(["p0", "p1"], ["nửa đầu của", "đoạn gold"])
        self.assertEqual(doc.gold_part_index("đoạn gold"), 1)
        self.assertEqual(doc.gold_part_index("không có trong tài liệu"), -1)

    def test_search_falls_back_to_note_rank_for_legacy_notes(self):
        client = FakeLongGoldClient(["n1", "n2"], "n1", "gold text")
        cases = run_search(client, _one_pair(), {"a.txt": _legacy_doc("n1")}, 5, 5)
        self.assertEqual(cases[0].gold_document_id, "")
        self.assertEqual(cases[0].ranked_document_ids, ["n1", "n2"])

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