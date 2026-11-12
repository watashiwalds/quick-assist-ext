"""AutoChunk Task 1 — trích nội dung trang bằng Trafilatura (process pool) → block có id/occ."""

import time
from pathlib import Path

import pytest

from quickassist.business.page_match import extractor
from quickassist.business.page_match._trafilatura_worker import extract_texts
from quickassist.business.page_match.extractor import (
    ExtractError,
    build_blocks,
    extract_blocks,
    extract_text_blocks,
    split_long_block,
    split_paragraphs,
)

FIXTURES = Path(__file__).parents[3] / "fixtures" / "html"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- worker (chạy trực tiếp, không pool)

def test_resolution_list_items_in_document_order_without_boilerplate() -> None:
    texts = extract_texts(_html("resolutions.html"))
    assert texts[0].startswith("Danh sách nghị quyết")
    items = [t for t in texts if t.startswith("Nghị quyết số")]
    assert [t[14:21] for t in items] == ["12/2023", "13/2023", "14/2023", "15/2023", "16/2023"]
    joined = " ".join(texts)
    for junk in ("Trang chủ", "cookie", "Tin liên quan", "Mọi quyền được bảo lưu"):
        assert junk not in joined, junk


def test_article_keeps_headings_quotes_and_table_cells_and_drops_scripts() -> None:
    texts = extract_texts(_html("article.html"))
    assert "Kubernetes cơ bản cho người mới bắt đầu" in texts
    assert any(t.startswith("Hãy luôn đặt resource requests") for t in texts)
    assert "etcd" in texts and "Chọn node phù hợp để chạy Pod mới tạo." in texts
    assert not any("__NEXT_DATA__" in t or "secret" in t for t in texts)


def test_blank_page_has_no_content() -> None:
    assert extract_texts(_html("blank.html")) == []
    assert extract_texts("<<<không phải html>>>") == []


def test_nested_list_item_text_is_not_duplicated_into_parent() -> None:
    html = ("<html><body><article><p>Mở đầu bài viết đủ dài để được giữ lại làm nội dung chính.</p>"
            "<ul><li>Mục cha<ul><li>Mục con</li></ul>đuôi cha</li></ul></article></body></html>")
    texts = extract_texts(html)
    assert "Mục con" in texts
    assert all("Mục con" not in t for t in texts if t.startswith("Mục cha"))


# ---------------------------------------------------------------- hàm thuần

def test_split_long_block_by_sentence_keeps_every_word() -> None:
    text = " ".join(f"Câu số {i} nói về đất đai và quy hoạch." for i in range(60))
    pieces = split_long_block(text, 200)
    assert len(pieces) > 1 and all(len(p) <= 200 for p in pieces)
    assert " ".join(pieces).split() == text.split()
    assert all(p.endswith(".") for p in pieces)  # cắt đúng biên câu


def test_split_sentence_without_punctuation_is_hard_split_on_spaces() -> None:
    text = "từ " * 500
    pieces = split_long_block(text.strip(), 120)
    assert all(len(p) <= 120 for p in pieces)
    assert " ".join(pieces).split() == text.split()


def test_short_block_unchanged() -> None:
    assert split_long_block("ngắn.", 1200) == ["ngắn."]


def test_build_blocks_ids_and_occurrences() -> None:
    ex = build_blocks(["A lặp", "B", "A lặp", "C", "A lặp"], max_block_chars=1200, max_chars=10_000)
    assert [b.id for b in ex.blocks] == ["b00", "b01", "b02", "b03", "b04"]
    assert [b.occ for b in ex.blocks] == [0, 0, 1, 0, 2]
    assert ex.total_chars == sum(len(b.text) for b in ex.blocks) and not ex.truncated


def test_build_blocks_occ_renumbered_after_split() -> None:
    long = "Một câu giống nhau. " * 10
    ex = build_blocks([long.strip()], max_block_chars=40, max_chars=10_000)
    same = [b for b in ex.blocks if b.text == ex.blocks[0].text]
    assert [b.occ for b in same] == list(range(len(same))) and len(same) > 1


def test_build_blocks_caps_total_chars_on_block_boundary() -> None:
    ex = build_blocks(["x" * 40, "y" * 40, "z" * 40], max_block_chars=1200, max_chars=100)
    assert [b.text[0] for b in ex.blocks] == ["x", "y"] and ex.truncated and ex.total_chars == 80


# ---------------------------------------------------------------- nguồn text dán

def test_split_paragraphs_on_blank_lines_preserves_order_and_inner_line_breaks() -> None:
    text = "Đoạn một.\n\nĐoạn hai\ndòng hai.\n\n\n  Đoạn ba.  \r\n"
    assert split_paragraphs(text) == ["Đoạn một.", "Đoạn hai\ndòng hai.", "Đoạn ba."]


def test_split_paragraphs_without_blank_lines_falls_back_to_sentences() -> None:
    # Copy từ PDF/Word thường chỉ có \n đơn → vẫn có ranh giới đoạn theo câu.
    text = "Câu một về đất đai.\nCâu hai về quy hoạch!\nCâu ba về giao thông?"
    assert split_paragraphs(text) == [
        "Câu một về đất đai.", "Câu hai về quy hoạch!", "Câu ba về giao thông?",
    ]


def test_split_paragraphs_normalizes_and_drops_empty_input() -> None:
    assert split_paragraphs("") == []
    assert split_paragraphs("  \n\n \x00 ") == []
    assert split_paragraphs("Một\x00 đoạn.\r\n\r\nĐoạn khác.") == ["Một đoạn.", "Đoạn khác."]


def test_extract_text_blocks_builds_blocks_and_caps_chars() -> None:
    ex = extract_text_blocks("A.\n\nB.\n\nC.", max_block_chars=1200, max_chars=4)
    assert [b.text for b in ex.blocks] == ["A.", "B."] and ex.truncated


def test_extract_text_blocks_empty_raises() -> None:
    with pytest.raises(ExtractError) as e:
        extract_text_blocks(" \n\n ", max_block_chars=1200, max_chars=50_000)
    assert e.value.reason == "empty"


# ---------------------------------------------------------------- process pool

def _hang(_: str) -> list[str]:
    time.sleep(60)
    return []


def _crash(_: str) -> list[str]:
    import os

    os._exit(1)


async def test_extract_blocks_via_process_pool() -> None:
    ex = await extract_blocks(_html("resolutions.html"), timeout_seconds=30, max_block_chars=1200,
                              max_chars=50_000)
    assert len(ex.blocks) == 8 and ex.blocks[0].id == "b00"


async def test_empty_page_raises_extract_error() -> None:
    with pytest.raises(ExtractError) as e:
        await extract_blocks(_html("blank.html"), timeout_seconds=30, max_block_chars=1200, max_chars=50_000)
    assert e.value.reason == "empty"


@pytest.mark.parametrize(("fn", "reason"), [(_hang, "timeout"), (_crash, "crashed")])
async def test_hung_or_crashed_parser_is_killed_and_pool_recovers(monkeypatch, fn, reason) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(extractor, "_worker_fn", fn)
    started = time.monotonic()
    with pytest.raises(ExtractError) as e:
        await extract_blocks("<p>x</p>", timeout_seconds=3, max_block_chars=1200, max_chars=50_000)
    assert e.value.reason == reason and time.monotonic() - started < 30
    monkeypatch.undo()  # pool mới, hàm thật → lại chạy bình thường
    ex = await extract_blocks(_html("article.html"), timeout_seconds=30, max_block_chars=1200,
                              max_chars=50_000)
    assert ex.blocks
