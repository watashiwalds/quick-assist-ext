"""Infrastructure Layer — giới hạn tần suất theo user (task H02, R03).

Cửa sổ trượt trong bộ nhớ tiến trình: đủ cho quy mô demo (1 instance API, SDS §4.5).
Chạy nhiều instance API → mỗi instance đếm riêng (giới hạn thực tế = N × limit); khi đó
thay implementation bằng Redis/PostgreSQL mà KHÔNG đổi chữ ký `check()`.
"""

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after: int  # giây (0 nếu được phép)


class SlidingWindowLimiter:
    def __init__(self, *, max_keys: int = 50_000) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._max_keys = max_keys

    def check(self, key: str, *, limit: int, window_seconds: float, now: float | None = None) -> RateDecision:
        if limit <= 0:
            return RateDecision(True, 0)
        t = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                if len(self._hits) >= self._max_keys:  # chống phình bộ nhớ: bỏ khoá cũ nhất
                    self._hits.pop(next(iter(self._hits)))
                q = self._hits[key] = deque()
            while q and q[0] <= t - window_seconds:
                q.popleft()
            if len(q) >= limit:
                return RateDecision(False, max(1, int(q[0] + window_seconds - t) + 1))
            q.append(t)
            return RateDecision(True, 0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()
