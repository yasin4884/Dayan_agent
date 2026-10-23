"""جمعیت تست SQL + CMS برای باگ‌گیری."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def main() -> None:
    from backend.services import accounts
    from backend.services.cms import get_cms
    from backend.services.security import hash_password
    from databases.psql.base import get_session_factory, init_database
    from databases.psql.models import User
    from sqlalchemy import select

    info = await init_database()
    print("db:", info)

    factory = get_session_factory()
    async with factory() as db:
        group = await accounts.ensure_default_group(db)
        await accounts.ensure_bootstrap_developer(db)

        samples = [
            ("علی", "تستی", "student1", "1401001", "Student1@123"),
            ("سارا", "نمونه", "student2", "1401002", "Student2@123"),
            ("رضا", "باگ‌گیر", "student3", "1401003", "Student3@123"),
        ]
        created = 0
        for first, last, username, code, password in samples:
            exists = await db.scalar(
                select(User).where((User.username == username) | (User.student_code == code))
            )
            if exists:
                continue
            db.add(
                User(
                    first_name=first,
                    last_name=last,
                    username=username,
                    student_code=code,
                    password_hash=hash_password(password),
                    group_id=group.id,
                    is_active=True,
                )
            )
            created += 1
        await db.commit()
        print(f"students created: {created} (group={group.name})")

    cms = get_cms()
    site = cms.load()
    if not site.get("notifications"):
        site["notifications"] = [
            {
                "id": "seed-n1",
                "title": "اطلاعیه تست",
                "body": "این یک اطلاعیه تست برای باگ‌گیری است.",
                "pinned": True,
                "enabled": True,
                "group_ids": [],
                "created_at": "2026-09-10",
            }
        ]
    if not site.get("calendar", {}).get("events"):
        site.setdefault("calendar", {"title": "تقویم آموزشی", "events": []})
        site["calendar"]["events"] = [
            {
                "id": "seed-e1",
                "title": "مهلت تست",
                "label": "آزمون",
                "date": "2026-09-20",
                "time": "10:00",
                "description": "رویداد تست جمعیت",
                "enabled": True,
                "group_ids": [],
            }
        ]
    if not site.get("faqs"):
        site["faqs"] = [
            {
                "id": "seed-f1",
                "question": "چطور رمز را عوض کنم؟",
                "answer": "از پروفایل → عوض کردن رمز.",
                "enabled": True,
            }
        ]
    cms.save(site)
    print("cms seeded")
    print("developer login: developer / ChangeMe@1234")
    print("students: student1..3 / Student1@123 ...")


if __name__ == "__main__":
    asyncio.run(main())
