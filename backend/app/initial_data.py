"""Create or update the initial admin account.

Credentials come from the command line or the environment — never from source. The
command refuses to invent a password, so an instance that was never configured has no
usable admin account.

    python -m app.initial_data --email owner@example.com --password '...' --role super_admin
    INITIAL_ADMIN_EMAIL=... INITIAL_ADMIN_PASSWORD=... python -m app.initial_data
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AdminRole
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AdminUser

MIN_PASSWORD_LENGTH = 10


def upsert_admin(
    db: Session, *, email: str, password: str, full_name: str, role: str
) -> tuple[AdminUser, bool]:
    """Idempotent: running it again resets the password of the same account."""
    normalized = email.strip().lower()
    account = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == normalized)
    ).scalar_one_or_none()

    created = account is None
    if account is None:
        account = AdminUser(email=normalized, full_name=full_name, role=role)
        db.add(account)
    else:
        account.full_name = full_name
        account.role = role
    account.password_hash = hash_password(password)
    account.is_active = True
    db.flush()
    return account, created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the initial admin account.")
    parser.add_argument("--email", default=settings.INITIAL_ADMIN_EMAIL)
    parser.add_argument("--password", default=settings.INITIAL_ADMIN_PASSWORD)
    parser.add_argument("--name", default=settings.INITIAL_ADMIN_NAME)
    parser.add_argument(
        "--role",
        default=AdminRole.SUPER_ADMIN.value,
        choices=[role.value for role in AdminRole],
    )
    args = parser.parse_args(argv)

    if not args.email or not args.password:
        parser.error(
            "an email and a password are required "
            "(pass --email/--password or set INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD)"
        )
    if len(args.password) < MIN_PASSWORD_LENGTH:
        parser.error(f"the password must be at least {MIN_PASSWORD_LENGTH} characters")

    with SessionLocal() as db:
        account, created = upsert_admin(
            db,
            email=args.email,
            password=args.password,
            full_name=args.name,
            role=args.role,
        )
        db.commit()
        action = "Created" if created else "Updated"
        print(f"{action} admin {account.email} with role {account.role}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
