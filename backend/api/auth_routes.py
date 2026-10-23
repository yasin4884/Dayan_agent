from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from backend.api.deps import CurrentAdmin, CurrentUser, DbSession
from backend.api.schemas import (
    AdminLoginRequest,
    AdminRegisterRequest,
    ChangePasswordRequest,
    GroupCreateRequest,
    GroupUpdateRequest,
    LoginRequest,
    RefreshRequest,
    RegisterUserRequest,
    TokenResponse,
)
from backend.errors import AppError
from backend.services import accounts
from backend.services.audit import log_audit
from backend.services.rate_limit import limit_login, limit_register
from backend.services.security import client_ip
from databases.psql.models import Group

router = APIRouter(tags=["auth"])


# --------------------------------------------------------------------------- #
# گروه‌ها (عمومی برای فرم ثبت‌نام)
# --------------------------------------------------------------------------- #
@router.get("/public/groups")
async def public_groups(db: DbSession) -> list[dict[str, Any]]:
    groups = await accounts.list_groups(db, only_active=True)
    if not groups:
        groups = [await accounts.ensure_default_group(db)]
        await db.commit()
    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "sort_order": g.sort_order,
        }
        for g in groups
    ]


@router.get("/auth/status")
async def auth_status(db: DbSession) -> dict[str, Any]:
    from core.config import get_settings

    settings = get_settings()
    admins = await accounts.count_admins(db)
    # فقط در محیط توسعه — DEBUG به‌تنهایی در production کافی نیست
    can_recover = settings.app_env.lower() in {"development", "dev", "local", "test"}
    return {
        "has_admin": admins > 0,
        "needs_admin_setup": admins == 0,
        "can_recover_admin": can_recover,
        "db_engine": "sqlite" if "sqlite" in (settings.postgres_dsn or "") or settings.db_fallback_sqlite else "postgres",
    }


# --------------------------------------------------------------------------- #
# کاربر
# --------------------------------------------------------------------------- #
@router.post("/auth/register", response_model=TokenResponse)
async def register_user(body: RegisterUserRequest, request: Request, db: DbSession):
    await limit_register(request)
    # اگر گروهی نبود، پیش‌فرض بساز
    await accounts.ensure_default_group(db)
    user = await accounts.register_user(
        db,
        first_name=body.first_name,
        last_name=body.last_name,
        username=body.username,
        student_code=body.student_code,
        password=body.password,
        password_confirm=body.password_confirm,
        group_id=body.group_id,
    )
    tokens = await accounts.issue_session(
        db,
        subject_id=user.id,
        subject_type="user",
        claims={
            "group_id": user.group_id,
            "username": user.username,
            "name": user.full_name,
        },
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "user.register",
        actor_id=user.id,
        actor_type="user",
        ip=client_ip(request),
        target=user.username,
    )
    group = await accounts.get_group(db, user.group_id or "") if user.group_id else None
    return TokenResponse(
        **tokens,
        user=accounts.public_user(user, group.name if group else None),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login_user(body: LoginRequest, request: Request, db: DbSession):
    await limit_login(request, identity=body.identifier)
    try:
        user = await accounts.authenticate_user(db, body.identifier, body.password)
    except AppError as exc:
        await log_audit(
            "user.login",
            actor_type="anonymous",
            ip=client_ip(request),
            status="fail",
            target=body.identifier,
            detail={"error": exc.error_code},
        )
        raise

    tokens = await accounts.issue_session(
        db,
        subject_id=user.id,
        subject_type="user",
        claims={
            "group_id": user.group_id,
            "username": user.username,
            "name": user.full_name,
        },
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "user.login",
        actor_id=user.id,
        actor_type="user",
        ip=client_ip(request),
        target=user.username,
    )
    group = await accounts.get_group(db, user.group_id or "") if user.group_id else None
    return TokenResponse(
        **tokens,
        user=accounts.public_user(user, group.name if group else None),
    )


@router.get("/auth/me")
async def me(user: CurrentUser, db: DbSession) -> dict[str, Any]:
    group = await accounts.get_group(db, user.group_id or "") if user.group_id else None
    return accounts.public_user(user, group.name if group else None)


@router.post("/auth/change-password")
async def change_user_password(
    body: ChangePasswordRequest,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """عوض کردن رمز دانشجو."""
    await accounts.change_user_password(
        db,
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
        new_password_confirm=body.new_password_confirm,
    )
    await log_audit(
        "user.change_password",
        actor_id=user.id,
        actor_type="user",
        ip=client_ip(request),
        target=user.username,
    )
    return {"ok": True, "message": "رمز عبور به‌روز شد."}


# --------------------------------------------------------------------------- #
# ادمین — مسیر جدا
# --------------------------------------------------------------------------- #
@router.post("/admin/auth/setup", response_model=TokenResponse)
async def setup_first_admin(body: AdminRegisterRequest, request: Request, db: DbSession):
    """فقط وقتی هیچ ادمینی نیست کار می‌کند (راه‌اندازی اولیه)."""
    await limit_register(request)
    if await accounts.count_admins(db) > 0:
        raise AppError("ALREADY_EXISTS", message="ادمین قبلاً ساخته شده است.")
    admin = await accounts.register_admin(
        db,
        full_name=body.full_name,
        personnel_code=body.personnel_code,
        password=body.password,
        password_confirm=body.password_confirm,
        role="admin",
    )
    tokens = await accounts.issue_session(
        db,
        subject_id=admin.id,
        subject_type="admin",
        claims={"role": admin.role, "name": admin.full_name},
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "admin.setup",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=admin.personnel_code,
    )
    return TokenResponse(**tokens, user=accounts.public_admin(admin))


@router.post("/admin/auth/signup", response_model=TokenResponse)
async def admin_signup(body: AdminRegisterRequest, request: Request, db: DbSession):
    """ثبت‌نام ادمین از صفحه ورود — بدون نیاز به لاگین قبلی."""
    await limit_register(request)
    admin = await accounts.register_admin(
        db,
        full_name=body.full_name,
        personnel_code=body.personnel_code,
        password=body.password,
        password_confirm=body.password_confirm,
        role="admin",
    )
    tokens = await accounts.issue_session(
        db,
        subject_id=admin.id,
        subject_type="admin",
        claims={"role": admin.role, "name": admin.full_name},
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "admin.signup",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=admin.personnel_code,
    )
    return TokenResponse(**tokens, user=accounts.public_admin(admin))


@router.post("/admin/auth/register")
async def register_admin(
    body: AdminRegisterRequest,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    """ثبت‌نام ادمین جدید فقط توسط ادمین فعلی."""
    await limit_register(request)
    created = await accounts.register_admin(
        db,
        full_name=body.full_name,
        personnel_code=body.personnel_code,
        password=body.password,
        password_confirm=body.password_confirm,
        role="admin",
    )
    await log_audit(
        "admin.register",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=created.personnel_code,
    )
    return {"user": accounts.public_admin(created)}


@router.post("/admin/auth/login", response_model=TokenResponse)
async def login_admin(body: AdminLoginRequest, request: Request, db: DbSession):
    await limit_login(request, identity=f"admin:{body.personnel_code}")
    try:
        admin = await accounts.authenticate_admin(db, body.personnel_code, body.password)
    except AppError as exc:
        await log_audit(
            "admin.login",
            actor_type="anonymous",
            ip=client_ip(request),
            status="fail",
            target=body.personnel_code,
            detail={"error": exc.error_code},
        )
        raise

    tokens = await accounts.issue_session(
        db,
        subject_id=admin.id,
        subject_type="admin",
        claims={"role": admin.role, "name": admin.full_name},
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "admin.login",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=admin.personnel_code,
    )
    return TokenResponse(**tokens, user=accounts.public_admin(admin))


@router.post("/admin/auth/change-password")
async def change_admin_password(
    body: ChangePasswordRequest,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    """عوض کردن رمز ادمین واردشده."""
    if admin.kind != "admin":
        raise AppError("FORBIDDEN", message="از مسیر دولوپر برای عوض کردن اعتبار استفاده کن.")
    from databases.psql.models import AdminUser

    row = await db.get(AdminUser, admin.id)
    if row is None:
        raise AppError("TOKEN_INVALID")
    await accounts.change_admin_password(
        db,
        admin=row,
        current_password=body.current_password,
        new_password=body.new_password,
        new_password_confirm=body.new_password_confirm,
    )
    await log_audit(
        "admin.change_password",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=admin.personnel_code,
    )
    return {"ok": True, "message": "رمز عبور به‌روز شد."}


@router.post("/admin/auth/recover", response_model=TokenResponse)
async def recover_admin(body: AdminRegisterRequest, request: Request, db: DbSession):
    """فقط در محیط توسعه: بازنشانی/ساخت ادمین."""
    from core.config import get_settings

    settings = get_settings()
    if settings.app_env.lower() not in {"development", "dev", "local", "test"}:
        raise AppError("FORBIDDEN", message="بازنشانی رمز در این محیط فعال نیست.")
    await limit_register(request)
    admin = await accounts.reset_admin_password(
        db,
        personnel_code=body.personnel_code,
        password=body.password,
        password_confirm=body.password_confirm,
        full_name=body.full_name,
    )
    tokens = await accounts.issue_session(
        db,
        subject_id=admin.id,
        subject_type="admin",
        claims={"role": admin.role, "name": admin.full_name},
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "admin.recover",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=admin.personnel_code,
    )
    return TokenResponse(**tokens, user=accounts.public_admin(admin))


@router.get("/admin/auth/me")
async def admin_me(admin: CurrentAdmin) -> dict[str, Any]:
    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "personnel_code": admin.personnel_code,
        "role": admin.role,
        "kind": admin.kind,
    }


# --------------------------------------------------------------------------- #
# رفرش / خروج
# --------------------------------------------------------------------------- #
@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_tokens(body: RefreshRequest, request: Request, db: DbSession):
    tokens, subject_id, subject_type = await accounts.rotate_session(
        db,
        raw_refresh=body.refresh_token,
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    user_payload: dict[str, Any] | None = None
    if subject_type == "user":
        from databases.psql.models import User

        user = await db.get(User, subject_id)
        if user:
            group = await accounts.get_group(db, user.group_id or "") if user.group_id else None
            user_payload = accounts.public_user(user, group.name if group else None)
    elif subject_type == "developer":
        from databases.psql.models import DeveloperUser

        dev = await db.get(DeveloperUser, subject_id)
        if dev:
            user_payload = accounts.public_developer(dev)
    else:
        from databases.psql.models import AdminUser

        admin = await db.get(AdminUser, subject_id)
        if admin:
            user_payload = accounts.public_admin(admin)
    return TokenResponse(**tokens, user=user_payload)


@router.post("/auth/logout")
async def logout(body: RefreshRequest, request: Request, db: DbSession) -> dict[str, str]:
    await accounts.revoke_session(db, body.refresh_token)
    await log_audit("auth.logout", actor_type="anonymous", ip=client_ip(request))
    return {"message": "با موفقیت خارج شدید."}


# --------------------------------------------------------------------------- #
# مدیریت گروه‌ها (ادمین)
# --------------------------------------------------------------------------- #
@router.get("/admin/groups")
async def admin_list_groups(db: DbSession, _: CurrentAdmin) -> list[dict[str, Any]]:
    groups = await accounts.list_groups(db, only_active=False)
    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in groups
    ]


@router.post("/admin/groups")
async def admin_create_group(
    body: GroupCreateRequest,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    exists = await db.scalar(select(Group).where(Group.name == body.name))
    if exists is not None:
        raise AppError("ALREADY_EXISTS", message="گروهی با این نام وجود دارد.")
    group = Group(
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(group)
    await db.flush()
    await log_audit(
        "group.create",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=group.id,
        detail={"name": group.name},
    )
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "sort_order": group.sort_order,
        "is_active": group.is_active,
    }


@router.patch("/admin/groups/{group_id}")
async def admin_update_group(
    group_id: str,
    body: GroupUpdateRequest,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    group = await db.get(Group, group_id)
    if group is None:
        raise AppError("NOT_FOUND")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(group, key, value)
    await db.flush()
    await log_audit(
        "group.update",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=group.id,
        detail=data,
    )
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "sort_order": group.sort_order,
        "is_active": group.is_active,
    }
