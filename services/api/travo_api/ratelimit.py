"""Per-client rate limit for the sign-in endpoints (docs/06, docs/14 §7).

A sliding window in process memory: the API runs as one uvicorn process per deployment in the
pilot (ADR-022), so no shared store is needed. Horizontal scaling needs a shared store instead.

The API is not reachable from the internet; the web BFF calls it and passes the browser's
address in `X-Travo-Client-IP` (the rightmost X-Forwarded-For entry, which the platform proxy
adds). Without that header the peer address is used.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from travo_api.config import get_settings

CLIENT_IP_HEADER = "x-travo-client-ip"
WINDOW_SECONDS = 60.0


class SlidingWindow:
    def __init__(self, limit: int, window: float = WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> float:
        """Record one attempt; return 0 if allowed, else seconds until the next is allowed."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return q[0] + self.window - now
            q.append(now)
            if len(self._hits) > 10_000:  # drop idle clients so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[k]
            return 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_auth = SlidingWindow(get_settings().auth_rate_limit_per_minute)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get(CLIENT_IP_HEADER, "").strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host if request.client else "unknown"


def auth_rate_limit(request: Request) -> None:
    """FastAPI dependency for /v1/auth/*: 429 with Retry-After when a client tries too often."""
    limit = get_settings().auth_rate_limit_per_minute
    if limit <= 0:
        return
    _auth.limit = limit
    wait = _auth.hit(client_ip(request))
    if wait > 0:
        raise HTTPException(
            429, "too many sign-in attempts", headers={"Retry-After": str(int(wait) + 1)}
        )


def reset_auth_limits() -> None:
    _auth.reset()
