from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.config import get_settings

logger = logging.getLogger(__name__)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_active_dsn: str = ""


def _build_engine(dsn: str) -> AsyncEngine:
    settings = get_settings()
    kwargs: dict = {"echo": settings.db_echo, "future": True}
    if dsn.startswith("postgresql"):
        # برای بار زیاد: pool ثابت + بازیافت اتصال کهنه
        kwargs.update(
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"timeout": 3},
        )
    return create_async_engine(dsn, **kwargs)


async def _dsn_works(dsn: str) -> bool:
    engine = _build_engine(dsn)
    try:
        async with asyncio.timeout(4):
            async with engine.connect() as conn:
                from sqlalchemy import text

                await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("اتصال به دیتابیس ناموفق (%s): %s", dsn.split("@")[-1], exc)
        return False
    finally:
        await engine.dispose()


async def init_database() -> dict[str, object]:
    """اتصال به Postgres؛ اگر نبود و اجازه داده شده باشد، SQLite توسعه."""
    global _engine, _session_factory, _active_dsn

    settings = get_settings()
    settings.data_root.mkdir(parents=True, exist_ok=True)

    primary = settings.postgres_dsn
    chosen = ""
    if await _dsn_works(primary):
        chosen = primary
    elif settings.db_fallback_sqlite:
        logger.warning("Postgres در دسترس نیست؛ برای توسعه از SQLite استفاده می‌شود")
        chosen = settings.sqlite_dsn
    else:
        raise RuntimeError("اتصال به Postgres برقرار نشد و fallback غیرفعال است")

    _engine = _build_engine(chosen)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _active_dsn = chosen

    # مدل‌ها باید قبل از create_all ایمپورت شده باشند
    from databases.psql import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return {
        "ok": True,
        "engine": "postgres" if chosen.startswith("postgresql") else "sqlite",
    }


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("دیتابیس راه‌اندازی نشده است")
    return _session_factory


def active_dsn_kind() -> str:
    if not _active_dsn:
        return "none"
    return "postgres" if _active_dsn.startswith("postgresql") else "sqlite"


async def get_db():
    """Dependency فست‌ای‌پی‌آی برای گرفتن session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def db_health() -> dict[str, object]:
    if _session_factory is None:
        return {"ok": False, "engine": "none", "detail": "راه‌اندازی نشده"}
    try:
        from sqlalchemy import text

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return {"ok": True, "engine": active_dsn_kind()}
    except Exception as exc:
        return {"ok": False, "engine": active_dsn_kind(), "detail": str(exc)}
