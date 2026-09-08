"""Small fixed-window rate limiter for sensitive public endpoints."""

from __future__ import annotations

from collections import defaultdict, deque
from ipaddress import ip_address
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import settings


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        trusted = ip_address(peer) in {ip_address(value) for value in settings.TRUSTED_PROXY_IPS}
    except ValueError:
        trusted = False
    if not trusted:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    candidates = [value.strip() for value in forwarded.split(",") if value.strip()]
    for value in reversed(candidates):
        try:
            if ip_address(value) not in {ip_address(item) for item in settings.TRUSTED_PROXY_IPS}:
                return value
        except ValueError:
            continue
    return peer


class RateLimiter:
    _MAX_CLIENTS = 10_000

    def __init__(self, scope: str, limit_setting: str) -> None:
        self.scope = scope
        self.limit_setting = limit_setting
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def __call__(self, request: Request) -> None:
        limit = getattr(settings, self.limit_setting)
        if limit <= 0:
            return
        now = monotonic()
        cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
        key = client_ip(request)
        with self._lock:
            if key not in self._hits and len(self._hits) >= self._MAX_CLIENTS:
                self._hits.pop(next(iter(self._hits)))
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "rate_limited", "message": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW_SECONDS)},
                )
            hits.append(now)


login_rate_limit = RateLimiter("login", "LOGIN_RATE_LIMIT")
order_create_rate_limit = RateLimiter("order-create", "ORDER_CREATE_RATE_LIMIT")
order_lookup_rate_limit = RateLimiter("order-lookup", "ORDER_LOOKUP_RATE_LIMIT")
