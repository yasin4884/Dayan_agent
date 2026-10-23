from __future__ import annotations



import logging

from typing import Any



logger = logging.getLogger(__name__)



_KNOWN_PAGES: dict[str, dict[str, str]] = {
    "/": {"title": "صفحه اصلی", "purpose": "نمای کلی سامانه و دسترسی سریع."},
    "/login": {"title": "ورود / ثبت‌نام", "purpose": "ورود و ساخت حساب دانشجو."},
    "/forms": {"title": "فرم‌ها", "purpose": "دانلود و مشاهده فرم‌های آموزشی."},
    "/tickets": {"title": "تیکت", "purpose": "پشتیبانی انسانی و ارسال پیام به ادمین."},
    "/calendar": {"title": "تقویم", "purpose": "رویدادها و مهلت‌های آموزشی."},
    "/notifications": {"title": "اطلاع‌رسانی", "purpose": "اطلاعیه‌ها و پیام‌های سازمانی."},
    "/circulars": {"title": "بخشنامه‌ها", "purpose": "بخشنامه‌ها و فایل‌های رسمی."},
    "/professors": {"title": "اساتید", "purpose": "فهرست و امتیاز اساتید."},
    "/chat": {"title": "گفتگو", "purpose": "گفتگو با دستیار هوشمند."},
    "/courses": {"title": "دروس", "purpose": "دروس و واحدها."},
    "/library": {"title": "کتابخانه", "purpose": "منابع کتابخانه‌ای."},
    "/profile": {"title": "پروفایل", "purpose": "اطلاعات حساب کاربری."},
    "/search": {"title": "جستجو", "purpose": "جستجو در سامانه."},
    "/survey": {"title": "نظرسنجی", "purpose": "شرکت در نظرسنجی‌ها."},
    "/transcript": {"title": "کارنامه", "purpose": "مشاهده یا تحلیل کارنامه."},
}





def normalize_path(path: str | None) -> str:

    if not path:

        return "/"

    p = path.strip() or "/"

    if not p.startswith("/"):

        p = "/" + p

    if len(p) > 1 and p.endswith("/"):

        p = p.rstrip("/")

    return p





def describe_page(

    path: str | None,

    title: str | None = None,

    page_text: str | None = None,

    cms_site: dict[str, Any] | None = None,

) -> str:

    """متن context موقعیت کاربر برای مدل."""

    path_n = normalize_path(path)

    known = _KNOWN_PAGES.get(path_n, {})

    cms_title = ""

    cms_purpose = ""



    if cms_site:

        for item in (cms_site.get("nav") or []) + (cms_site.get("modules") or []):

            href = str(item.get("href") or "")

            if normalize_path(href) == path_n:

                cms_title = str(item.get("title") or item.get("label") or "")

                cms_purpose = str(item.get("description") or item.get("badge") or "")

                break



    display_title = title or cms_title or known.get("title") or path_n

    purpose = cms_purpose or known.get("purpose") or "صفحه‌ای از سامانه سازمانی."



    lines = [

        "موقعیت فعلی کاربر در سامانه:",

        f"- مسیر (URL path): {path_n}",

        f"- عنوان صفحه: {display_title}",

        f"- کاربرد صفحه: {purpose}",

        "اگر کاربر گفت «اینجا»، «این صفحه»، «این اطلاعات» یا مشابه، منظورش همین موقعیت است.",

    ]

    text = (page_text or "").strip()

    if text:

        lines.append("خلاصه متن/اطلاعات قابل‌مشاهده در صفحه:")

        lines.append(text[:4000])

    return "\n".join(lines)


