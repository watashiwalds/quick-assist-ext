"""Smoke test pipeline với backend giả — kiểm tra artifact, report, recompute."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_evaluation
from run_evaluation import _diff, recompute_metrics, run_pipeline
from steady_backend import SteadyConfig, StreamResult
from steady_metrics import METRICS_VERSION


class FakeBackend:
    def __init__(self):
        self.quota_calls = 0
        self.deleted_notes = []
        self.deleted_folder = None

    def health(self):
        return {"status": "ok"}

    def login(self):
        pass

    def ready(self):
        return {"status": "ok", "db": "ok"}

    def quota(self):
        self.quota_calls += 1
        return {"used_tokens": 100 if self.quota_calls == 1 else 150}

    def find_or_create_folder(self, name):
        return {"id": "folder-1", "name": name}

    def create_note(self, content=None, title=None, idempotency_key=None,
                    folder_id=None, parts=None, document_id=None):
        self.content = content or (parts[0] if parts else "")
        self.document_id = document_id
        return 201, {"id": "note-1", "document_id": document_id,
                     "part_ids": ["note-1"], "part_count": 1,
                     "index_status": "READY", "created_at": "now",
                     "content": self.content}, 5.0

    def get_note(self, note_id):
        return {"id": note_id, "index_status": "READY", "content": self.content}, 1.0

    def list_document_parts(self, document_id):
        return [{"id": "note-1", "part_index": 0, "index_status": "READY",
                 "content": self.content}], 1.0

    def list_notes(self, folder_id=None):
        return [{"id": "note-1", "document_id": None, "content": self.content}]

    def count_notes(self, folder_id=None):
        return 1

    def search(self, query, max_sources=5, folder_id=None):
        return [{
            "domain": None, "label": "Không rõ nguồn", "source_rank": 1,
            "note_count": 1, "document_id": self.document_id, "source_type": "document",
            "notes": [{"note_id": "note-1", "document_id": self.document_id,
                       "title": "t", "url": None, "summary": None,
                       "snippet": self.content, "score": 0.9, "similarity": 0.8}],
        }], 10.0

    def chat_sse(self, question, folder_id=None):
        return StreamResult([
            ("sources", [{"index": 1, "note_id": "note-1", "chunk_id": "chunk-1",
                          "snippet": "snippet"}]),
            ("delta", {"text": "Khoảng 285 độ C [1]."}),
            ("done", {"tokens_used": 9}),
        ], first_event_ms=5.0, total_ms=40.0)

    def page_match(self, query, html=None, text=None, title=None):
        return {"mode": "segments", "warning": None, "match_ratio": 0.5,
                "total_chars": len(text or html or ""), "truncated": False,
                "items": [{"id": "b00", "occ": 0, "text": text or "", "score": 0.9,
                           "verified": True}]}, 20.0

    def bulk_delete_notes(self, note_ids):
        self.deleted_notes = note_ids
        return len(note_ids)

    def delete_folder(self, folder_id):
        self.deleted_folder = folder_id

    def close(self):
        pass


def _dataset(root: Path) -> Path:
    (root / "sources").mkdir(parents=True)
    body = "Đoạn gold có 285 độ C."
    (root / "sources" / "a.txt").write_text(body, encoding="utf-8")
    (root / "qa_pairs.csv").write_text(
        "source_file,question,gold_text,answerable\n"
        f"a.txt,Nhiệt độ?,\"{body}\",yes\n"
        "a.txt,Giá?,\"Tài liệu không đề cập.\",no\n",
        encoding="utf-8")
    return root


class TestPipeline(unittest.TestCase):
    def test_end_to_end_artifacts_and_recompute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = _dataset(root / "dataset")
            runs = root / "runs"
            fake = FakeBackend()
            cfg = SteadyConfig(
                dataset_dir=dataset, modules=["search", "rag", "pagematch"],
                model_label="fake", evidence_type="smoke", folder_mode="run",
                cleanup_notes=True)

            with mock.patch.object(run_evaluation, "RUNS_DIR", runs), \
                    mock.patch.object(run_evaluation, "BackendClient", return_value=fake):
                run_dir = run_pipeline(cfg)

            for name in ("run_manifest.json", "raw_results.jsonl", "metrics.json", "report.md"):
                self.assertTrue((run_dir / name).exists(), name)

            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["metrics_version"], METRICS_VERSION)
            self.assertEqual(manifest["folder_id"], "folder-1")
            self.assertEqual(manifest["max_sources"], 5)
            self.assertTrue(manifest["eval_code_sha256"])
            self.assertTrue(manifest["command"])

            metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["tokens_consumed"], 50)
            self.assertEqual(metrics["ingest"]["created"], 1)
            self.assertEqual(metrics["search"]["recall_at_k"], 1.0)
            self.assertEqual(metrics["rag"]["unanswerable"]["false_answer_rate"], 1.0)
            self.assertIn("smoke", (run_dir / "report.md").read_text(encoding="utf-8"))

            self.assertEqual(fake.deleted_notes, ["note-1"])
            self.assertEqual(fake.deleted_folder, "folder-1")

            recomputed = recompute_metrics(run_dir)
            self.assertEqual(_diff(metrics, recomputed), [])

    def test_fatal_keeps_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = _dataset(root / "dataset")
            runs = root / "runs"

            class Broken(FakeBackend):
                def list_notes(self, folder_id=None):
                    raise RuntimeError("boom")

            cfg = SteadyConfig(dataset_dir=dataset, modules=["search"],
                               model_label="fake", evidence_type="smoke")
            with mock.patch.object(run_evaluation, "RUNS_DIR", runs), \
                    mock.patch.object(run_evaluation, "BackendClient", return_value=Broken()):
                with self.assertRaises(RuntimeError):
                    run_pipeline(cfg)

            run_dir = next(p for p in runs.iterdir() if p.is_dir())
            metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertIn("fatal_error", metrics)
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "raw_results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()