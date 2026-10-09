"""Business Layer — Semantic Search Service: chia văn bản thành chunk (hàm thuần, dễ test & benchmark).

v2 (task N04, mặc định) — chia theo CÂU tiếng Việt, giữ nguyên chữ ký `chunk_text(text, *, size, overlap)`:
  1. Tách đoạn (dòng trống) và dòng gạch đầu dòng thành đơn vị riêng.
  2. Tách câu: dấu . ! ? … rồi khoảng trắng + chữ HOA/số/ngoặc — KHÔNG tách sau chữ viết tắt
     tiếng Việt thường gặp (TP., TS., PGS., v.v., Q.1 …) hay số thập phân (1.5, 3.000).
  3. Gom câu vào chunk ≤ `size`; ưu tiên cắt ở ranh giới đoạn khi chunk đã đủ dài.
  4. Overlap theo CÂU (mang các câu cuối ≤ `overlap` ký tự sang chunk sau) — không cắt giữa từ.
  5. Câu dài hơn `size` → cắt theo TỪ (không bao giờ cắt giữa từ trừ khi một "từ" dài hơn size).
Bất biến (có test): mọi chunk ≤ size; không mất từ nào; thứ tự giữ nguyên.

v1 (`chunk_text_v1`) giữ lại để benchmark / quay về bằng CHUNKING_STRATEGY=v1.
"""

import re
from collections.abc import Callable

# ---------------------------------------------------------------- v1 (bản gốc)
_SENT_SPLIT_V1 = re.compile(r"(?<=[.!?…。])\s+|\n{2,}")


def chunk_text_v1(text: str, *, size: int, overlap: int) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    pieces = [p.strip() for p in _SENT_SPLIT_V1.split(text) if p and p.strip()]
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


# ---------------------------------------------------------------- v2 (theo câu tiếng Việt)
# Chữ viết tắt (viết thường, không dấu chấm cuối) — gặp "<abbr>." thì KHÔNG coi là hết câu.
_ABBREVIATIONS = frozenset({
    "tp", "tt", "tx", "q", "p", "h", "ts", "ths", "pgs", "gs", "bs", "ks", "cn", "th.s", "ts.bs",
    "v.v", "vv", "vd", "v.d", "tr", "st", "sđd", "nxb", "đ/c", "mr", "mrs", "ms", "dr",
    "prof", "no", "vs", "etc", "e.g", "i.e", "fig", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec", "inc", "ltd", "co", "corp", "ubnd", "hđnd",
})
# Ứng viên kết câu: cụm dấu kết thúc + (ngoặc/nháy đóng) + khoảng trắng.
_END = re.compile(r"[.!?…]+[\"'”’)\]]*\s+")
_BULLET = re.compile(r"^\s*(?:[-*•–+]|\d{1,3}[.)])\s+")
_WS = re.compile(r"[ \t ]+")


def _is_abbreviation(before: str) -> bool:
    word = before.rsplit(None, 1)[-1] if before.strip() else ""
    word = word.lstrip("(\"'“‘[").lower()
    if not word:
        return False
    if word in _ABBREVIATIONS:
        return True
    # Một chữ cái (tên viết tắt "Nguyễn V. A.") hoặc chuỗi chữ cái+chấm ("U.S", "v.v")
    return (len(word) == 1 and word.isalpha()) or bool(re.fullmatch(r"(?:\w\.)+\w?", word))


def split_sentences(paragraph: str) -> list[str]:
    """Tách câu trong một đoạn (đã chuẩn hoá khoảng trắng)."""
    out: list[str] = []
    start = 0
    for m in _END.finditer(paragraph):
        end = m.end()
        nxt = paragraph[end:end + 1]
        if not nxt:
            break
        punct = m.group().strip()
        # "…" hoặc "!" "?" luôn kết câu; "." chỉ kết câu nếu không phải viết tắt và câu sau
        # bắt đầu bằng chữ HOA / số / ngoặc mở.
        if punct.startswith(".") and not punct.startswith("..."):
            if _is_abbreviation(paragraph[start:m.start()]):
                continue
            if not (nxt.isupper() or nxt.isdigit() or nxt in "\"'“‘([-•"):
                continue
        out.append(paragraph[start:m.start() + len(m.group().rstrip())].strip())
        start = end
    tail = paragraph[start:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def _units(text: str) -> list[tuple[str, bool]]:
    """[(câu, là_câu_đầu_đoạn)] theo thứ tự."""
    units: list[tuple[str, bool]] = []
    for para in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [ln for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        # Mỗi gạch đầu dòng là một "đoạn" riêng; các dòng thường liền nhau được nối lại.
        blocks: list[str] = []
        for ln in lines:
            if _BULLET.match(ln) or not blocks:
                blocks.append(ln)
            else:
                blocks[-1] += " " + ln
        for block in blocks:
            sentences = split_sentences(_WS.sub(" ", block).strip())
            units += [(s, i == 0) for i, s in enumerate(sentences)]
    return units


def _split_long(sentence: str, size: int, overlap: int) -> list[str]:
    """Câu dài hơn size → các mảnh ≤ size, cắt ở ranh giới TỪ, overlap theo từ."""
    words = sentence.split(" ")
    pieces: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        while len(w) > size:  # "từ" khổng lồ (URL, chuỗi base64) → buộc cắt cứng
            if cur:
                pieces.append(" ".join(cur))
                cur, cur_len = [], 0
            pieces.append(w[:size])
            w = w[size:]
        add = len(w) + (1 if cur else 0)
        if cur_len + add > size:
            pieces.append(" ".join(cur))
            keep: list[str] = []
            keep_len = 0
            for prev in reversed(cur):  # overlap theo từ
                if keep_len + len(prev) + 1 > overlap:
                    break
                keep.insert(0, prev)
                keep_len += len(prev) + 1
            cur = keep
            cur_len = len(" ".join(cur))
            add = len(w) + (1 if cur else 0)
            if cur_len + add > size:  # overlap + từ mới vẫn quá dài → bỏ overlap
                cur, cur_len, add = [], 0, len(w)
        cur.append(w)
        cur_len += add
    if cur:
        pieces.append(" ".join(cur))
    return [p for p in pieces if p]


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("size phải > 0")
    overlap = max(0, min(overlap, size // 2))
    units = _units(text)
    if not units:
        return []
    flat = " ".join(u for u, _ in units)
    if len(flat) <= size:
        return [flat]

    chunks: list[str] = []
    cur: list[str] = []
    fresh = 0  # số mảnh MỚI trong cur (không tính phần overlap mang sang)

    def length(parts: list[str]) -> int:
        return sum(len(p) for p in parts) + max(0, len(parts) - 1)

    def flush() -> None:
        nonlocal cur, fresh
        fresh = 0
        if not cur:
            return
        chunks.append(" ".join(cur))
        carry: list[str] = []
        for s in reversed(cur):  # overlap theo câu
            if length([s, *carry]) > overlap:
                break
            carry.insert(0, s)
        cur = carry

    for sentence, starts_paragraph in units:
        pieces = _split_long(sentence, size, overlap) if len(sentence) > size else [sentence]
        for i, piece in enumerate(pieces):
            new_para = starts_paragraph and i == 0
            if cur and (
                length([*cur, piece]) > size
                or (new_para and length(cur) >= size * 0.6)  # đủ dài → cắt ở ranh giới đoạn
            ):
                flush()
                if length([*cur, piece]) > size:  # overlap + mảnh mới quá dài → bỏ overlap
                    cur = []
            cur.append(piece)
            fresh += 1
    if cur and fresh:
        chunks.append(" ".join(cur))
    return chunks


CHUNKERS: dict[str, Callable[..., list[str]]] = {"v1": chunk_text_v1, "v2": chunk_text}
