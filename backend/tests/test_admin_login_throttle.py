from __future__ import annotations

from datetime import timedelta

from app.db.base import utcnow
from app.services.admin_login_throttle import AdminLoginThrottleService


def test_third_failure_starts_a_fifteen_minute_cooldown(db) -> None:
    limiter = AdminLoginThrottleService(db)
    now = utcnow()
    for _ in range(3):
        limiter.record_failure("198.51.100.9", "admin@example.com", now=now)
    blocked = limiter.check("198.51.100.9", "admin@example.com", now=now)
    assert blocked is not None
    assert blocked.retry_after == 15 * 60


def test_expired_cooldowns_escalate_and_cap_at_sixty_minutes(db) -> None:
    limiter = AdminLoginThrottleService(db)
    now = utcnow()
    for expected_minutes in (15, 30, 60, 60):
        for _ in range(3):
            limiter.record_failure("198.51.100.9", "admin@example.com", now=now)
        blocked = limiter.check("198.51.100.9", "admin@example.com", now=now)
        assert blocked is not None and blocked.retry_after == expected_minutes * 60
        now += timedelta(minutes=expected_minutes + 1)


def test_success_clears_account_scope_but_retains_ip_abuse_history(db) -> None:
    limiter = AdminLoginThrottleService(db)
    now = utcnow()
    limiter.record_failure("198.51.100.9", "admin@example.com", now=now)
    limiter.clear_identifier("admin@example.com")
    assert limiter.check("198.51.100.9", "admin@example.com", now=now) is None
    limiter.record_failure("198.51.100.9", "other@example.com", now=now)
    limiter.record_failure("198.51.100.9", "third@example.com", now=now)
    assert limiter.check("198.51.100.9", "fourth@example.com", now=now) is not None


def test_blocked_login_skips_password_verification(client, monkeypatch) -> None:
    import app.api.v1.endpoints.auth as endpoint

    payload = {"email": "blocked@example.com", "password": "not-the-password"}
    for _ in range(3):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    monkeypatch.setattr(endpoint, "verify_password", lambda *_: (_ for _ in ()).throw(AssertionError("called")))
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 429
    assert response.headers["Retry-After"]
