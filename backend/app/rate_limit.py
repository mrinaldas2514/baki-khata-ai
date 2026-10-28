"""A small in-memory rate limiter: at most N requests per time window for one key.

Keys are a client IP (login, register) or a shop (parse, transcribe). It lives in the server's
memory, so limits are per server process and reset on restart; behind several processes or a
proxy, put the limit in the proxy instead (README, "Rate limits").
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from app.config import Settings


@dataclass(frozen=True)
class Limit:
    requests: int
    window_seconds: float


class RateLimitedError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Too many requests, retry after {retry_after} s")
        self.retry_after = retry_after


class RateLimiter:
    def __init__(self, limits: dict[str, Limit], clock: Callable[[], float] = time.monotonic):
        self.limits = limits
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, name: str, key: str) -> None:
        """Count one request for (name, key); RateLimitedError if it's over the limit."""
        limit = self.limits.get(name)
        if limit is None:
            return
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault((name, key), deque())
            while hits and hits[0] <= now - limit.window_seconds:
                hits.popleft()
            if len(hits) >= limit.requests:
                raise RateLimitedError(max(1, math.ceil(hits[0] + limit.window_seconds - now)))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._forget_idle(now)

    def _forget_idle(self, now: float) -> None:
        longest = max(limit.window_seconds for limit in self.limits.values())
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - longest]:
            del self._hits[key]


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if not settings.rate_limit_enabled:
        return RateLimiter({})
    return RateLimiter(
        {
            "login": Limit(settings.rate_limit_login_per_minute, 60),
            "register": Limit(settings.rate_limit_register_per_hour, 3600),
            "parse": Limit(settings.rate_limit_parse_per_minute, 60),
            "transcribe": Limit(settings.rate_limit_transcribe_per_minute, 60),
        }
    )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate(request: Request, name: str, key: str) -> None:
    request.app.state.rate_limiter.hit(name, key)
