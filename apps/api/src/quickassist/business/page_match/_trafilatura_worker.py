"""Business Layer — Page Match: hàm chạy TRONG PROCESS CON (ProcessPoolExecutor) để parse HTML không tin cậy.

Tách riêng module + chỉ import trafilatura/lxml → process con khởi động nhẹ, lỗi parse (lxml/libxml2)
không lan sang event loop của API (ADR-0013, AD-2). Hàm phải ở cấp module để pickle được (spawn).
"""

from __future__ import annotations

from typing import Any

# Phần tử khối trong XML của Trafilatura (output_format="xml"): đoạn, tiêu đề, mục danh sách,
# trích dẫn, ô bảng, khối code. Một khối = một "đoạn" người dùng có thể chọn.
BLOCK_TAGS = ("p", "head", "item", "quote", "cell", "code")


def _collect(el: Any, parts: list[str]) -> None:
    """Gom text của `el` nhưng bỏ qua mọi khối con (kể cả lồng sâu, vd list → item)."""
    parts.append(el.text or "")
    for child in el:
        if child.tag in BLOCK_TAGS or child.tag == "lb":
            parts.append("\n")  # khối con được tách thành đoạn riêng; lb = xuống dòng
        else:
            _collect(child, parts)
        parts.append(child.tail or "")


def _own_text(el: Any) -> str:
    """Text của khối, KHÔNG gồm text của khối con — chuẩn hoá khoảng trắng."""
    parts: list[str] = []
    _collect(el, parts)
    return " ".join("".join(parts).split())


def extract_texts(html: str) -> list[str]:
    """HTML → danh sách text khối theo thứ tự tài liệu (đã chuẩn hoá khoảng trắng, bỏ rỗng).

    favor_recall=True: trang danh sách (nghị quyết, mục lục) thường bị cắt bớt khi ưu tiên precision.
    """
    import trafilatura
    from lxml import etree

    xml = trafilatura.extract(
        html, output_format="xml", include_tables=True, include_comments=False,
        include_links=False, include_images=False, include_formatting=False,
        favor_recall=True, deduplicate=False, with_metadata=False,
    )
    if not xml:
        return []
    root = etree.fromstring(xml.encode("utf-8"), parser=etree.XMLParser(resolve_entities=False,
                                                                           no_network=True))
    main = root.find("main")
    scope = main if main is not None else root
    out: list[str] = []
    for el in scope.iter(*BLOCK_TAGS):
        text = _own_text(el)
        if text:
            out.append(text)
    return out
