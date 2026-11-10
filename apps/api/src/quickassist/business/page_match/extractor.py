"""Business Layer — Page Match: HTML trang → các đoạn (block) để embed + thẩm định (ADR-0013).

- Trafilatura chạy trong ProcessPoolExecutor (spawn) — lazy singleton, timeout cứng; treo → kill cả pool
  và tạo lại ở lần gọi sau; crash parse (lxml) không lan vào event loop của API.
- Khối > `max_block_chars` được tách theo câu (`split_long_block`).
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


def build_blocks(texts: list[str], *, max_block_chars: int, max_chars: int) -> Extraction:
    """Text khối thô (thứ tự tài liệu) → Block có id/occ, đã tách câu và cap tổng ký tự."""
    blocks: list[Block] = []
    seen: dict[str, int] = {}
    total = 0
    truncated = False
    for raw in texts:
        for piece in split_long_block(raw, max_block_chars):
            if total + len(piece) > max_chars:
                truncated = True
                break
            occ = seen.get(piece, 0)
            seen[piece] = occ + 1
            blocks.append(Block(f"b{len(blocks):02d}", piece, occ))
            total += len(piece)
        if truncated:
            break
    return Extraction(blocks, total, truncated)


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
