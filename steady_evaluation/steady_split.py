"""§3.0 — Chia tài liệu dài thành part ≤ trần backend (đồng bộ với extension).

Harness trước đây cắt cứng ở ``max_note_chars`` (mất 12,7–50,5% nội dung 3 file TXT).
Từ Lát 3, harness dùng đúng hợp đồng D2: chia tại ranh giới đoạn → câu → từ,
mỗi part ≤ trần, gửi một lần qua ``POST /notes`` với ``parts`` + ``document_id``.

Quy tắc giống ``apps/extension/src/shared/notes/split.ts``:
  - mục tiêu mỗi part ≈ 90% trần (mặc định 18k với trần 20k) để không sát giới hạn;
  - không part nào vượt trần;
  - ghép lại KHÔNG mất ký tự: ``"".join(split_text(text)) == text``.
    (Backend strip() hai đầu mỗi part nên chỉ khoảng trắng ở biên có thể mất.)

Hàm thuần, không I/O → test độc lập, dùng lại được cho mọi module.
"""

from __future__ import annotations

import re

# Mục tiêu mỗi phần = 90% trần (khớp TARGET_RATIO của extension).
TARGET_RATIO = 0.9

# Câu kết thúc bằng . ! ? … (có thể kèm ngoặc/nháy đóng) rồi khoảng trắng.
_SENTENCE = re.compile(r"""[.!?…](?:["'”’)\]]+)?\s+""")


def _paragraph_cut(text: str, lo: int, hi: int) -> int | None:
    at = text.rfind("\n\n", 0, hi)
    return at + 2 if at >= lo else None


def _sentence_cut(text: str, lo: int, hi: int) -> int | None:
    best: int | None = None
    for match in _SENTENCE.finditer(text, 0, hi):
        end = match.end()
        if end >= lo:
            best = end
    return best


def _word_cut(text: str, lo: int, hi: int) -> int | None:
    at = text.rfind(" ", 0, hi)
    return at + 1 if at >= lo else None


def _choose_cut(text: str, max_chars: int, target_chars: int) -> int:
    """Chọn điểm cắt: boundary ưu tiên cao nhất trong [60% target, target],
    nới tới trần nếu không có; không có boundary nào → cắt cứng tại trần."""
    min_cut = max(1, int(target_chars * 0.6))
    for find in (_paragraph_cut, _sentence_cut, _word_cut):
        cut = find(text, min_cut, target_chars)
        if cut is None:
            cut = find(text, min_cut, max_chars)
        if cut is not None:
            return min(cut, max_chars)
    return max_chars


def split_text(text: str, max_chars: int = 20_000,
               target_chars: int | None = None) -> list[str]:
    """Chia ``text`` thành các part ≤ ``max_chars`` (mặc định trần server).

    ``target_chars`` mặc định = 90% ``max_chars``. Văn bản rỗng → ``[]``.
    """
    limit = max(1, int(max_chars))
    target = int(target_chars) if target_chars is not None else int(limit * TARGET_RATIO)
    target = min(limit, max(1, target))
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = _choose_cut(rest, limit, target)
        parts.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        parts.append(rest)
    return parts
