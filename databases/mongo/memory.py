from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
except ImportError:  # pragma: no cover
    MongoClient = None  # type: ignore
    Collection = Any  # type: ignore


class ConversationMemory:

    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._col: Collection | None = None
        self._file_fallback = self.settings.data_root / "memory" / "conversations.json"
        self._file_fallback.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self) -> None:
        if MongoClient is None:
            logger.warning("pymongo نصب نیست؛ حافظه روی فایل محلی می‌رود")
            return
        try:
            self._client = MongoClient(self.settings.mongo_uri, serverSelectionTimeoutMS=800)
            self._client.admin.command("ping")
            db = self._client[self.settings.mongo_db]
            self._col = db["conversations"]
            logger.info("حافظه مکالمه به Mongo وصل شد")
        except Exception as exc:
            logger.warning("Mongo در دسترس نیست؛ fallback فایل: %s", exc)
            self._client = None
            self._col = None

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        turn = {
            "role": role,
            "content": content,
            "meta": meta or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if self._col is not None:
            self._col.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "turns": {
                            "$each": [turn],
                            "$slice": -int(self.settings.memory_max_turns),
                        }
                    },
                    "$set": {"updated_at": turn["at"]},
                    "$setOnInsert": {"created_at": turn["at"], "session_id": session_id},
                },
                upsert=True,
            )
            return

        data = self._load_file()
        item = data.get(session_id) or {"session_id": session_id, "turns": []}
        item["turns"].append(turn)
        item["turns"] = item["turns"][-int(self.settings.memory_max_turns) :]
        item["updated_at"] = turn["at"]
        data[session_id] = item
        self._save_file(data)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        if self._col is not None:
            doc = self._col.find_one({"session_id": session_id}) or {}
            return list(doc.get("turns") or [])
        data = self._load_file()
        return list((data.get(session_id) or {}).get("turns") or [])

    def build_memory_context(self, session_id: str) -> str:
        turns = self.get_history(session_id)
        if not turns:
            return ""
        lines = []
        for t in turns:
            lines.append(f"{t.get('role', 'user')}: {t.get('content', '')}")
        return "تاریخچه گفتگو:\n" + "\n".join(lines)

    def _load_file(self) -> dict[str, Any]:
        import json

        if not self._file_fallback.exists():
            return {}
        with self._file_fallback.open(encoding="utf-8") as f:
            return json.load(f)

    def _save_file(self, data: dict[str, Any]) -> None:
        import json

        with self._file_fallback.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


_memory: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
