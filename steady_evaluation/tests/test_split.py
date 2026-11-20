"""Test hàm chia tài liệu dài (thuần, không I/O)."""

from __future__ import annotations

import unittest

from steady_split import TARGET_RATIO, split_text


class TestSplitText(unittest.TestCase):
    def test_short_text_kept_as_single_part(self):
        self.assertEqual(split_text("ngắn", 20_000), ["ngắn"])
        self.assertEqual(split_text("", 20_000), [])

    def test_no_character_loss(self):
        text = ("Đoạn một có câu. " * 2_000) + "\n\n" + ("Đoạn hai dài hơn! " * 2_000)
        parts = split_text(text, 1_000)
        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(parts), text)

    def test_every_part_within_limit(self):
        text = "từ " * 10_000
        parts = split_text(text, 1_000)
        self.assertTrue(all(len(p) <= 1_000 for p in parts), [len(p) for p in parts])
        self.assertEqual("".join(parts), text)

    def test_prefers_paragraph_boundary(self):
        text = ("a" * 700) + "\n\n" + ("b" * 700)
        parts = split_text(text, 1_000)
        self.assertEqual(parts, ["a" * 700 + "\n\n", "b" * 700])

    def test_falls_back_to_sentence(self):
        text = ("câu một. " * 100) + ("câu hai. " * 100)
        parts = split_text(text, 1_000)
        self.assertTrue(parts[0].endswith(". "))
        self.assertLessEqual(len(parts[0]), 1_000)

    def test_hard_cut_without_boundaries(self):
        text = "x" * 2_500
        parts = split_text(text, 1_000)
        self.assertEqual([len(p) for p in parts], [1_000, 1_000, 500])
        self.assertEqual("".join(parts), text)

    def test_target_ratio_defaults_to_90_percent(self):
        text = ("từ " * 10_000)
        parts = split_text(text, 1_000)
        # Phần đầu nhắm ~900 ký tự, không phải sát trần 1.000.
        self.assertLessEqual(len(parts[0]), int(1_000 * TARGET_RATIO))
        self.assertGreaterEqual(len(parts[0]), int(1_000 * TARGET_RATIO * 0.6))


if __name__ == "__main__":
    unittest.main()
