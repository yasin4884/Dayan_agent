from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from core.config import get_settings

# همه محتوا از پنل ادمین می‌آید — اینجا فقط ساختار خالی است (بدون داده نمونه)
_DEFAULT_CMS: dict[str, Any] = {
    "brand": {
        "name": "",
        "product_title": "",
        "tagline": "",
        "logo_url": "",
        "favicon_url": "",
        # لینک سایت دانشگاه فقط برای نمایش در صفحه اصلی (جدا از کرول مدل)
        "website_url": "",
        "website_label": "سایت دانشگاه",
    },
    "theme": {
        "default_mode": "light",
        "primary": "#0ea5e9",
        "accent": "#14b8a6",
        "accent_orange": "#f97316",
        "accent_blue": "#2563eb",
        "accent_green": "#16a34a",
        "accent_cyan": "#06b6d4",
    },
    # اسلایدر متحرک بالای صفحه اصلی
    # {id,title,subtitle,image_url,link_url,sort_order,enabled,group_ids}
    "banners": [],
    # دکمه‌های دسترسی سریع
    # {id,title,description,button_label,href,color,icon,badge,enabled,sort_order,group_ids}
    "quick_actions": [],
    # تقویم آموزشی — {id,label,date,time,description,remind_days,group_ids}
    "calendar": {"title": "", "events": []},
    # اطلاع‌رسانی — {id,title,body,pinned,push,created_at,group_ids}
    "notifications": [],
    # بخشنامه — {id,title,body,file_url,file_name,created_at,group_ids}
    "circulars": [],
    # فرم‌ها — {id,slug,title,description,file_url,filename,group_ids}
    "forms": [],
    # اساتید و امتیاز — {id,full_name,course,score,rank,note,group_ids}
    "professors": [],
    "telegram": {
        "enabled": False,
        "title": "",
        "description": "",
        "button_label": "",
        "url": "",
    },
    "links": [],
    "comments": [],
    "hero_banner": {
        "enabled": False,
        "title": "",
        "subtitle": "",
        "image_url": "",
        "background": "",
    },
    "login": {
        "user": {"title": "ورود", "subtitle": "", "banner_url": "", "banner_text": ""},
        "admin": {"title": "ورود ادمین", "subtitle": "", "banner_url": "", "banner_text": ""},
    },
    "nav": [
        {"id": "home", "label": "خانه", "href": "/", "icon": "home"},
        {"id": "notifications", "label": "اطلاع‌رسانی", "href": "/notifications", "icon": "bell"},
        {"id": "calendar", "label": "تقویم", "href": "/calendar", "icon": "calendar"},
        {"id": "forms", "label": "فرم‌ها", "href": "/forms", "icon": "file"},
        {"id": "tickets", "label": "تیکت", "href": "/tickets", "icon": "ticket"},
        {"id": "profile", "label": "پروفایل", "href": "/profile", "icon": "user"},
    ],
    "groups": [],
    "ai_rules": [
        "اولویت با اسناد ایندکس‌شده، فرم‌ها و داده‌های سامانه است.",
        "اگر در دیتابیس نبود از سایت دانشگاه که ادمین تنظیم کرده کمک بگیر.",
        "از خودت چیزی نساز.",
    ],
    # سوالات متداول — وقتی مدل قطع است یا سوال دقیق بود از همین‌ها جواب بده
    # {id, question, answer, keywords, enabled}
    "faqs": [],
    # دانش ربات — documents فقط از سرویس دانش به‌روز می‌شود
    # website برای صفحه اصلی نیست؛ crawl_url / web_base_url برای کرول مدل است
    "knowledge": {
        "web_base_url": "",
        "crawl_url": "",
        "crawl_enabled": False,
        "documents": [],
    },
}

# بخش‌هایی که فیلتر گروه دارند
_GROUP_FILTERED = (
    "banners",
    "quick_actions",
    "notifications",
    "circulars",
    "forms",
    "professors",
    "comments",
    "links",
)


def _visible_for_group(item: dict[str, Any], group_id: str | None) -> bool:
    """group_ids خالی یا ['*'] یعنی برای همه."""
    groups = item.get("group_ids")
    if groups is None or groups == [] or groups == ["*"]:
        return True
    if not group_id:
        return False
    return group_id in groups


def _sorted(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda x: int(x.get("sort_order") or 0))


class CMSStore:
    def __init__(self, path=None):
        settings = get_settings()
        self.path = path or settings.cms_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(deepcopy(_DEFAULT_CMS))

    def load(self) -> dict[str, Any]:
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        merged = deepcopy(_DEFAULT_CMS)
        _deep_merge(merged, data)
        return merged

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        current = {}
        if self.path.exists():
            try:
                with self.path.open(encoding="utf-8") as f:
                    current = json.load(f) or {}
            except Exception:
                current = {}
        # لیست اسناد ایندکس‌شده را از PUT/PATCH ظاهری پنل پاک نکن
        incoming_knowledge = data.get("knowledge") if isinstance(data.get("knowledge"), dict) else None
        current_docs = ((current.get("knowledge") or {}) if isinstance(current.get("knowledge"), dict) else {}).get("documents") or []
        if incoming_knowledge is None:
            data = {**data, "knowledge": {**(current.get("knowledge") or {}), "documents": current_docs}}
        elif "documents" not in incoming_knowledge:
            incoming_knowledge = {**incoming_knowledge, "documents": current_docs}
            data = {**data, "knowledge": incoming_knowledge}

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def patch(self, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        _deep_merge(current, updates)
        return self.save(current)

    def get_ai_rules_text(self) -> str:
        rules = self.load().get("ai_rules") or []
        if not rules:
            return ""
        lines = "\n".join(f"- {r}" for r in rules if r)
        return f"\n\nقوانین به‌روز ادمین:\n{lines}"

    def public_view(self, group_id: str | None = None) -> dict[str, Any]:
        """نمای عمومی: فقط آیتم‌های فعال و مخصوص گروه کاربر."""
        site = self.load()

        for key in _GROUP_FILTERED:
            items = [i for i in (site.get(key) or []) if _visible_for_group(i, group_id)]
            items = [i for i in items if i.get("enabled", True)]
            site[key] = _sorted(items)

        cal = site.get("calendar") or {}
        events = [e for e in (cal.get("events") or []) if _visible_for_group(e, group_id)]
        site["calendar"] = {**cal, "events": _sorted(events)}

        # اطلاعیه‌ها: پین‌شده‌ها بالا، بعد جدیدترین
        site["notifications"] = sorted(
            site.get("notifications") or [],
            key=lambda n: (not n.get("pinned"), str(n.get("created_at") or "")),
            reverse=False,
        )

        site["nav"] = [
            n
            for n in (site.get("nav") or [])
            if n.get("id") != "chat" and n.get("href") != "/chat"
        ]
        # سازگاری با نسخه قبلی فرانت
        site["modules"] = site.get("quick_actions") or []
        site.pop("ai_rules", None)
        site.pop("knowledge", None)
        # FAQ همیشه برای فرانت عمومی (چیپ‌های پیشنهادی + پاسخ سریع)
        raw_faqs = site.get("faqs") or []
        site["faqs"] = [
            {
                "id": str(f.get("id") or ""),
                "question": str(f.get("question") or "").strip(),
                "answer": str(f.get("answer") or "").strip(),
            }
            for f in raw_faqs
            if f.get("enabled", True) and str(f.get("question") or "").strip() and str(f.get("answer") or "").strip()
        ]
        login = dict(site.get("login") or {})
        login.pop("admin", None)
        site["login"] = login
        return site

    def list_faqs(self) -> list[dict[str, Any]]:
        items = self.load().get("faqs") or []
        return [i for i in items if i.get("enabled", True)]


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


_cms: CMSStore | None = None


def get_cms() -> CMSStore:
    global _cms
    if _cms is None:
        _cms = CMSStore()
    return _cms


def reset_cms_singleton() -> None:
    global _cms
    _cms = None
