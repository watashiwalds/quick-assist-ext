"""QuotaService.leased(): giữ chỗ phải được hoàn với MỌI lỗi giữa reserve và commit —
không chỉ AIProviderError — kể cả khi request bị huỷ (client ngắt kết nối).

Chỉ kiểm tra luồng điều khiển của context manager (reserve/release được thay bằng bản ghi lại);
phép tính quota trên DB thật nằm ở tests/integration/business/test_quota.py.
"""

import uuid

import anyio
import anyio.lowlevel
import pytest

from quickassist.business.quota import QuotaService
from quickassist.business.quota.quota_service import QuotaLease

UID = uuid.uuid4()


def _service(released: list[str]) -> QuotaService:
    svc = QuotaService(session=None)  # type: ignore[arg-type]

    async def reserve(user_id, operation, estimate, request_id):  # type: ignore[no-untyped-def]
        return QuotaLease(user_id, request_id, estimate)

    async def release(lease: QuotaLease) -> None:
        await anyio.lowlevel.checkpoint()  # có await thật: bị huỷ ngay nếu không được shield
        released.append(lease.request_id)

    svc.reserve = reserve  # type: ignore[method-assign]
    svc.release = release  # type: ignore[method-assign]
    return svc


async def test_releases_on_non_ai_exception() -> None:
    released: list[str] = []
    svc = _service(released)
    with pytest.raises(RuntimeError, match="boom"):
        async with svc.leased(UID, "summary", 100, "r-1"):
            raise RuntimeError("boom")
    assert released == ["r-1"]


async def test_releases_when_request_is_cancelled() -> None:
    released: list[str] = []
    svc = _service(released)
    with anyio.CancelScope() as scope:
        async with svc.leased(UID, "summary", 100, "r-2"):
            scope.cancel()  # như Starlette huỷ handler khi client ngắt kết nối
            await anyio.sleep(1)  # đang chờ AI → bị huỷ tại đây
    assert scope.cancelled_caught
    assert released == ["r-2"]


async def test_does_not_release_ledger_owned_by_earlier_request() -> None:
    """request_id đã có trong ledger (request song song cùng key còn đang chạy) → lỗi ở đây không
    được release giữ chỗ của request kia, nếu không lần commit của nó thành no-op (AI miễn phí)."""
    released: list[str] = []
    svc = _service(released)

    async def reserve_existing(user_id, operation, estimate, request_id):  # type: ignore[no-untyped-def]
        return QuotaLease(user_id, request_id, estimate, is_new=False)

    svc.reserve = reserve_existing  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        async with svc.leased(UID, "summary", 100, "r-4"):
            raise RuntimeError("Conflict: key đã dùng")
    assert released == []


async def test_does_not_release_on_success() -> None:
    released: list[str] = []
    svc = _service(released)
    async with svc.leased(UID, "summary", 100, "r-3") as lease:
        assert lease.request_id == "r-3" and lease.reserved == 100
    assert released == []
