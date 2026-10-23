from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.api.deps import CurrentAdmin, CurrentUser, DbSession
from backend.errors import AppError
from backend.services import tickets as svc
from backend.services.audit import log_audit
from backend.services.media import save_upload
from backend.services.rate_limit import limit_default
from backend.services.realtime import ADMIN_INBOX, get_hub, ticket_room
from backend.services.security import client_ip, decode_access_token
from databases.psql.base import get_session_factory
from databases.psql.models import AdminUser, User

router = APIRouter(tags=["tickets"])


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=250)
    body: str = Field(default="", max_length=4000)


class TicketMessageIn(BaseModel):
    body: str = Field(default="", max_length=4000)


class TicketStatusIn(BaseModel):
    status: str = Field(pattern="^(open|pending|closed)$")


# --------------------------------------------------------------------------- #
# کاربر
# --------------------------------------------------------------------------- #
@router.get("/tickets")
async def my_tickets(user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    return await svc.list_user_tickets(db, user.id)


@router.post("/tickets")
async def open_ticket(
    body: TicketCreate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    await limit_default(request, "ticket_create")
    ticket, msg = await svc.create_ticket(db, user=user, subject=body.subject, body=body.body)
    await log_audit(
        "ticket.create",
        actor_id=user.id,
        actor_type="user",
        ip=client_ip(request),
        target=ticket.id,
    )
    payload = svc.serialize_ticket(ticket, user=user)
    payload["messages"] = [svc.serialize_message(msg)]
    await get_hub().broadcast(
        ADMIN_INBOX,
        {"type": "ticket.opened", "ticket": payload},
    )
    return payload


@router.get("/tickets/{ticket_id}")
async def get_my_ticket(ticket_id: str, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_user(db, ticket_id, user.id)
    await svc.mark_read(db, ticket, "user")
    data = svc.serialize_ticket(ticket, user=user)
    data["messages"] = await svc.list_messages(db, ticket.id)
    return data


@router.post("/tickets/{ticket_id}/messages")
async def send_user_message(
    ticket_id: str,
    body: TicketMessageIn,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_user(db, ticket_id, user.id)
    msg = await svc.add_message(
        db, ticket=ticket, sender_type="user", sender_id=user.id, body=body.body
    )
    serialized = svc.serialize_message(msg)
    await get_hub().broadcast(
        ticket_room(ticket.id),
        {"type": "message", "message": serialized},
        skip_origin=f"user:{user.id}",
    )
    await get_hub().broadcast(
        ADMIN_INBOX,
        {"type": "ticket.updated", "ticket": svc.serialize_ticket(ticket, user=user)},
    )
    return serialized


@router.post("/tickets/{ticket_id}/upload")
async def user_upload(
    ticket_id: str,
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    body: str = Form(""),
) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_user(db, ticket_id, user.id)
    info = save_upload("ticket", file.filename, await file.read())
    msg = await svc.add_message(
        db,
        ticket=ticket,
        sender_type="user",
        sender_id=user.id,
        body=body,
        file_url=info["url"],
        file_name=info["filename"],
    )
    serialized = svc.serialize_message(msg)
    await get_hub().broadcast(
        ticket_room(ticket.id), {"type": "message", "message": serialized}
    )
    return serialized


@router.post("/tickets/{ticket_id}/close")
async def close_my_ticket(ticket_id: str, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_user(db, ticket_id, user.id)
    await svc.set_status(db, ticket, "closed")
    data = svc.serialize_ticket(ticket, user=user)
    await get_hub().broadcast(ticket_room(ticket.id), {"type": "status", "ticket": data})
    return data


# --------------------------------------------------------------------------- #
# ادمین
# --------------------------------------------------------------------------- #
@router.get("/admin/tickets")
async def admin_tickets(
    _: CurrentAdmin,
    db: DbSession,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    return await svc.list_all_tickets(db, status=status, limit=limit, offset=offset)


@router.get("/admin/tickets/{ticket_id}")
async def admin_get_ticket(ticket_id: str, _: CurrentAdmin, db: DbSession) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_admin(db, ticket_id)
    user = await db.get(User, ticket.user_id)
    await svc.mark_read(db, ticket, "admin")
    data = svc.serialize_ticket(ticket, user=user)
    data["messages"] = await svc.list_messages(db, ticket.id)
    return data


@router.post("/admin/tickets/{ticket_id}/messages")
async def admin_send_message(
    ticket_id: str,
    body: TicketMessageIn,
    admin: CurrentAdmin,
    db: DbSession,
) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_admin(db, ticket_id)
    msg = await svc.add_message(
        db, ticket=ticket, sender_type="admin", sender_id=admin.id, body=body.body
    )
    serialized = svc.serialize_message(msg)
    user = await db.get(User, ticket.user_id)
    await get_hub().broadcast(
        ticket_room(ticket.id),
        {"type": "message", "message": serialized},
        skip_origin=f"admin:{admin.id}",
    )
    await get_hub().broadcast(
        ADMIN_INBOX,
        {"type": "ticket.updated", "ticket": svc.serialize_ticket(ticket, user=user)},
    )
    return serialized


@router.post("/admin/tickets/{ticket_id}/upload")
async def admin_upload(
    ticket_id: str,
    admin: CurrentAdmin,
    db: DbSession,
    file: UploadFile = File(...),
    body: str = Form(""),
) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_admin(db, ticket_id)
    info = save_upload("ticket", file.filename, await file.read())
    msg = await svc.add_message(
        db,
        ticket=ticket,
        sender_type="admin",
        sender_id=admin.id,
        body=body,
        file_url=info["url"],
        file_name=info["filename"],
    )
    serialized = svc.serialize_message(msg)
    await get_hub().broadcast(
        ticket_room(ticket.id), {"type": "message", "message": serialized}
    )
    return serialized


@router.patch("/admin/tickets/{ticket_id}")
async def admin_set_status(
    ticket_id: str,
    body: TicketStatusIn,
    admin: CurrentAdmin,
    db: DbSession,
) -> dict[str, Any]:
    ticket = await svc.get_ticket_for_admin(db, ticket_id)
    await svc.set_status(db, ticket, body.status)
    user = await db.get(User, ticket.user_id)
    data = svc.serialize_ticket(ticket, user=user)
    await log_audit(
        "ticket.status",
        actor_id=admin.id,
        actor_type="admin",
        target=ticket.id,
        detail={"status": body.status},
    )
    await get_hub().broadcast(ticket_room(ticket.id), {"type": "status", "ticket": data})
    return data


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
async def _actor_from_token(token: str) -> tuple[str, str, str]:
    """(id, type, name) — توکن را از query می‌گیرد چون مرورگر هدر Authorization روی WS نمی‌گذارد."""
    payload = decode_access_token(token)
    factory = get_session_factory()
    async with factory() as db:
        if payload.get("typ") == "admin":
            admin = await db.get(AdminUser, str(payload.get("sub") or ""))
            if admin is None or not admin.is_active:
                raise AppError("TOKEN_INVALID")
            return admin.id, "admin", admin.full_name
        if payload.get("typ") == "user":
            user = await db.get(User, str(payload.get("sub") or ""))
            if user is None or not user.is_active:
                raise AppError("TOKEN_INVALID")
            return user.id, "user", user.full_name
    raise AppError("FORBIDDEN")


@router.websocket("/ws/tickets/{ticket_id}")
async def ticket_socket(ws: WebSocket, ticket_id: str, token: str = ""):
    if not token:
        await ws.close(code=4401)
        return
    try:
        actor_id, actor_type, actor_name = await _actor_from_token(token)
    except AppError:
        await ws.close(code=4401)
        return

    factory = get_session_factory()
    async with factory() as db:
        if actor_type == "user":
            try:
                await svc.get_ticket_for_user(db, ticket_id, actor_id)
            except AppError:
                await ws.close(code=4403)
                return
        else:
            try:
                await svc.get_ticket_for_admin(db, ticket_id)
            except AppError:
                await ws.close(code=4404)
                return

    hub = get_hub()
    conn = await hub.connect(ws, ticket_room(ticket_id), actor_id, actor_type, actor_name)
    try:
        while True:
            raw = await ws.receive_text()
            await hub.touch(conn)
            try:
                data = json.loads(raw)
            except Exception:
                continue
            kind = data.get("type")
            if kind in {"ping", "heartbeat"}:
                members = await hub.members(ticket_room(ticket_id))
                await hub.broadcast(
                    ticket_room(ticket_id),
                    {
                        "type": "presence",
                        "actor_type": actor_type,
                        "actor_name": actor_name,
                        "online": True,
                        "members": members,
                    },
                )
                continue
            if kind == "typing":
                await hub.broadcast(
                    ticket_room(ticket_id),
                    {
                        "type": "typing",
                        "actor_type": actor_type,
                        "actor_name": actor_name,
                        "typing": bool(data.get("typing", True)),
                    },
                    skip_origin=f"{actor_type}:{actor_id}",
                )
                continue
            if kind == "message":
                body = str(data.get("body") or "")
                async with factory() as db:
                    if actor_type == "user":
                        ticket = await svc.get_ticket_for_user(db, ticket_id, actor_id)
                    else:
                        ticket = await svc.get_ticket_for_admin(db, ticket_id)
                    msg = await svc.add_message(
                        db,
                        ticket=ticket,
                        sender_type=actor_type,
                        sender_id=actor_id,
                        body=body,
                    )
                    await db.commit()
                    serialized = svc.serialize_message(msg)
                await hub.broadcast(
                    ticket_room(ticket_id),
                    {"type": "message", "message": serialized},
                )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(conn)


@router.websocket("/ws/admin/inbox")
async def admin_inbox(ws: WebSocket, token: str = ""):
    if not token:
        await ws.close(code=4401)
        return
    try:
        actor_id, actor_type, actor_name = await _actor_from_token(token)
    except AppError:
        await ws.close(code=4401)
        return
    if actor_type != "admin":
        await ws.close(code=4403)
        return

    hub = get_hub()
    conn = await hub.connect(ws, ADMIN_INBOX, actor_id, actor_type, actor_name)
    try:
        while True:
            await ws.receive_text()
            await hub.touch(conn)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(conn)
