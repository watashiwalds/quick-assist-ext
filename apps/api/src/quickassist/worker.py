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
from quickassist.infrastructure.logging import configure_logging


def load_job_handlers() -> None:
    """Nạp các module ở Business Layer có @job_handler. Thêm job mới → thêm 1 dòng."""
    import quickassist.business.semantic_search.indexing_job  # noqa: F401


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
        await worker_loop(stop)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
