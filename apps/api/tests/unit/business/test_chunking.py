"""N04 — chunking v2 theo câu tiếng Việt: bất biến (≤ size, không mất từ, giữ thứ tự),
không tách câu sai ở chữ viết tắt/số thập phân, overlap theo câu, v1 vẫn dùng được."""

import random
import re

import pytest

from quickassist.business.semantic_search.chunking import (
    CHUNKERS,
    chunk_text,
    chunk_text_v1,
    split_sentences,
)


def words(s: str) -> list[str]:
    return re.findall(r"\S+", s)


def test_short_text_is_single_chunk() -> None:
    assert chunk_text("Xin chào.", size=100, overlap=10) == ["Xin chào."]


def test_empty_text() -> None:
    assert chunk_text("   \n\n ", size=100, overlap=10) == []


@pytest.mark.parametrize(("text", "expected"), [
    ("Tôi sống ở TP. Hồ Chí Minh. Tôi học CNTT.", ["Tôi sống ở TP. Hồ Chí Minh.", "Tôi học CNTT."]),
    ("PGS. TS. Nguyễn Văn A giảng bài. Rất hay!", ["PGS. TS. Nguyễn Văn A giảng bài.", "Rất hay!"]),
    ("Giá tăng 1.5 lần. Lãi suất 7.2%.", ["Giá tăng 1.5 lần.", "Lãi suất 7.2%."]),
    ("Gồm táo, cam, v.v. Tất cả đều tươi.", ["Gồm táo, cam, v.v. Tất cả đều tươi."]),
    ("Bạn đã hiểu chưa? Chưa… Vậy đọc lại!", ["Bạn đã hiểu chưa?", "Chưa…", "Vậy đọc lại!"]),
    ("Anh ấy nói “Xong rồi.” Sau đó về nhà.", ["Anh ấy nói “Xong rồi.”", "Sau đó về nhà."]),
    ("Xem https://example.com/a.b nhé. OK", ["Xem https://example.com/a.b nhé.", "OK"]),
])
def test_vietnamese_sentence_split(text: str, expected: list[str]) -> None:
    assert split_sentences(text) == expected


def test_chunks_end_at_sentence_boundaries_and_overlap_whole_sentences() -> None:
    text = " ".join(f"Câu số {i} nói về pgvector và tìm kiếm ngữ nghĩa." for i in range(60))
    chunks = chunk_text(text, size=300, overlap=60)
    assert len(chunks) > 1 and all(len(c) <= 300 for c in chunks)
    assert all(c.endswith(".") for c in chunks)  # không cắt giữa câu
    for a, b in zip(chunks, chunks[1:], strict=False):
        first_sentence_of_b = split_sentences(b)[0]
        assert first_sentence_of_b in a  # overlap là câu nguyên vẹn của chunk trước


def test_prefers_paragraph_boundary() -> None:
    p1 = " ".join(["Đoạn một nói về nấu phở."] * 10)  # ~260 ký tự ≥ 60% size → cắt ở ranh giới đoạn
    p2 = " ".join(["Đoạn hai nói về Kubernetes."] * 10)
    chunks = chunk_text(f"{p1}\n\n{p2}", size=400, overlap=0)
    assert all(("phở" in c) != ("Kubernetes" in c) for c in chunks)  # không trộn 2 chủ đề


def test_bullets_are_units() -> None:
    text = "Việc cần làm:\n- Mua sữa\n- Học bài\n1. Nộp báo cáo\n2) Gọi điện"
    expected = "Việc cần làm: - Mua sữa - Học bài 1. Nộp báo cáo 2) Gọi điện"
    assert chunk_text(text, size=1000, overlap=0) == [expected]
    small = chunk_text(text, size=20, overlap=0)
    assert all(len(c) <= 20 for c in small) and words(" ".join(small)) == words(text)


def test_very_long_sentence_is_split_on_words() -> None:
    sentence = " ".join(f"từ{i}" for i in range(400)) + "."
    chunks = chunk_text(sentence, size=120, overlap=20)
    assert all(len(c) <= 120 for c in chunks)
    joined = {w.rstrip(".") for w in words(" ".join(chunks))}
    assert all(f"từ{i}" in joined for i in range(400))  # không mất / cắt đôi từ nào


def test_giant_token_is_hard_split() -> None:
    chunks = chunk_text("a" * 1000, size=300, overlap=50)
    assert all(len(c) <= 300 for c in chunks) and sum(len(c) for c in chunks) >= 1000


@pytest.mark.parametrize("seed", range(30))
def test_invariants_on_random_text(seed: int) -> None:
    rnd = random.Random(seed)
    vocab = ["Hà", "Nội", "pgvector", "TP.", "v.v.", "1.5", "tìm", "kiếm", "ngữ", "nghĩa", "ghi", "chú",
             "x" * rnd.randint(1, 80), "Đà", "Nẵng", "AI"]
    paras = []
    for _ in range(rnd.randint(1, 6)):
        sents = [" ".join(rnd.choice(vocab) for _ in range(rnd.randint(1, 40))) + rnd.choice(".!?…")
                 for _ in range(rnd.randint(1, 8))]
        paras.append(" ".join(sents))
    text = "\n\n".join(paras)
    size, overlap = rnd.randint(40, 600), rnd.randint(0, 200)
    chunks = chunk_text(text, size=size, overlap=overlap)
    assert chunks and all(0 < len(c) <= size for c in chunks)
    # không mất từ, đúng thứ tự (bỏ phần trùng do overlap)
    covered = " ".join(chunks)
    pos = 0
    for w in words(text):
        found = covered.find(w, pos) if len(w) <= size else covered.find(w[:size], pos)
        assert found >= 0, (w, seed)
        pos = found


def test_v1_still_available_for_benchmark() -> None:
    assert set(CHUNKERS) == {"v1", "v2"}
    text = " ".join(f"Câu số {i} nói về pgvector." for i in range(100))
    assert all(len(c) <= 300 for c in chunk_text_v1(text, size=300, overlap=50))
