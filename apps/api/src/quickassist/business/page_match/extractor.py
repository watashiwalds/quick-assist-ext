"""Business Layer — Page Match: nội dung nguồn → các đoạn (block) để embed + thẩm định (ADR-0013).

- HTML: Trafilatura chạy trong ProcessPoolExecutor (spawn) — lazy singleton, timeout cứng; treo → kill cả
  pool và tạo lại ở lần gọi sau; crash parse (lxml) không lan vào event loop của API.
- Text dán (PDF/Word/chat…): bỏ qua Trafilatura, tách đoạn thuần Python (`split_paragraphs`); dòng đơn
  trong mỗi đoạn là hard-wrap của PDF/Word → nối lại bằng khoảng trắng (reflow).
- Khối > `max_block_chars` được tách theo câu (`split_long_block`); khối < `min_block_chars` (chỉ nguồn
  text dán) được gộp với khối liền kề — copy từ PDF thường cắt theo dòng hiển thị hoặc theo câu đơn lẻ.
- `occ` = số lần đúng text đó đã xuất hiện trước → extension highlight đúng lần xuất hiện thứ n.
- Cap tổng ký tự theo biên khối → giới hạn chi phí embed.
"""

import asyncio
import multiprocessing
import re
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

from quickassist.business.page_match import _trafilatura_worker
from quickassist.infrastructure.logging import get_logger

log = get_logger(__name__)

_SENTENCE_END = re.compile(r"(?<=[.!?…;:])\s+")
_BLANK_LINE = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Block:
    id: str
    text: str
    occ: int


@dataclass(frozen=True)
class Extraction:
    blocks: list[Block]
    total_chars: int
    truncated: bool  # True = trang dài hơn cap, đã bỏ các khối cuối


class ExtractError(Exception):
    """Không trích được nội dung: trang rỗng / không có nội dung chính / parse lỗi / quá thời gian."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------- hàm thuần (dễ unit test)

def _hard_split(text: str, max_chars: int) -> list[str]:
    """Câu dài hơn max (không có dấu câu) → cắt theo khoảng trắng gần nhất, cùng lắm cắt cứng."""
    out: list[str] = []
    while len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars + 1)
        if cut <= 0:
            cut = max_chars
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def split_long_block(text: str, max_chars: int) -> list[str]:
    """Tách khối dài theo câu, gom câu liền nhau tới gần `max_chars`. Không mất chữ nào
    (chỉ khác khoảng trắng giữa các mảnh)."""
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    cur = ""
    for sentence in _SENTENCE_END.split(text):
        for part in _hard_split(sentence, max_chars):
            if not cur:
                cur = part
            elif len(cur) + 1 + len(part) <= max_chars:
                cur = f"{cur} {part}"
            else:
                pieces.append(cur)
                cur = part
    if cur:
        pieces.append(cur)
    return pieces


def split_paragraphs(text: str) -> list[str]:
    """Văn bản người dùng dán → các đoạn liền mạch, giữ thứ tự tài liệu.

    - Chuẩn hoá xuống dòng (CRLF/CR → LF), bỏ NUL; tách theo dòng trống (`\\n\\n`).
    - Reflow: bên trong mỗi đoạn, `\\n` đơn là hard-wrap theo chiều rộng trang (copy từ PDF/Word)
      → nối lại bằng một khoảng trắng. Không có dòng trống → cả tài liệu là một đoạn;
      `build_blocks` sẽ tách theo câu và gộp tới ngưỡng khối tối thiểu.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()
    if not normalized:
        return []
    paragraphs = []
    for p in _BLANK_LINE.split(normalized):
        p = " ".join(line.strip() for line in p.split("\n") if line.strip())
        if p:
            paragraphs.append(p)
    return paragraphs


def build_blocks(
    texts: list[str], *, max_block_chars: int, max_chars: int, min_block_chars: int = 0,
) -> Extraction:
    """Text khối thô (thứ tự tài liệu) → Block có id/occ, đã tách câu, gộp khối ngắn và cap tổng ký tự.

    `min_block_chars` > 0 (nguồn text dán): khối ngắn hơn ngưỡng được gộp với khối liền kề — cosine,
    thẩm định LLM và ghi chú cần đoạn đủ ngữ cảnh. Giới hạn mỗi lần gộp là `min(max_block_chars,
    max_chars)` để khối gộp không vượt ngân sách tổng; đường dẫn HTML giữ `min_block_chars=0` vì
    "Xem trên trang" cần khối khớp nguyên văn nội dung trang.
    """
    blocks: list[Block] = []
    seen: dict[str, int] = {}
    total = 0
    truncated = False
    group_limit = min(max_block_chars, max_chars)
    buf = ""

    def flush(text: str) -> bool:
        """Thêm một block; False = vượt cap tổng ký tự → dừng, phần còn lại bị bỏ (truncated)."""
        nonlocal total, truncated
        if not text:
            return True
        if total + len(text) > max_chars:
            truncated = True
            return False
        occ = seen.get(text, 0)
        seen[text] = occ + 1
        blocks.append(Block(f"b{len(blocks):02d}", text, occ))
        total += len(text)
        return True

    for raw in texts:
        for piece in split_long_block(raw, max_block_chars):
            if buf and len(buf) + 1 + len(piece) > group_limit:
                if not flush(buf):
                    return Extraction(blocks, total, truncated)
                buf = ""
            buf = f"{buf} {piece}" if buf else piece
            if len(buf) >= min_block_chars:
                if not flush(buf):
                    return Extraction(blocks, total, truncated)
                buf = ""
    flush(buf)  # đuôi tài liệu chưa đủ ngưỡng gộp → vẫn thành block cuối
    return Extraction(blocks, total, truncated)


def extract_text_blocks(
    text: str, *, max_block_chars: int, max_chars: int, min_block_chars: int = 0,
) -> Extraction:
    """Text dán → Extraction, không qua Trafilatura/process pool. Rỗng → ExtractError("empty")."""
    extraction = build_blocks(
        split_paragraphs(text),
        max_block_chars=max_block_chars, max_chars=max_chars, min_block_chars=min_block_chars,
    )
    if not extraction.blocks:
        raise ExtractError("empty")
    return extraction


# ---------------------------------------------------------------- process pool

_pool: ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()
_WORKERS = 2
# Hàm chạy trong process con — tách ra biến module để test thay bằng hàm treo/crash.
_worker_fn = _trafilatura_worker.extract_texts


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            # spawn: process con sạch, không thừa kế event loop/thread/kết nối DB của API.
            _pool = ProcessPoolExecutor(max_workers=_WORKERS, mp_context=multiprocessing.get_context("spawn"))
        return _pool


def _reset_pool(*, kill: bool) -> None:
    """Bỏ pool hiện tại (treo/hỏng). kill=True → giết process con đang chạy để giải phóng CPU/RAM."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is None:
        return
    if kill:
        # ProcessPoolExecutor không có API kill công khai; _processes là chi tiết ổn định từ py3.8.
        for proc in list(getattr(pool, "_processes", {}).values()):
            try:
                proc.kill()
            except Exception:  # noqa: BLE001 — process có thể đã chết
                pass
    pool.shutdown(wait=False, cancel_futures=True)


def shutdown_extractor() -> None:
    """Gọi khi tắt API (lifespan)."""
    _reset_pool(kill=True)


async def extract_blocks(
    html: str, *, timeout_seconds: float, max_block_chars: int, max_chars: int,
) -> Extraction:
    loop = asyncio.get_running_loop()
    try:
        fut = loop.run_in_executor(_get_pool(), _worker_fn, html)
        texts = await asyncio.wait_for(fut, timeout=timeout_seconds)
    except TimeoutError as e:
        log.warning("page_extract_timeout", extra={"timeout_s": timeout_seconds})
        _reset_pool(kill=True)
        raise ExtractError("timeout") from e
    except BrokenProcessPool as e:
        log.warning("page_extract_pool_broken")
        _reset_pool(kill=True)
        raise ExtractError("crashed") from e
    except Exception as e:  # noqa: BLE001 — lỗi parse HTML không tin cậy → "không trích được"
        log.warning("page_extract_failed", extra={"error_type": type(e).__name__})
        raise ExtractError("parse_failed") from e
    extraction = build_blocks(list(texts), max_block_chars=max_block_chars, max_chars=max_chars)
    if not extraction.blocks:
        raise ExtractError("empty")
    return extraction
