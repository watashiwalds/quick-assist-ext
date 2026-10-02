"""Business Layer — Semantic Search Service: chia văn bản thành chunk (hàm thuần, dễ test & benchmark).

Chiến lược v1: gom theo đoạn → câu, cửa sổ ký tự có overlap. Thay bằng semantic
chunking ở task N04 mà KHÔNG đổi chữ ký hàm.
"""

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?…。])\s+|\n{2,}")


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    pieces = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in pieces:
        while len(p) > size:  # câu quá dài → cắt cứng
            head, p = p[:size], p[size - overlap:]
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(head)
        if len(buf) + len(p) + 1 <= size:
            buf = f"{buf} {p}".strip()
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap else ""
            buf = f"{tail} {p}".strip() if len(tail) + len(p) + 1 <= size else p
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]
