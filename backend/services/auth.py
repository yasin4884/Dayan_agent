from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from core.config import get_settings
from databases.mongo.users import get_user_repository

Role = Literal["admin", "user"]


def _normalize_password(password: str) -> bytes:
    """خروجی ثابت و کوتاه برای bcrypt (بدون خطای ۷۲ بایت)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def _hash_password(password: str) -> str:
    try:
        return bcrypt.hashpw(_normalize_password(password), bcrypt.gensalt()).decode("ascii")
    except Exception as exc:
        raise ValueError("رمز عبور قابل پردازش نیست. رمز دیگری انتخاب کنید.") from exc


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_normalize_password(password), password_hash.encode("ascii"))
    except Exception:
        return False


class UserStore:
    def __init__(self):
        self.repo = get_user_repository()

    def list_users(self) -> list[dict[str, Any]]:
        return self.repo.list_users()

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        return self.repo.find_by_email(email)

    def find_by_personnel_code(self, code: str) -> dict[str, Any] | None:
        return self.repo.find_by_personnel_code(code)

    def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.repo.find_by_id(user_id)

    def count_admins(self) -> int:
        return sum(1 for u in self.list_users() if u.get("role") == "admin")

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: Role = "user",
        group_id: str | None = None,
        personnel_code: str | None = None,
    ) -> dict[str, Any]:
        if self.find_by_email(email):
            raise ValueError("این ایمیل قبلاً ثبت شده است")
        code = (personnel_code or "").strip()
        if role == "user" and not code:
            raise ValueError("کد پرسنلی الزامی است")
        if code and self.find_by_personnel_code(code):
            raise ValueError("این کد پرسنلی قبلاً ثبت شده است")

        user = {
            "id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "full_name": full_name.strip() or email.strip(),
            "role": role,
            "group_id": group_id,
            "personnel_code": code or None,
            "password_hash": _hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.insert(user)
        return user

    def verify(self, email: str, password: str) -> dict[str, Any] | None:
        user = self.find_by_email(email)
        if not user:
            return None
        if not _verify_password(password, user["password_hash"]):
            return None
        return user


def create_access_token(user: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user.get("full_name", ""),
        "group_id": user.get("group_id"),
        "personnel_code": user.get("personnel_code"),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("توکن نامعتبر است") from exc


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "role": user["role"],
        "group_id": user.get("group_id"),
        "personnel_code": user.get("personnel_code"),
    }


_users: UserStore | None = None


def get_user_store() -> UserStore:
    global _users
    if _users is None:
        _users = UserStore()
    return _users
