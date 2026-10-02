from quickassist.modules.search.chunking import chunk_text


def test_short_text_is_single_chunk() -> None:
    assert chunk_text("Xin chào.", size=100, overlap=10) == ["Xin chào."]


def test_empty_text() -> None:
    assert chunk_text("   ", size=100, overlap=10) == []


def test_long_text_respects_size_and_keeps_all_words() -> None:
    text = " ".join(f"Câu số {i} nói về pgvector và tìm kiếm ngữ nghĩa." for i in range(200))
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)
    for i in (0, 77, 199):
        assert any(f"Câu số {i} " in c for c in chunks)


def test_very_long_sentence_is_hard_split() -> None:
    chunks = chunk_text("a" * 1000, size=300, overlap=50)
    assert all(len(c) <= 300 for c in chunks)
    assert sum(len(c) for c in chunks) >= 1000
