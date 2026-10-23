from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover
    MongoClient = None  # type: ignore


class AuditLog:
    """لاگ عملیات حساس در Mongo؛ اگر Mongo نبود، فایل JSONL محلی."""

    def __init__(self):
        self.settings = get_settings()
        self._col = None
        self._file = self.settings.data_root / "logs" / "audit.jsonl"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self) -> None:
        if MongoClient is None:
            return
        try:
            client = MongoClient(self.settings.mongo_uri, serverSelectionTimeoutMS=800)
            client.admin.command("ping")
            col = client[self.settings.mongo_db]["audit_log"]
            col.create_index([("at", -1)])
            col.create_index([("actor_id", 1), ("at", -1)])
            self._col = col
        except Exception as exc:
            logger.warning("Mongo برای audit در دسترس نیست؛ fallback فایل: %s", exc)
            self._col = None

    def record(
        self,
        action: str,
        actor_id: str = "",
        actor_type: str = "anonymous",
        ip: str = "",
        status: str = "ok",
        target: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "action": action,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "ip": ip,
            "status": status,
            "target": target,
            "detail": detail or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if self._col is not None:
            try:
                self._col.insert_one(dict(entry))
                return
            except Exception as exc:
                logger.warning("ثبت audit در Mongo ناموفق: %s", exc)
        try:
            with self._file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover
            logger.warning("ثبت audit روی فایل ناموفق: %s", exc)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if self._col is not None:
            try:
                docs = list(self._col.find({}, {"_id": 0}).sort("at", -1).limit(limit))
                return docs
            except Exception:
                pass
        if not self._file.exists():
            return []
        lines = self._file.read_text(encoding="utf-8").splitlines()[-limit:]
        out: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out


_audit: AuditLog | None = None


def get_audit() -> AuditLog:
    global _audit
    if _audit is None:
        _audit = AuditLog()
    return _audit


async def log_audit(action: str, **kwargs: Any) -> None:
    """نوشتن لاگ بدون بلاک کردن event loop."""
    from starlette.concurrency import run_in_threadpool

    try:
        await run_in_threadpool(get_audit().record, action, **kwargs)
    except Exception as exc:  # pragma: no cover
        logger.warning("audit ناموفق: %s", exc)
