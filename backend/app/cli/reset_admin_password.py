"""Interactively reset the password for one existing administrator."""

from __future__ import annotations

import argparse
import sys
from getpass import getpass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.initial_data import MIN_PASSWORD_LENGTH
from app.db.session import SessionLocal
from app.models import AdminUser


class UnknownAdminError(ValueError):
    pass


class AmbiguousAdminError(ValueError):
    pass


class PasswordMismatchError(ValueError):
    pass


def ensure_password_confirmation(password: str, confirmation: str) -> None:
    if password != confirmation:
        raise PasswordMismatchError("password confirmation does not match")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


def reset_password(db: Session, *, identifier: str, password: str) -> AdminUser:
    normalized = identifier.strip().lower()
    accounts = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == normalized)
    ).scalars().all()
    if not accounts:
        raise UnknownAdminError("no administrator matches that email")
    if len(accounts) != 1:
        raise AmbiguousAdminError("more than one administrator matches that email")

    account = accounts[0]
    account.password_hash = hash_password(password)
    db.flush()
    return account


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset an existing administrator password.")
    parser.add_argument("--email", required=True, help="Existing administrator email address.")
    args = parser.parse_args(argv)

    password = getpass("New password: ")
    confirmation = getpass("Confirm new password: ")
    try:
        ensure_password_confirmation(password, confirmation)
        with SessionLocal() as db:
            reset_password(db, identifier=args.email, password=password)
            db.commit()
    except (AmbiguousAdminError, PasswordMismatchError, UnknownAdminError, ValueError) as exc:
        print(f"Password reset refused: {exc}", file=sys.stderr)
        return 2

    print("Administrator password reset.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
