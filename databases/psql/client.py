from __future__ import annotations

import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore


def postgres_dsn_sync() -> str:
    """DSN همگام — فقط برای تشخیص وضعیت و اسکریپت‌های مدیریتی."""
    s = get_settings()
    return (
        f"postgresql://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def check_postgres() -> dict[str, Any]:
    """بررسی سریع دسترسی به Postgres (بدون SQLAlchemy)."""
    if psycopg is None:
        return {"ok": False, "detail": "psycopg نصب نیست"}
    try:
        with psycopg.connect(postgres_dsn_sync(), connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"ok": True, "detail": "connected"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
