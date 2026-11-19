"""Test nạp/kiểm chứng dataset — fail-fast, cột tùy chọn, exit code."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from steady_dataset import DatasetError, load_dataset, validate_bundle

BASE_DIR = Path(__file__).resolve().parents[1]


def _write_dataset(root: Path, csv_body: str) -> Path:
    (root / "sources").mkdir(parents=True)
    (root / "sources" / "a.txt").write_text("Đoạn gold có 285 độ C và 1,5 tấn.", encoding="utf-8")
    (root / "qa_pairs.csv").write_text(csv_body, encoding="utf-8")
    return root


class TestDatasetValidation(unittest.TestCase):
    def test_valid_with_reference_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_dataset(Path(tmp), (
                "source_file,question,gold_text,answerable,reference_answer\n"
                "a.txt,Hỏi 1?,Đoạn gold,no,285 độ C\n"
                "a.txt,Hỏi 2?,Đoạn gold,no,\n"
                "a.txt,Hỏi 3?,không có trong nguồn,yes,\n"
            ))
            cfg = SimpleNamespace(dataset_dir=root, max_html_bytes=2_000_000)
            bundle = load_dataset(cfg)
            self.assertEqual(len(bundle.pairs), 2)
            self.assertEqual(bundle.excluded_rows, 1)
            self.assertTrue(bundle.issues)
            self.assertEqual(bundle.pairs[0].reference_answer, "285 độ C")

    def test_empty_question_and_gold_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_dataset(Path(tmp), (
                "source_file,question,gold_text,answerable\n"
                "a.txt,,Đoạn gold,no\n"
                "a.txt,Hỏi?,,no\n"
            ))
            cfg = SimpleNamespace(dataset_dir=root, max_html_bytes=2_000_000)
            bundle = load_dataset(cfg)
            self.assertEqual(bundle.pairs, [])
            self.assertGreaterEqual(len(bundle.issues), 2)
            with self.assertRaises(DatasetError):
                validate_bundle(bundle)

    def test_validate_bundle_allow_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_dataset(Path(tmp), (
                "source_file,question,gold_text,answerable\n"
                "a.txt,Hỏi?,Đoạn gold,no\n"
                "a.txt,,Đoạn gold,no\n"
            ))
            cfg = SimpleNamespace(dataset_dir=root, max_html_bytes=2_000_000)
            bundle = load_dataset(cfg)
            self.assertEqual(len(bundle.pairs), 1)
            with self.assertRaises(DatasetError):
                validate_bundle(bundle)  # phải raise
            validate_bundle(bundle, allow_partial=True)  # không raise

    def test_cli_validate_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_dataset(Path(tmp), (
                "source_file,question,gold_text,answerable\n"
                "a.txt,,Đoạn gold,no\n"
            ))
            proc = subprocess.run(
                [sys.executable, str(BASE_DIR / "run_evaluation.py"), "--validate",
                 "--dataset-dir", str(root)],
                cwd=BASE_DIR, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_cli_validate_clean_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_dataset(Path(tmp), (
                "source_file,question,gold_text,answerable\n"
                "a.txt,Hỏi?,Đoạn gold,no\n"
            ))
            proc = subprocess.run(
                [sys.executable, str(BASE_DIR / "run_evaluation.py"), "--validate",
                 "--dataset-dir", str(root)],
                cwd=BASE_DIR, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()