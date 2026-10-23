from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.api.deps import CurrentDeveloper, DbSession
from backend.api.schemas import ChangePasswordRequest, StrictModel, TokenResponse
from backend.errors import AppError
from backend.services import accounts
from backend.services.audit import log_audit
from backend.services import process_manager as pm
from backend.services.rate_limit import limit_default, limit_login
from backend.services.security import client_ip
from core.text_utils import normalize_text

router = APIRouter(tags=["developer"])


class DevLoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class DevCredentialsRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_username: str | None = Field(default=None, min_length=3, max_length=60)
    new_password: str = Field(min_length=8, max_length=128)
    new_password_confirm: str = Field(min_length=8, max_length=128)


class DevCreateRequest(StrictModel):
    username: str = Field(min_length=3, max_length=60)
    display_name: str = Field(default="", max_length=160)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)


class ServiceAction(BaseModel):
    service: str = Field(min_length=2, max_length=40)


@router.get("/dev/bootstrap")
async def dev_bootstrap_info(db: DbSession) -> dict[str, Any]:
    await accounts.ensure_bootstrap_developer(db)
    await db.commit()
    return {"ok": True}


@router.post("/dev/auth/login", response_model=TokenResponse)
async def dev_login(body: DevLoginRequest, request: Request, db: DbSession):
    await limit_login(request)
    await accounts.ensure_bootstrap_developer(db)
    dev = await accounts.authenticate_developer(db, body.username, body.password)
    tokens = await accounts.issue_session(
        db,
        subject_id=dev.id,
        subject_type="developer",
        claims={
            "role": "developer",
            "name": dev.display_name,
            "username": dev.username,
            "must_change": bool(dev.must_change_credentials),
        },
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip(request),
    )
    await log_audit(
        "developer.login",
        actor_id=dev.id,
        actor_type="developer",
        ip=client_ip(request),
        target=dev.username,
    )
    return TokenResponse(**tokens, user=accounts.public_developer(dev))


@router.get("/dev/auth/me")
async def dev_me(dev: CurrentDeveloper) -> dict[str, Any]:
    return accounts.public_developer(dev)


@router.post("/dev/auth/change-credentials")
async def dev_change_credentials(
    body: DevCredentialsRequest,
    request: Request,
    db: DbSession,
    dev: CurrentDeveloper,
) -> dict[str, Any]:
    updated = await accounts.change_developer_credentials(
        db,
        dev=dev,
        current_password=body.current_password,
        new_username=body.new_username,
        new_password=body.new_password,
        new_password_confirm=body.new_password_confirm,
    )
    await log_audit(
        "developer.change_credentials",
        actor_id=dev.id,
        actor_type="developer",
        ip=client_ip(request),
        target=updated.username,
    )
    return {"ok": True, "user": accounts.public_developer(updated)}


@router.get("/dev/users")
async def dev_list_users(db: DbSession, _: CurrentDeveloper) -> list[dict[str, Any]]:
    rows = await accounts.list_developers(db)
    return [accounts.public_developer(d) for d in rows]


@router.post("/dev/users", response_model=dict)
async def dev_create_user(
    body: DevCreateRequest,
    request: Request,
    db: DbSession,
    actor: CurrentDeveloper,
) -> dict[str, Any]:
    if actor.must_change_credentials:
        raise AppError("FORBIDDEN", message="اول نام کاربری و رمز خودت را عوض کن.")
    created = await accounts.create_developer(
        db,
        username=body.username,
        password=body.password,
        password_confirm=body.password_confirm,
        display_name=normalize_text(body.display_name),
    )
    await log_audit(
        "developer.create",
        actor_id=actor.id,
        actor_type="developer",
        ip=client_ip(request),
        target=created.username,
    )
    return {"ok": True, "user": accounts.public_developer(created)}


@router.get("/dev/services")
async def dev_services(_: CurrentDeveloper) -> dict[str, Any]:
    return {"services": pm.status(), "databases": pm.db_snapshot()}


@router.post("/dev/services/restart")
async def dev_restart(body: ServiceAction, request: Request, actor: CurrentDeveloper) -> dict[str, Any]:
    await limit_default(request, "dev_restart")
    if actor.must_change_credentials:
        raise AppError("FORBIDDEN", message="اول اعتبار حساب را عوض کن.")
    result = pm.restart(body.service)
    await log_audit(
        "developer.restart",
        actor_id=actor.id,
        actor_type="developer",
        ip=client_ip(request),
        target=body.service,
        detail=result,
    )
    return result


@router.post("/dev/services/start")
async def dev_start(body: ServiceAction, request: Request, actor: CurrentDeveloper) -> dict[str, Any]:
    await limit_default(request, "dev_start")
    if actor.must_change_credentials:
        raise AppError("FORBIDDEN", message="اول اعتبار حساب را عوض کن.")
    result = pm.start(body.service)
    await log_audit(
        "developer.start",
        actor_id=actor.id,
        actor_type="developer",
        ip=client_ip(request),
        target=body.service,
        detail=result,
    )
    return result


@router.post("/dev/services/stop")
async def dev_stop(body: ServiceAction, request: Request, actor: CurrentDeveloper) -> dict[str, Any]:
    await limit_default(request, "dev_stop")
    if actor.must_change_credentials:
        raise AppError("FORBIDDEN", message="اول اعتبار حساب را عوض کن.")
    result = pm.stop(body.service)
    await log_audit(
        "developer.stop",
        actor_id=actor.id,
        actor_type="developer",
        ip=client_ip(request),
        target=body.service,
        detail=result,
    )
    return result


@router.get("/dev/logs/{service}")
async def dev_logs(service: str, _: CurrentDeveloper, lines: int = 200) -> dict[str, Any]:
    if service == "audit":
        return {"id": "audit", "lines": pm.read_audit_tail(lines), "path": "data/logs/audit.jsonl"}
    if service not in pm.SERVICES and service != "audit":
        raise AppError("VALIDATION_ERROR", message="سرویس ناشناخته")
    return pm.read_log(service, lines=lines)


@router.get("/dev/overview")
async def dev_overview(_: CurrentDeveloper) -> dict[str, Any]:
    from ai_model.model import get_llm_service

    llm_ok = False
    try:
        llm_ok = get_llm_service().is_available()
    except Exception:
        llm_ok = False
    return {
        "services": pm.status(),
        "databases": pm.db_snapshot(),
        "llm_available": llm_ok,
        "bootstrap_user": accounts.BOOTSTRAP_DEV_USER,
    }
