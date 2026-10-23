from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.services.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    validate_password_strength,
    verify_password,
)
from core.text_utils import normalize_identifier, normalize_text
from databases.psql.models import AdminUser, DeveloperUser, Group, RefreshToken, User

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# گروه‌ها
# --------------------------------------------------------------------------- #
async def list_groups(db: AsyncSession, only_active: bool = True) -> list[Group]:
    stmt = select(Group)
    if only_active:
        stmt = stmt.where(Group.is_active.is_(True))
    stmt = stmt.order_by(Group.sort_order, Group.name)
    return list((await db.scalars(stmt)).all())


async def ensure_default_group(db: AsyncSession) -> Group:
    """اگر هیچ گروه فعالی نبود، «گروه عمومی» می‌سازد تا ثبت‌نام گیر نکند."""
    groups = await list_groups(db, only_active=True)
    if groups:
        return groups[0]
    any_group = await db.scalar(select(Group).order_by(Group.sort_order, Group.name).limit(1))
    if any_group is not None:
        any_group.is_active = True
        await db.flush()
        return any_group
    group = Group(name="گروه عمومی", description="گروه پیش‌فرض", is_active=True, sort_order=0)
    db.add(group)
    await db.flush()
    logger.info("گروه پیش‌فرض ساخته شد: %s", group.id)
    return group


async def get_group(db: AsyncSession, group_id: str) -> Group | None:
    return await db.get(Group, group_id)


# --------------------------------------------------------------------------- #
# نمایش
# --------------------------------------------------------------------------- #
def public_user(user: User, group_name: str | None = None) -> dict[str, Any]:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "username": user.username,
        "student_code": user.student_code,
        "group_id": user.group_id,
        "group_name": group_name,
        "role": "user",
        "is_active": user.is_active,
    }


def public_admin(admin: AdminUser) -> dict[str, Any]:
    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "personnel_code": admin.personnel_code,
        "role": admin.role,
        "is_active": admin.is_active,
    }


# --------------------------------------------------------------------------- #
# ثبت‌نام کاربر
# --------------------------------------------------------------------------- #
async def register_user(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    username: str,
    student_code: str,
    password: str,
    password_confirm: str,
    group_id: str,
) -> User:
    if password != password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(password)

    username = normalize_identifier(username)
    student_code = normalize_identifier(student_code)

    if not group_id:
        raise AppError("GROUP_REQUIRED")
    group = await get_group(db, group_id)
    if group is None or not group.is_active:
        raise AppError("GROUP_INVALID")

    existing = await db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise AppError("USERNAME_TAKEN")
    existing = await db.scalar(select(User).where(User.student_code == student_code))
    if existing is not None:
        raise AppError("STUDENT_CODE_TAKEN")

    user = User(
        first_name=normalize_text(first_name),
        last_name=normalize_text(last_name),
        username=username,
        student_code=student_code,
        password_hash=hash_password(password),
        group_id=group.id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, identifier: str, password: str) -> User:
    """ورود با نام کاربری یا کد دانشجویی."""
    key = normalize_identifier(identifier)
    if not key:
        raise AppError("INVALID_CREDENTIALS")

    user = await db.scalar(
        select(User).where(or_(User.username == key, User.student_code == key))
    )
    if user is None or not verify_password(password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS")
    if not user.is_active:
        raise AppError("ACCOUNT_DISABLED")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = _now()
    await db.flush()
    return user


# --------------------------------------------------------------------------- #
# ادمین
# --------------------------------------------------------------------------- #
async def count_admins(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(AdminUser)) or 0)


async def register_admin(
    db: AsyncSession,
    *,
    full_name: str,
    personnel_code: str,
    password: str,
    password_confirm: str,
    role: str = "admin",
) -> AdminUser:
    if password != password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(password)

    personnel_code = normalize_identifier(personnel_code)
    existing = await db.scalar(
        select(AdminUser).where(AdminUser.personnel_code == personnel_code)
    )
    if existing is not None:
        raise AppError("PERSONNEL_CODE_TAKEN")

    admin = AdminUser(
        full_name=normalize_text(full_name),
        personnel_code=personnel_code,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def authenticate_admin(db: AsyncSession, personnel_code: str, password: str) -> AdminUser:
    key = normalize_identifier(personnel_code)
    if not key:
        raise AppError("INVALID_CREDENTIALS")

    admin = await db.scalar(select(AdminUser).where(AdminUser.personnel_code == key))
    if admin is None or not verify_password(password, admin.password_hash):
        raise AppError("INVALID_CREDENTIALS")
    if not admin.is_active:
        raise AppError("ACCOUNT_DISABLED")

    if needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(password)
    admin.last_login_at = _now()
    await db.flush()
    return admin


async def reset_admin_password(
    db: AsyncSession,
    *,
    personnel_code: str,
    password: str,
    password_confirm: str,
    full_name: str = "",
) -> AdminUser:
    """بازنشانی رمز ادمین موجود، یا ساخت ادمین اگر نبود (فقط برای حالت توسعه)."""
    if password != password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(password)
    key = normalize_identifier(personnel_code)
    if not key:
        raise AppError("VALIDATION_ERROR", message="شماره پرسنلی لازم است.")
    admin = await db.scalar(select(AdminUser).where(AdminUser.personnel_code == key))
    if admin is None:
        admin = AdminUser(
            full_name=normalize_text(full_name) or "ادمین",
            personnel_code=key,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
    else:
        admin.password_hash = hash_password(password)
        admin.is_active = True
        if full_name.strip():
            admin.full_name = normalize_text(full_name)
    await db.flush()
    return admin


async def change_admin_password(
    db: AsyncSession,
    *,
    admin: AdminUser,
    current_password: str,
    new_password: str,
    new_password_confirm: str,
) -> AdminUser:
    if new_password != new_password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(new_password)
    if not verify_password(current_password, admin.password_hash):
        raise AppError("WRONG_PASSWORD")
    admin.password_hash = hash_password(new_password)
    await db.flush()
    return admin


async def change_user_password(
    db: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
    new_password_confirm: str,
) -> User:
    if new_password != new_password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(new_password)
    if not verify_password(current_password, user.password_hash):
        raise AppError("WRONG_PASSWORD")
    user.password_hash = hash_password(new_password)
    await db.flush()
    return user


# --------------------------------------------------------------------------- #
# دولوپر
# --------------------------------------------------------------------------- #
BOOTSTRAP_DEV_USER = "developer"
BOOTSTRAP_DEV_PASS = "ChangeMe@1234"


def public_developer(dev: DeveloperUser) -> dict[str, Any]:
    return {
        "id": dev.id,
        "username": dev.username,
        "display_name": dev.display_name,
        "role": "developer",
        "must_change_credentials": bool(dev.must_change_credentials),
        "is_active": dev.is_active,
    }


async def count_developers(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(DeveloperUser)) or 0)


async def ensure_bootstrap_developer(db: AsyncSession) -> DeveloperUser:
    """اگر هیچ دولوپری نبود، اکانت پیش‌ساخته می‌سازد."""
    existing = await db.scalar(select(DeveloperUser).order_by(DeveloperUser.created_at).limit(1))
    if existing is not None:
        return existing
    dev = DeveloperUser(
        username=BOOTSTRAP_DEV_USER,
        display_name="Developer",
        password_hash=hash_password(BOOTSTRAP_DEV_PASS),
        must_change_credentials=True,
        is_active=True,
    )
    db.add(dev)
    await db.flush()
    logger.info("اکانت پیش‌ساخته دولوپر ساخته شد: %s", BOOTSTRAP_DEV_USER)
    return dev


async def authenticate_developer(db: AsyncSession, username: str, password: str) -> DeveloperUser:
    key = normalize_identifier(username)
    await ensure_bootstrap_developer(db)
    dev = await db.scalar(select(DeveloperUser).where(DeveloperUser.username == key))
    if dev is None or not verify_password(password, dev.password_hash):
        raise AppError("INVALID_CREDENTIALS")
    if not dev.is_active:
        raise AppError("ACCOUNT_DISABLED")
    if needs_rehash(dev.password_hash):
        dev.password_hash = hash_password(password)
    dev.last_login_at = _now()
    await db.flush()
    return dev


async def change_developer_credentials(
    db: AsyncSession,
    *,
    dev: DeveloperUser,
    current_password: str,
    new_username: str | None,
    new_password: str,
    new_password_confirm: str,
) -> DeveloperUser:
    if not verify_password(current_password, dev.password_hash):
        raise AppError("WRONG_PASSWORD")
    if new_password != new_password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(new_password)
    if new_username:
        uname = normalize_identifier(new_username)
        if len(uname) < 3:
            raise AppError("VALIDATION_ERROR", message="نام کاربری حداقل ۳ کاراکتر.")
        other = await db.scalar(
            select(DeveloperUser).where(DeveloperUser.username == uname, DeveloperUser.id != dev.id)
        )
        if other is not None:
            raise AppError("USERNAME_TAKEN", message="این نام کاربری قبلاً ثبت شده.")
        dev.username = uname
    dev.password_hash = hash_password(new_password)
    dev.must_change_credentials = False
    await db.flush()
    return dev


async def create_developer(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    password_confirm: str,
    display_name: str = "",
) -> DeveloperUser:
    if password != password_confirm:
        raise AppError("PASSWORD_MISMATCH")
    validate_password_strength(password)
    uname = normalize_identifier(username)
    if len(uname) < 3:
        raise AppError("VALIDATION_ERROR", message="نام کاربری حداقل ۳ کاراکتر.")
    exists = await db.scalar(select(DeveloperUser).where(DeveloperUser.username == uname))
    if exists is not None:
        raise AppError("USERNAME_TAKEN", message="این نام کاربری قبلاً ثبت شده.")
    dev = DeveloperUser(
        username=uname,
        display_name=normalize_text(display_name) or uname,
        password_hash=hash_password(password),
        must_change_credentials=True,
        is_active=True,
    )
    db.add(dev)
    await db.flush()
    return dev


async def list_developers(db: AsyncSession) -> list[DeveloperUser]:
    return list((await db.scalars(select(DeveloperUser).order_by(DeveloperUser.created_at))).all())


# --------------------------------------------------------------------------- #
# نشست‌ها (access + refresh)
# --------------------------------------------------------------------------- #
async def issue_session(
    db: AsyncSession,
    *,
    subject_id: str,
    subject_type: str,
    claims: dict[str, Any] | None = None,
    user_agent: str = "",
    ip: str = "",
) -> dict[str, Any]:
    raw, token_hash, expires_at = new_refresh_token()
    db.add(
        RefreshToken(
            subject_id=subject_id,
            subject_type=subject_type,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:300],
            ip=(ip or "")[:60],
        )
    )
    await db.flush()
    access = create_access_token(subject_id, subject_type, claims)  # type: ignore[arg-type]
    return {
        "access_token": access,
        "refresh_token": raw,
        "token_type": "bearer",
    }


async def rotate_session(
    db: AsyncSession,
    *,
    raw_refresh: str,
    user_agent: str = "",
    ip: str = "",
) -> tuple[dict[str, Any], str, str]:
    """رفرش قدیمی را باطل و یک جفت توکن تازه صادر می‌کند."""
    token_hash = hash_refresh_token(raw_refresh or "")
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record is None or record.revoked_at is not None:
        raise AppError("REFRESH_INVALID")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        raise AppError("REFRESH_INVALID")

    record.revoked_at = _now()
    await db.flush()

    claims: dict[str, Any] = {}
    if record.subject_type == "user":
        user = await db.get(User, record.subject_id)
        if user is None or not user.is_active:
            raise AppError("ACCOUNT_DISABLED")
        claims = {"group_id": user.group_id, "username": user.username, "name": user.full_name}
    elif record.subject_type == "developer":
        dev = await db.get(DeveloperUser, record.subject_id)
        if dev is None or not dev.is_active:
            raise AppError("ACCOUNT_DISABLED")
        claims = {
            "role": "developer",
            "name": dev.display_name,
            "username": dev.username,
            "must_change": bool(dev.must_change_credentials),
        }
    else:
        admin = await db.get(AdminUser, record.subject_id)
        if admin is None or not admin.is_active:
            raise AppError("ACCOUNT_DISABLED")
        claims = {"role": admin.role, "name": admin.full_name}

    tokens = await issue_session(
        db,
        subject_id=record.subject_id,
        subject_type=record.subject_type,
        claims=claims,
        user_agent=user_agent,
        ip=ip,
    )
    return tokens, record.subject_id, record.subject_type


async def revoke_session(db: AsyncSession, raw_refresh: str) -> None:
    token_hash = hash_refresh_token(raw_refresh or "")
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def revoke_all_sessions(db: AsyncSession, subject_id: str, subject_type: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.subject_id == subject_id,
            RefreshToken.subject_type == subject_type,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
