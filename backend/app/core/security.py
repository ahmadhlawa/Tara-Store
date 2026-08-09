"""Password hashing and JWT access tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_password_hash = PasswordHash.recommended()  # Argon2id

TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:  # malformed/legacy hash -> treated as a failed login
        return False


def create_access_token(subject: int, role: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "type": TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != TOKEN_TYPE:
        return None
    return payload
