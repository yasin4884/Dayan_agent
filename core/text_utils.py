from __future__ import annotations

# ارقام فارسی/عربی -> لاتین (کاربر ایرانی معمولاً با کیبورد فارسی عدد می‌زند)
_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹" "٠١٢٣٤٥٦٧٨٩",
    "0123456789" "0123456789",
)

# نویسه‌های عربی -> فارسی استاندارد
_CHAR_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ﻻ": "لا", "\u200c": " "})


def normalize_digits(value: str | None) -> str:
    if not value:
        return ""
    return value.translate(_DIGIT_MAP)


def normalize_text(value: str | None) -> str:
    """فاصله‌های اضافه، ارقام و نویسه‌های عربی را یکدست می‌کند."""
    if not value:
        return ""
    cleaned = value.translate(_DIGIT_MAP).translate(_CHAR_MAP)
    return " ".join(cleaned.split())


def normalize_identifier(value: str | None) -> str:
    """برای نام کاربری / کد دانشجویی / کد پرسنلی: بدون فاصله و حروف کوچک."""
    return normalize_digits((value or "").strip()).replace(" ", "").lower()
