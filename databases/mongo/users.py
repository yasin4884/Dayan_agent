from __future__ import annotations

import json
import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
except ImportError:  # pragma: no cover
    MongoClient = None  # type: ignore
    Collection = Any  # type: ignore


class UserRepository:
    """کاربران در Mongo؛ اگر Mongo نبود فایل JSON."""

    def __init__(self):
        settings = get_settings()
        self._file = settings.data_root / "users.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._col: Collection | None = None
        self._connect()
        self._migrate_file_to_mongo()

    def _connect(self) -> None:
        if MongoClient is None:
            return
        try:
            settings = get_settings()
            self._client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=800)
            self._client.admin.command("ping")
            self._col = self._client[settings.mongo_db]["users"]
            self._col.create_index("email", unique=True)
            logger.info("UserRepository به Mongo وصل شد")
        except Exception as exc:
            logger.warning("UserRepository Mongo ناموفق؛ فایل: %s", exc)
            self._client = None
            self._col = None

    def _migrate_file_to_mongo(self) -> None:
        if self._col is None or not self._file.exists():
            return
        try:
            if self._col.estimated_document_count() > 0:
                return
            users = json.loads(self._file.read_text(encoding="utf-8") or "[]")
            if users:
                self._col.insert_many(users)
                logger.info("مهاجرت %s کاربر از فایل به Mongo", len(users))
        except Exception as exc:
            logger.warning("مهاجرت کاربران: %s", exc)

    def list_users(self) -> list[dict[str, Any]]:
        if self._col is not None:
            return list(self._col.find({}, {"_id": 0}))
        if not self._file.exists():
            return []
        return json.loads(self._file.read_text(encoding="utf-8") or "[]")

    def _save_file(self, users: list[dict[str, Any]]) -> None:
        self._file.write_text(
            json.dumps(users, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        email_l = email.strip().lower()
        if self._col is not None:
            return self._col.find_one({"email": email_l}, {"_id": 0})
        for u in self.list_users():
            if str(u.get("email", "")).lower() == email_l:
                return u
        return None

    def find_by_personnel_code(self, code: str) -> dict[str, Any] | None:
        code_n = code.strip()
        if not code_n:
            return None
        if self._col is not None:
            return self._col.find_one({"personnel_code": code_n}, {"_id": 0})
        for u in self.list_users():
            if str(u.get("personnel_code", "")).strip() == code_n:
                return u
        return None

    def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        if self._col is not None:
            return self._col.find_one({"id": user_id}, {"_id": 0})
        for u in self.list_users():
            if u.get("id") == user_id:
                return u
        return None

    def insert(self, user: dict[str, Any]) -> None:
        if self._col is not None:
            doc = dict(user)
            self._col.insert_one(doc)
            return
        users = self.list_users()
        users.append(user)
        self._save_file(users)


_repo: UserRepository | None = None


def get_user_repository() -> UserRepository:
    global _repo
    if _repo is None:
        _repo = UserRepository()
    return _repo
