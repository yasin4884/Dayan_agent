from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.services.security import decode_access_token
from databases.psql.base import get_db
from databases.psql.models import AdminUser, DeveloperUser, User

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


class StaffActor:
    """ادمین یا دولوپر — برای دسترسی به مسیرهای CMS/ادمین."""

    def __init__(self, *, id: str, full_name: str, personnel_code: str, role: str, kind: str):
        self.id = id
        self.full_name = full_name
        self.personnel_code = personnel_code
        self.role = role
        self.kind = kind  # admin | developer


async def optional_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> dict[str, Any] | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        return decode_access_token(credentials.credentials)
    except AppError:
        return None


async def require_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise AppError("AUTH_REQUIRED")
    return decode_access_token(credentials.credentials)


async def current_user(
    db: DbSession,
    payload: Annotated[dict[str, Any], Depends(require_payload)],
) -> User:
    if payload.get("typ") != "user":
        raise AppError("FORBIDDEN")
    user = await db.get(User, str(payload.get("sub") or ""))
    if user is None:
        raise AppError("TOKEN_INVALID")
    if not user.is_active:
        raise AppError("ACCOUNT_DISABLED")
    return user


async def current_user_optional(
    db: DbSession,
    payload: Annotated[dict[str, Any] | None, Depends(optional_payload)] = None,
) -> User | None:
    if not payload or payload.get("typ") != "user":
        return None
    user = await db.get(User, str(payload.get("sub") or ""))
    if user is None or not user.is_active:
        return None
    return user


async def current_admin(
    db: DbSession,
    payload: Annotated[dict[str, Any], Depends(require_payload)],
) -> StaffActor:
    """ادمین یا دولوپر — هر دو به مسیرهای /admin دسترسی دارند."""
    typ = payload.get("typ")
    if typ == "admin":
        admin = await db.get(AdminUser, str(payload.get("sub") or ""))
        if admin is None:
            raise AppError("TOKEN_INVALID")
        if not admin.is_active:
            raise AppError("ACCOUNT_DISABLED")
        return StaffActor(
            id=admin.id,
            full_name=admin.full_name,
            personnel_code=admin.personnel_code,
            role=admin.role,
            kind="admin",
        )
    if typ == "developer":
        dev = await db.get(DeveloperUser, str(payload.get("sub") or ""))
        if dev is None:
            raise AppError("TOKEN_INVALID")
        if not dev.is_active:
            raise AppError("ACCOUNT_DISABLED")
        if getattr(dev, "must_change_credentials", False):
            # هنوز اجازهٔ خواندن وضعیت/عوض کردن اعتبار را دارد؛ مسیرهای سنگین در route چک می‌شوند
            pass
        return StaffActor(
            id=dev.id,
            full_name=dev.display_name or dev.username,
            personnel_code=f"dev:{dev.username}",
            role="developer",
            kind="developer",
        )
    raise AppError("ADMIN_ONLY")


async def current_developer(
    db: DbSession,
    payload: Annotated[dict[str, Any], Depends(require_payload)],
) -> DeveloperUser:
    if payload.get("typ") != "developer":
        raise AppError("FORBIDDEN", message="فقط حساب دولوپر.")
    dev = await db.get(DeveloperUser, str(payload.get("sub") or ""))
    if dev is None:
        raise AppError("TOKEN_INVALID")
    if not dev.is_active:
        raise AppError("ACCOUNT_DISABLED")
    return dev


CurrentUser = Annotated[User, Depends(current_user)]
CurrentUserOptional = Annotated["User | None", Depends(current_user_optional)]
CurrentAdmin = Annotated[StaffActor, Depends(current_admin)]
CurrentDeveloper = Annotated[DeveloperUser, Depends(current_developer)]
