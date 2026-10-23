from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from databases.psql.models import Ticket, TicketMessage, User

OPEN_STATUSES = ("open", "pending")
VALID_STATUSES = ("open", "pending", "closed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_message(msg: TicketMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "ticket_id": msg.ticket_id,
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "body": msg.body,
        "file_url": msg.file_url,
        "file_name": msg.file_name,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
    }


def serialize_ticket(t: Ticket, *, user: User | None = None) -> dict[str, Any]:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "subject": t.subject,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "unread_for_admin": t.unread_for_admin,
        "unread_for_user": t.unread_for_user,
        "user_name": user.full_name if user else "",
        "student_code": user.student_code if user else "",
    }


async def create_ticket(
    db: AsyncSession, *, user: User, subject: str, body: str
) -> tuple[Ticket, TicketMessage]:
    subject = (subject or "").strip()
    if len(subject) < 3:
        raise AppError("VALIDATION_ERROR", message="موضوع تیکت باید حداقل ۳ کاراکتر باشد.")

    open_count = await db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.user_id == user.id, Ticket.status.in_(OPEN_STATUSES)
        )
    )
    if (open_count or 0) >= 5:
        raise AppError(
            "TOO_MANY_OPEN_TICKETS",
            message="شما ۵ تیکت باز دارید. اول یکی را ببندید.",
            status_code=429,
        )

    ticket = Ticket(user_id=user.id, subject=subject, status="open", last_message_at=_now())
    db.add(ticket)
    await db.flush()

    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type="user",
        sender_id=user.id,
        body=(body or "").strip(),
    )
    db.add(msg)
    ticket.unread_for_admin = 1
    await db.flush()
    return ticket, msg


async def get_ticket_for_user(db: AsyncSession, ticket_id: str, user_id: str) -> Ticket:
    """IDOR: تیکت باید مال همین کاربر باشد، نه فقط اینکه کاربر لاگین است."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None or ticket.user_id != user_id:
        raise AppError("NOT_FOUND", message="تیکتی با این شناسه پیدا نشد.")
    return ticket


async def get_ticket_for_admin(db: AsyncSession, ticket_id: str) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise AppError("NOT_FOUND", message="تیکتی با این شناسه پیدا نشد.")
    return ticket


async def list_user_tickets(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(Ticket)
        .where(Ticket.user_id == user_id)
        .order_by(Ticket.last_message_at.desc().nullslast(), Ticket.created_at.desc())
        .limit(100)
    )
    return [serialize_ticket(t) for t in rows]


async def list_all_tickets(
    db: AsyncSession, *, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    stmt = select(Ticket, User).join(User, User.id == Ticket.user_id)
    if status in VALID_STATUSES:
        stmt = stmt.where(Ticket.status == status)
    stmt = (
        stmt.order_by(Ticket.last_message_at.desc().nullslast(), Ticket.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    rows = await db.execute(stmt)
    return [serialize_ticket(t, user=u) for t, u in rows.all()]


async def list_messages(db: AsyncSession, ticket_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
        .limit(min(max(limit, 1), 500))
    )
    return [serialize_message(m) for m in rows]


async def add_message(
    db: AsyncSession,
    *,
    ticket: Ticket,
    sender_type: str,
    sender_id: str,
    body: str = "",
    file_url: str = "",
    file_name: str = "",
) -> TicketMessage:
    if ticket.status == "closed":
        raise AppError("TICKET_CLOSED", message="این تیکت بسته شده است.", status_code=409)
    body = (body or "").strip()
    if not body and not file_url:
        raise AppError("VALIDATION_ERROR", message="متن پیام یا فایل لازم است.")
    if len(body) > 4000:
        raise AppError("VALIDATION_ERROR", message="متن پیام بیش از حد بلند است.")

    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type=sender_type,
        sender_id=sender_id,
        body=body,
        file_url=file_url,
        file_name=file_name,
    )
    db.add(msg)
    ticket.last_message_at = _now()
    if sender_type == "user":
        ticket.unread_for_admin = (ticket.unread_for_admin or 0) + 1
        ticket.status = "open"
    else:
        ticket.unread_for_user = (ticket.unread_for_user or 0) + 1
        ticket.status = "pending"
    await db.flush()
    return msg


async def mark_read(db: AsyncSession, ticket: Ticket, reader_type: str) -> None:
    now = _now()
    other = "admin" if reader_type == "user" else "user"
    await db.execute(
        update(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.sender_type == other,
            TicketMessage.read_at.is_(None),
        )
        .values(read_at=now)
    )
    if reader_type == "user":
        ticket.unread_for_user = 0
    else:
        ticket.unread_for_admin = 0
    await db.flush()


async def set_status(db: AsyncSession, ticket: Ticket, status: str) -> Ticket:
    if status not in VALID_STATUSES:
        raise AppError("VALIDATION_ERROR", message="وضعیت تیکت نامعتبر است.")
    ticket.status = status
    ticket.closed_at = _now() if status == "closed" else None
    await db.flush()
    return ticket
