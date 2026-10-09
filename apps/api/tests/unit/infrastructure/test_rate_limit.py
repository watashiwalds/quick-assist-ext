"""H02/R03 — cửa sổ trượt theo user."""

from quickassist.infrastructure.rate_limit import SlidingWindowLimiter


def test_blocks_after_limit_and_recovers_after_window() -> None:
    lim = SlidingWindowLimiter()
    assert all(lim.check("u", limit=3, window_seconds=60, now=t).allowed for t in (0, 1, 2))
    d = lim.check("u", limit=3, window_seconds=60, now=3)
    assert not d.allowed and 1 <= d.retry_after <= 60
    assert lim.check("u", limit=3, window_seconds=60, now=61).allowed


def test_keys_are_independent_and_zero_disables() -> None:
    lim = SlidingWindowLimiter()
    lim.check("a", limit=1, window_seconds=60, now=0)
    assert lim.check("b", limit=1, window_seconds=60, now=0).allowed
    assert all(lim.check("c", limit=0, window_seconds=60).allowed for _ in range(100))


def test_bounded_memory() -> None:
    lim = SlidingWindowLimiter(max_keys=10)
    for i in range(100):
        lim.check(f"k{i}", limit=5, window_seconds=60, now=0)
    assert len(lim._hits) <= 10
