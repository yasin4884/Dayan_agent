from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from backend.errors import AppError
from core.config import get_settings

SubjectType = Literal["user", "admin", "developer"]

# پارامترها برای CPU معمولی: امن ولی سریع
_hasher = PasswordHasher(time_cost=2, memory_cost=64 * 1024, parallelism=2)

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z\u0600-\u06FF])(?=.*\d).{8,128}$")


# --------------------------------------------------------------------------- #
# رمز عبور
# --------------------------------------------------------------------------- #
def validate_password_strength(password: str) -> None:
    """حداقل ۸ کاراکتر، شامل حرف و عدد."""
    if not _PASSWORD_RE.match(password or ""):
        raise AppError("PASSWORD_WEAK")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("$argon2"):
        try:
            return _hasher.verify(stored_hash, password)
        except (VerifyMismatchError, Exception):
            return False
    # سازگاری با هش‌های قدیمی bcrypt (رمز از قبل با sha256 کوتاه می‌شد)
    if stored_hash.startswith("$2"):
        try:
            import bcrypt

            digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
            return bcrypt.checkpw(digest, stored_hash.encode("utf-8"))
        except Exception:
            return False
    return False


def needs_rehash(stored_hash: str) -> bool:
    if not stored_hash.startswith("$argon2"):
        return True
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# توکن‌ها
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject_id: str,
    subject_type: SubjectType,
    claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    expires = _now() + timedelta(minutes=settings.jwt_access_minutes)
    payload: dict[str, Any] = {
        "sub": subject_id,
        "typ": subject_type,
        "token_use": "access",
        "iat": int(_now().timestamp()),
        "exp": int(expires.timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        if "expired" in str(exc).lower():
            raise AppError("TOKEN_EXPIRED") from exc
        raise AppError("TOKEN_INVALID") from exc
    if payload.get("token_use") != "access":
        raise AppError("TOKEN_INVALID")
    return payload


def new_refresh_token() -> tuple[str, str, datetime]:
    """(توکن خام برای کلاینت، هش برای دیتابیس، زمان انقضا)"""
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    expires = _now() + timedelta(days=settings.jwt_refresh_days)
    return raw, hash_refresh_token(raw), expires


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:60]
    return (getattr(request.client, "host", "") or "")[:60]
