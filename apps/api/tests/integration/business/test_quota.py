"""A04 — Quota: reserve/commit/release nguyên tử, chạy song song không vượt hạn mức,
ledger request_id chống trừ trùng, không âm, hoàn giữ chỗ bị treo."""

import asyncio
import uuid

import pytest

from quickassist.business.common.exceptions import Conflict, QuotaExceeded
from quickassist.business.quota import QuotaService
from tests.conftest import login

pytestmark = pytest.mark.integration


async def _user(client, email: str = "q@x.vn") -> uuid.UUID:  # type: ignore[no-untyped-def]
    h = await login(client, email)
    return uuid.UUID((await client.get("/me", headers=h)).json()["id"])


async def _status(uid: uuid.UUID):  # type: ignore[no-untyped-def]
    async with QuotaService.open() as q:
        return await q.status(uid)


async def test_reserve_commit_release_math(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "quota_default_tokens", 1000)
    uid = await _user(client)
    async with QuotaService.open() as q:
        a = await q.reserve(uid, "summary", 300, "r-a")
        b = await q.reserve(uid, "summary", 200, "r-b")
    st = await _status(uid)
    assert (st.used_tokens, st.reserved_tokens, st.remaining) == (0, 500, 500)
    async with QuotaService.open() as q:
        await q.commit(a, 120)  # dùng thật ít hơn ước tính → phần dư trả lại
        await q.release(b)
    st = await _status(uid)
    assert (st.used_tokens, st.reserved_tokens, st.remaining) == (120, 0, 880)


async def test_concurrent_reservations_never_exceed_limit(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "quota_default_tokens", 500)
    uid = await _user(client)
    await _status(uid)  # tạo tài khoản quota trước

    async def one(i: int) -> bool:
        async with QuotaService.open() as q:
            try:
                await q.reserve(uid, "search", 100, f"race-{i}")
                return True
            except QuotaExceeded:
                return False

    results = await asyncio.gather(*(one(i) for i in range(20)))
    assert sum(results) == 5  # đúng 500 / 100
    st = await _status(uid)
    assert st.reserved_tokens == 500 and st.remaining == 0


async def test_settle_is_idempotent_per_request_id(client) -> None:
    uid = await _user(client)
    async with QuotaService.open() as q:
        lease = await q.reserve(uid, "embed_note", 50, "dup-1")
        await q.commit(lease, 40)
        await q.commit(lease, 40)  # gọi lại (retry) → không trừ thêm
        await q.release(lease)  # release sau commit → bỏ qua
        again = await q.reserve(uid, "embed_note", 50, "dup-1")  # cùng request_id
    assert again.already_settled and not again.is_new
    async with QuotaService.open() as q:
        await q.commit(again, 999)
    st = await _status(uid)
    assert st.used_tokens == 40 and st.reserved_tokens == 0


async def test_request_id_cannot_be_borrowed_by_another_user(client) -> None:
    a, b = await _user(client, "a@x.vn"), await _user(client, "b@x.vn")
    async with QuotaService.open() as q:
        await q.reserve(a, "summary", 10, "shared-key")
        with pytest.raises(Conflict):
            await q.reserve(b, "summary", 10, "shared-key")


async def test_exceeded_raises_and_leaves_no_ledger(client, monkeypatch) -> None:
    from quickassist.infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "quota_default_tokens", 10)
    uid = await _user(client)
    async with QuotaService.open() as q:
        with pytest.raises(QuotaExceeded):
            await q.reserve(uid, "summary", 11, "too-big")
        # request_id không bị "đốt": lần sau đủ quota vẫn dùng được
    monkeypatch.setattr(get_settings(), "quota_default_tokens", 10)
    st = await _status(uid)
    assert st.used_tokens == st.reserved_tokens == 0


async def test_stale_reservations_are_released(client) -> None:
    from sqlalchemy import text

    from quickassist.data.database import get_engine

    uid = await _user(client)
    async with QuotaService.open() as q:
        await q.reserve(uid, "embed_note", 70, "stuck-1")
        fresh = await q.reserve(uid, "embed_note", 30, "fresh-1")
    async with get_engine().begin() as conn:
        await conn.execute(text("UPDATE quota_ledger SET created_at = now() - interval '1 hour' "
                                "WHERE request_id = 'stuck-1'"))
    async with QuotaService.open() as q:
        assert await q.release_stale(older_than_minutes=15) == 1
        assert await q.release_stale(older_than_minutes=15) == 0
    st = await _status(uid)
    assert st.reserved_tokens == 30
    async with QuotaService.open() as q:
        await q.commit(fresh, 30)
    assert (await _status(uid)).used_tokens == 30


async def test_quota_endpoint(client) -> None:
    h = await login(client)
    r = (await client.get("/me/quota", headers=h)).json()
    assert r == {"limit_tokens": 200_000, "used_tokens": 0, "reserved_tokens": 0, "remaining_tokens": 200_000}
