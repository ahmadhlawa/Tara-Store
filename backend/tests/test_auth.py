from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AdminRole
from app.initial_data import main as initial_data_main
from app.initial_data import upsert_admin
from app.models import AdminUser
from app.cli.reset_admin_password import (
    PasswordMismatchError,
    UnknownAdminError,
    ensure_password_confirmation,
    reset_password,
)
from app.core.security import verify_password
from app.core.config import settings
from app.core.rate_limit import login_rate_limit
from tests.conftest import ADMIN_EMAIL, TEST_PASSWORD, auth, login, make_admin


def test_initial_admin_creation_is_idempotent(db: Session) -> None:
    account, created = upsert_admin(
        db,
        email="Owner@Example.com",
        password=TEST_PASSWORD,
        full_name="Owner",
        role=AdminRole.SUPER_ADMIN.value,
    )
    db.commit()
    assert created is True
    assert account.email == "owner@example.com"
    first_hash = account.password_hash

    account, created = upsert_admin(
        db,
        email="owner@example.com",
        password="AnotherPassw0rd!",
        full_name="Owner",
        role=AdminRole.SUPER_ADMIN.value,
    )
    db.commit()
    assert created is False
    assert account.password_hash != first_hash
    assert db.query(AdminUser).count() == 1


def test_initial_admin_command_refuses_a_short_password(capsys) -> None:
    try:
        initial_data_main(["--email", "a@b.test", "--password", "short"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - the command must not accept a weak password
        raise AssertionError("expected the command to reject a short password")


def test_reset_admin_password_preserves_account_state(db: Session, super_admin: AdminUser) -> None:
    reset_password(db, identifier=super_admin.email.upper(), password="ResetPassw0rd!42")
    db.commit()
    db.refresh(super_admin)

    assert verify_password("ResetPassw0rd!42", super_admin.password_hash)
    assert super_admin.role == AdminRole.SUPER_ADMIN.value
    assert super_admin.is_active is True


def test_reset_admin_password_rejects_unknown_identifier(db: Session) -> None:
    with pytest.raises(UnknownAdminError):
        reset_password(db, identifier="missing@example.com", password="ResetPassw0rd!42")


def test_reset_admin_password_rejects_mismatched_confirmation() -> None:
    with pytest.raises(PasswordMismatchError):
        ensure_password_confirmation("ResetPassw0rd!42", "different-password")


def test_login_succeeds_and_records_the_login_time(
    client: TestClient, db: Session, normal_admin: AdminUser
) -> None:
    assert normal_admin.last_login_at is None
    token = login(client, ADMIN_EMAIL)

    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == ADMIN_EMAIL
    assert "password" not in body and "password_hash" not in body

    db.expire_all()
    assert db.get(AdminUser, normal_admin.id).last_login_at is not None


def test_login_failure_is_generic(client: TestClient, normal_admin: AdminUser) -> None:
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "not-the-password"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": TEST_PASSWORD}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_disabled_admin_cannot_log_in(client: TestClient, db: Session) -> None:
    make_admin(db, email="disabled@example.com", is_active=False)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_is_rate_limited(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", 2)
    login_rate_limit._hits.clear()
    payload = {"email": "nobody@example.com", "password": TEST_PASSWORD}
    assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    limited = client.post("/api/v1/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["Retry-After"] == str(settings.RATE_LIMIT_WINDOW_SECONDS)
    login_rate_limit._hits.clear()


def test_a_token_stops_working_once_the_admin_is_deactivated(
    client: TestClient, db: Session, normal_admin: AdminUser
) -> None:
    token = login(client, ADMIN_EMAIL)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200

    db.get(AdminUser, normal_admin.id).is_active = False
    db.commit()

    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_admin_endpoints_require_a_token(client: TestClient) -> None:
    assert client.get("/api/v1/admin/products").status_code == 401
    assert client.get("/api/v1/admin/dashboard").status_code == 401


def test_garbage_and_tampered_tokens_are_rejected(client: TestClient, admin_token: str) -> None:
    assert client.get("/api/v1/auth/me", headers=auth("not-a-jwt")).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth(admin_token + "x")).status_code == 401


def test_normal_admin_cannot_manage_admin_accounts_or_audit_logs(
    client: TestClient, admin_token: str
) -> None:
    for path in ("/api/v1/admin/admins", "/api/v1/admin/audit-logs"):
        response = client.get(path, headers=auth(admin_token))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    created = client.post(
        "/api/v1/admin/admins",
        headers=auth(admin_token),
        json={
            "email": "new@example.com",
            "full_name": "New Admin",
            "password": "AnotherPassw0rd!",
            "role": "super_admin",
        },
    )
    assert created.status_code == 403


def test_super_admin_can_manage_admin_accounts(client: TestClient, super_token: str) -> None:
    created = client.post(
        "/api/v1/admin/admins",
        headers=auth(super_token),
        json={
            "email": "new@example.com",
            "full_name": "New Admin",
            "password": "AnotherPassw0rd!",
            "role": "admin",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["role"] == "admin"
    assert "password_hash" not in body

    new_id = body["id"]
    updated = client.patch(
        f"/api/v1/admin/admins/{new_id}",
        headers=auth(super_token),
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    duplicate = client.post(
        "/api/v1/admin/admins",
        headers=auth(super_token),
        json={
            "email": "new@example.com",
            "full_name": "Dup",
            "password": "AnotherPassw0rd!",
        },
    )
    assert duplicate.status_code == 409

    deleted = client.delete(f"/api/v1/admin/admins/{new_id}", headers=auth(super_token))
    assert deleted.status_code == 200


def test_super_admin_cannot_lock_itself_out(
    client: TestClient, super_token: str, super_admin: AdminUser
) -> None:
    disable_self = client.patch(
        f"/api/v1/admin/admins/{super_admin.id}",
        headers=auth(super_token),
        json={"is_active": False},
    )
    assert disable_self.status_code == 400
    assert disable_self.json()["error"]["code"] == "cannot_disable_self"

    delete_self = client.delete(
        f"/api/v1/admin/admins/{super_admin.id}", headers=auth(super_token)
    )
    assert delete_self.status_code == 400
