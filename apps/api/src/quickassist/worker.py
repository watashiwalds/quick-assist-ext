"""Composition root của tiến trình worker (cùng codebase, khác entrypoint).
Chạy: python -m quickassist.worker

Tách tiến trình để request API không bị chặn bởi gọi AI; scale worker độc lập (SDS §4.2).
"""

import asyncio
import signal

import quickassist.data.models  # noqa: F401 — đăng ký entity
from quickassist.data.database import dispose_engine
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.jobs import worker_loop
from quickassist.infrastructure.logging import configure_logging, get_logger


def load_job_handlers() -> None:
    """Nạp các module ở Business Layer có @job_handler. Thêm job mới → thêm 1 dòng."""
    import quickassist.business.semantic_search.indexing_job  # noqa: F401


async def housekeeping(stop: asyncio.Event, every_seconds: float = 300) -> None:
    """Việc định kỳ của worker: hoàn quota giữ chỗ bị treo (tiến trình chết giữa chừng)."""
    from quickassist.business.quota import QuotaService

    log = get_logger(__name__)
    while not stop.is_set():
        try:
            async with QuotaService.open() as quota:
                await quota.release_stale()
        except Exception:  # noqa: BLE001 — không làm sập worker
            log.exception("housekeeping_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=every_seconds)
        except TimeoutError:
            pass


async def main() -> None:
    configure_logging(get_settings().log_level)
    load_job_handlers()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    try:
        await asyncio.gather(worker_loop(stop), housekeeping(stop))
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
