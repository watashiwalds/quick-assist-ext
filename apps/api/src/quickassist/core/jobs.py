"""Hàng đợi job nền chạy trên chính PostgreSQL (ADR-0003).

Vì sao không Redis/Celery: MVP chỉ cần vài job/giây; thêm broker = thêm hạ tầng,
thêm điểm lỗi. `SELECT ... FOR UPDATE SKIP LOCKED` cho phép nhiều worker chạy song
song an toàn. Khi tải tăng, thay implementation này bằng broker mà không đổi API
`enqueue()` / `@job_handler`.

Cách dùng (module bất kỳ):
    # phát job — trong cùng transaction với thay đổi dữ liệu (outbox pattern)
    await enqueue(session, "search.index_note", {"note_id": str(note.id)}, dedupe_key=...)

    # xử lý job — trong module sở hữu nghiệp vụ, đăng ký ở handlers.py của module
    @job_handler("search.index_note")
    async def handle(session, payload): ...

Tên job: "<module>.<hành_động>" — module đứng đầu là module XỬ LÝ job.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.core.config import get_settings
from quickassist.core.db import Base, get_sessionmaker
from quickassist.core.logging import get_logger
from quickassist.core.request_context import set_request_id

log = get_logger(__name__)

JobHandler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
_HANDLERS: dict[str, JobHandler] = {}


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_queue", "status", "run_after"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")  # QUEUED|RUNNING|DONE|DEAD
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def job_handler(kind: str) -> Callable[[JobHandler], JobHandler]:
    def deco(fn: JobHandler) -> JobHandler:
        if kind in _HANDLERS:
            raise RuntimeError(f"Job handler '{kind}' đã được đăng ký")
        _HANDLERS[kind] = fn
        return fn

    return deco


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    delay_seconds: int = 0,
) -> None:
    """Thêm job vào hàng đợi. KHÔNG commit — job chỉ tồn tại nếu transaction gọi nó commit.

    dedupe_key: nếu job cùng key còn QUEUED thì bỏ qua (tránh index trùng khi sửa liên tục).
    """
    from quickassist.core.request_context import get_request_id

    stmt = insert(Job).values(
        id=uuid.uuid4(),
        kind=kind,
        payload=payload,
        dedupe_key=dedupe_key,
        max_attempts=get_settings().job_max_attempts,
        run_after=datetime.now(UTC) + timedelta(seconds=delay_seconds),
        request_id=get_request_id(),
    )
    if dedupe_key:
        # dedupe_key chỉ giữ khi job còn QUEUED (được xoá lúc worker nhận job),
        # nên sửa note trong lúc đang index vẫn tạo được job mới.
        stmt = stmt.on_conflict_do_nothing(index_elements=[Job.dedupe_key])
    await session.execute(stmt)


async def _claim_one(session: AsyncSession) -> Job | None:
    stale = datetime.now(UTC) - timedelta(minutes=10)
    row = await session.execute(
        select(Job)
        .where(
            Job.kind.in_(list(_HANDLERS)),
            ((Job.status == "QUEUED") & (Job.run_after <= func.now()))
            | ((Job.status == "RUNNING") & (Job.locked_at < stale)),  # worker chết giữa chừng
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = row.scalar_one_or_none()
    if job is None:
        return None
    job.status, job.locked_at, job.attempts = "RUNNING", datetime.now(UTC), job.attempts + 1
    job.dedupe_key = None
    await session.commit()
    return job


async def run_one_job() -> bool:
    """Lấy và chạy 1 job. Trả False nếu hàng đợi rỗng. Dùng trực tiếp trong test."""
    maker = get_sessionmaker()
    async with maker() as session:
        job = await _claim_one(session)
    if job is None:
        return False

    set_request_id(job.request_id or job.id.hex)
    handler = _HANDLERS[job.kind]
    async with maker() as session:
        try:
            payload = {**job.payload, "_attempt": job.attempts, "_max_attempts": job.max_attempts}
            await handler(session, payload)
            await session.commit()
            status, error, run_after = "DONE", None, None
        except Exception as e:  # noqa: BLE001 — job lỗi không được làm sập worker
            await session.rollback()
            error = f"{type(e).__name__}: {str(e)[:500]}"
            if job.attempts >= job.max_attempts:
                status, run_after = "DEAD", None
                log.error("job_dead", extra={"job_id": str(job.id), "kind": job.kind})
            else:
                status = "QUEUED"
                backoff = min(2**job.attempts * 5, 600)  # 10s, 20s, 40s ... tối đa 10'
                run_after = datetime.now(UTC) + timedelta(seconds=backoff)
                log.warning("job_retry", extra={"job_id": str(job.id), "kind": job.kind,
                                                "attempt": job.attempts, "err": error})
    async with maker() as session:
        values: dict[str, Any] = {"status": status, "last_error": error, "locked_at": None}
        if run_after:
            values["run_after"] = run_after
        await session.execute(update(Job).where(Job.id == job.id).values(**values))
        await session.commit()
    set_request_id(None)
    return True


async def drain(max_jobs: int = 100) -> int:
    """Chạy hết job đang chờ (dùng trong test / script)."""
    n = 0
    while n < max_jobs and await run_one_job():
        n += 1
    return n


async def worker_loop(stop: asyncio.Event) -> None:
    interval = get_settings().worker_poll_interval_seconds
    log.info("worker_started", extra={"handlers": sorted(_HANDLERS)})
    while not stop.is_set():
        try:
            had_job = await run_one_job()
        except Exception:  # noqa: BLE001
            log.exception("worker_iteration_failed")
            had_job = False
        if not had_job:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass


async def ping_db(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))
