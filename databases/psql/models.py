from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from databases.psql.base import Base, IdMixin, TimestampMixin

# target_groups: لیست شناسه گروه‌ها؛ خالی یعنی برای همه
TargetGroups = Mapped[list[str]]


class Group(IdMixin, TimestampMixin, Base):
    """گروه دانشجویی؛ در ثبت‌نام انتخاب می‌شود و مبنای فیلتر محتواست."""

    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(400), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list["User"]] = relationship(back_populates="group")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    student_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group | None] = relationship(back_populates="users")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class AdminUser(IdMixin, TimestampMixin, Base):
    """ادمین با شماره پرسنلی؛ auth کاملاً جدا از کاربر عادی."""

    __tablename__ = "admin_users"

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    personnel_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeveloperUser(IdMixin, TimestampMixin, Base):
    """حساب پنل دولوپر (پورت ۴۰۰۰) — جدا از ادمین و دانشجو."""

    __tablename__ = "developer_users"

    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), default="Developer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_credentials: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(IdMixin, TimestampMixin, Base):
    """رفرش توکن هش‌شده تا قابل باطل‌کردن باشد."""

    __tablename__ = "refresh_tokens"

    subject_id: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user | admin | developer
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    ip: Mapped[str] = mapped_column(String(60), default="")

    __table_args__ = (Index("ix_refresh_subject", "subject_type", "subject_id"),)


class Banner(IdMixin, TimestampMixin, Base):
    """اسلایدر بالای صفحه اصلی."""

    __tablename__ = "banners"

    title: Mapped[str] = mapped_column(String(200), default="")
    subtitle: Mapped[str] = mapped_column(String(400), default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    link_url: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class QuickAction(IdMixin, TimestampMixin, Base):
    """دکمه‌های دسترسی سریع صفحه اصلی."""

    __tablename__ = "quick_actions"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(400), default="")
    button_label: Mapped[str] = mapped_column(String(120), default="")
    href: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str] = mapped_column(String(30), default="blue")
    icon: Mapped[str] = mapped_column(String(60), default="")
    badge: Mapped[str] = mapped_column(String(60), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class Notification(IdMixin, TimestampMixin, Base):
    """اطلاع‌رسانی؛ مبنای push هم همین است."""

    __tablename__ = "notifications"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    send_push: Mapped[bool] = mapped_column(Boolean, default=False)
    push_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_groups: TargetGroups = mapped_column(JSON, default=list)

    __table_args__ = (Index("ix_notifications_created", "created_at"),)


class Circular(IdMixin, TimestampMixin, Base):
    """بخشنامه."""

    __tablename__ = "circulars"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    file_url: Mapped[str] = mapped_column(String(500), default="")
    file_name: Mapped[str] = mapped_column(String(250), default="")
    text_preview: Mapped[str] = mapped_column(Text, default="")
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class FormDoc(IdMixin, TimestampMixin, Base):
    """فرم‌هایی که ایجنت به کاربر می‌دهد."""

    __tablename__ = "forms"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(600), default="")
    file_url: Mapped[str] = mapped_column(String(500), default="")
    file_name: Mapped[str] = mapped_column(String(250), default="")
    text_preview: Mapped[str] = mapped_column(Text, default="")
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class CalendarEvent(IdMixin, TimestampMixin, Base):
    """مراحل تقویم آموزشی؛ پایه یادآوری‌های ایجنت."""

    __tablename__ = "calendar_events"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=0)
    target_groups: TargetGroups = mapped_column(JSON, default=list)

    __table_args__ = (Index("ix_calendar_date", "event_date"),)


class Professor(IdMixin, TimestampMixin, Base):
    __tablename__ = "professors"

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    course_name: Mapped[str] = mapped_column(String(200), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(500), default="")
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class ExternalLink(IdMixin, TimestampMixin, Base):
    """کانال تلگرام و لینک‌های بیرونی."""

    __tablename__ = "external_links"

    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(250), default="")
    button_label: Mapped[str] = mapped_column(String(120), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    target_groups: TargetGroups = mapped_column(JSON, default=list)


class SiteSetting(TimestampMixin, Base):
    """برند، تم، متن‌های ثابت — همه از پنل ادمین."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Comment(IdMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_name: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)


class Ticket(IdMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|pending|closed
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unread_for_admin: Mapped[int] = mapped_column(Integer, default=0)
    unread_for_user: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_tickets_user_status", "user_id", "status"),)


class TicketMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "ticket_messages"

    ticket_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False)  # user | admin
    sender_id: Mapped[str] = mapped_column(String(32), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    file_url: Mapped[str] = mapped_column(String(500), default="")
    file_name: Mapped[str] = mapped_column(String(250), default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ticket: Mapped[Ticket] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_ticket_messages_ticket", "ticket_id", "created_at"),)


class PushSubscription(IdMixin, TimestampMixin, Base):
    """اشتراک Web Push هر دستگاه کاربر."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(600), unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), default="")
    auth: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
