"""Persistent, shared progressive cooldowns for admin login failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from math import ceil

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import AdminLoginThrottle

_FAILURES_PER_COOLDOWN = 3
_COOLDOWN_MINUTES = (15, 30, 60)


def normalize_identifier(identifier: str) -> str:
    return identifier.strip().casefold()


def identifier_digest(identifier: str) -> str:
    return sha256(normalize_identifier(identifier).encode("utf-8")).hexdigest()


def ip_digest(ip: str) -> str:
    return sha256(ip.strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LoginBlocked:
    retry_after: int


class AdminLoginThrottleService:
    """Database rows make cooldowns survive workers, restarts, and deployments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _row(self, scope: str, key_hash: str) -> AdminLoginThrottle:
        query = select(AdminLoginThrottle).where(
            AdminLoginThrottle.scope == scope, AdminLoginThrottle.key_hash == key_hash
        ).with_for_update()
        row = self.db.execute(query).scalar_one_or_none()
        if row is not None:
            return row
        try:
            with self.db.begin_nested():
                row = AdminLoginThrottle(scope=scope, key_hash=key_hash)
                self.db.add(row)
                self.db.flush()
        except IntegrityError:
            row = self.db.execute(query).scalar_one()
        return row

    @staticmethod
    def _keys(ip: str, identifier: str) -> tuple[tuple[str, str], tuple[str, str]]:
        return (("ip", ip_digest(ip)), ("identifier", identifier_digest(identifier)))

    def check(self, ip: str, identifier: str, *, now: datetime | None = None) -> LoginBlocked | None:
        now = now or utcnow()
        retry_after = 0
        for scope, key_hash in self._keys(ip, identifier):
            row = self.db.execute(
                select(AdminLoginThrottle).where(
                    AdminLoginThrottle.scope == scope, AdminLoginThrottle.key_hash == key_hash
                )
            ).scalar_one_or_none()
            if row and row.blocked_until and row.blocked_until > now:
                retry_after = max(retry_after, ceil((row.blocked_until - now).total_seconds()))
        return LoginBlocked(retry_after) if retry_after else None

    def record_failure(self, ip: str, identifier: str, *, now: datetime | None = None) -> int | None:
        now = now or utcnow()
        longest_cooldown: int | None = None
        for scope, key_hash in self._keys(ip, identifier):
            row = self._row(scope, key_hash)
            if row.blocked_until and row.blocked_until <= now:
                row.blocked_until = None
                row.failures = 0
            row.failures += 1
            if row.failures >= _FAILURES_PER_COOLDOWN:
                minutes = _COOLDOWN_MINUTES[min(row.cooldown_level, len(_COOLDOWN_MINUTES) - 1)]
                row.cooldown_level = min(row.cooldown_level + 1, len(_COOLDOWN_MINUTES) - 1)
                row.failures = 0
                row.blocked_until = now + timedelta(minutes=minutes)
                longest_cooldown = max(longest_cooldown or 0, minutes)
        return longest_cooldown

    def clear_identifier(self, identifier: str) -> None:
        """A valid login clears only that identifier; IP-wide abuse remains protected."""
        self.db.execute(
            delete(AdminLoginThrottle).where(
                AdminLoginThrottle.scope == "identifier",
                AdminLoginThrottle.key_hash == identifier_digest(identifier),
            )
        )
