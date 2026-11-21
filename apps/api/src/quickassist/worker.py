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
from quickassist.infrastructure.openai import provider_cache


def load_job_handlers() -> None:
    """Nạp các module ở Business Layer có @job_handler. Thêm job mới → thêm 1 dòng."""
    import quickassist.business.semantic_search.indexing_job  # noqa: F401


async def _repair_once() -> None:
    """Repair save→rebuild bị đứt (crash giữa 2 commit): enqueue lại rebuild cho các user có
    applied_fingerprint lệch embedding_fingerprint (P5 §7.2)."""
    from quickassist.business.semantic_search.rebuild import repair_pending_rebuilds
    from quickassist.data.database import get_sessionmaker

    async with get_sessionmaker()() as session:
        repaired = await repair_pending_rebuilds(session)
    if repaired:
        get_logger(__name__).info("rebuild_repaired", extra={"users": repaired})


async def housekeeping(stop: asyncio.Event, every_seconds: float = 300) -> None:
    """Việc định kỳ của worker: hoàn quota giữ chỗ bị treo (tiến trình chết giữa chừng),
    repair rebuild chưa được bàn giao (P5 §7.2)."""
    from quickassist.business.quota import QuotaService

    log = get_logger(__name__)
    while not stop.is_set():
        try:
            async with QuotaService.open() as quota:
                await quota.release_stale()
        except Exception:  # noqa: BLE001 — không làm sập worker
            log.exception("housekeeping_failed")
        try:
            await _repair_once()
        except Exception:  # noqa: BLE001 — lỗi repair không làm sập worker
            log.exception("rebuild_repair_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=every_seconds)
        except TimeoutError:
            pass


async def main() -> None:
    settings = get_settings()
    if settings.dev_unlimited and settings.app_env == "prod":
        raise RuntimeError("DEV_UNLIMITED phải tắt khi APP_ENV=prod")
    configure_logging(settings.log_level)
    load_job_handlers()
    try:
        await _repair_once()  # repair lúc khởi động — catch-all để lỗi không làm sập worker
    except Exception:  # noqa: BLE001
        get_logger(__name__).exception("rebuild_repair_failed")
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
        await provider_cache.close_all()  # đóng provider BYOK còn mở (ADR-0016)
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
