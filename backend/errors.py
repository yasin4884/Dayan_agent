from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# error_code -> (کد وضعیت، پیام فارسی)
ERROR_CATALOG: dict[str, tuple[int, str]] = {
    # احراز هویت
    "INVALID_CREDENTIALS": (401, "نام کاربری یا رمز عبور اشتباه است."),
    "AUTH_REQUIRED": (401, "برای این کار باید وارد حساب خود شوید."),
    "TOKEN_INVALID": (401, "نشست شما معتبر نیست. دوباره وارد شوید."),
    "TOKEN_EXPIRED": (401, "نشست شما منقضی شده است. دوباره وارد شوید."),
    "REFRESH_INVALID": (401, "توکن تازه‌سازی معتبر نیست. دوباره وارد شوید."),
    "ACCOUNT_DISABLED": (403, "حساب شما غیرفعال شده است. با پشتیبانی تماس بگیرید."),
    "ADMIN_ONLY": (403, "این بخش فقط برای ادمین است."),
    "FORBIDDEN": (403, "شما به این بخش دسترسی ندارید."),
    # ثبت‌نام
    "USERNAME_TAKEN": (409, "این نام کاربری قبلاً ثبت شده است."),
    "STUDENT_CODE_TAKEN": (409, "این کد دانشجویی قبلاً ثبت شده است."),
    "PERSONNEL_CODE_TAKEN": (409, "این شماره پرسنلی قبلاً ثبت شده است."),
    "PASSWORD_MISMATCH": (422, "رمز عبور و تکرار آن یکسان نیستند."),
    "PASSWORD_WEAK": (422, "رمز عبور باید حداقل ۸ کاراکتر و شامل حرف و عدد باشد."),
    "WRONG_PASSWORD": (401, "رمز فعلی اشتباه است."),
    "GROUP_INVALID": (422, "گروه انتخابی معتبر نیست."),
    "GROUP_REQUIRED": (422, "انتخاب گروه الزامی است."),
    # داده
    "NOT_FOUND": (404, "موردی که خواستید پیدا نشد."),
    "ALREADY_EXISTS": (409, "این مورد قبلاً ثبت شده است."),
    "VALIDATION_ERROR": (422, "اطلاعات ارسالی نامعتبر است."),
    # فایل
    "FILE_TOO_LARGE": (413, "حجم فایل بیش از حد مجاز است."),
    "FILE_TYPE_NOT_ALLOWED": (415, "این نوع فایل پشتیبانی نمی‌شود."),
    "FILE_EMPTY": (422, "فایل ارسالی خالی است."),
    "TEXT_EXTRACT_FAILED": (422, "متن این فایل استخراج نشد. فرمت Word، Excel یا PDF بفرستید."),
    "CRAWL_URL_REQUIRED": (422, "آدرس سایت دانشگاه را وارد کنید."),
    # تیکت و پشتیبانی
    "TICKET_CLOSED": (409, "این تیکت بسته شده است."),
    "TOO_MANY_OPEN_TICKETS": (429, "تعداد تیکت‌های باز شما زیاد است."),
    # اعلان
    "PUSH_NOT_CONFIGURED": (503, "سرویس اعلان هنوز تنظیم نشده است."),
    "PUSH_SUBSCRIPTION_INVALID": (422, "اطلاعات اشتراک اعلان نامعتبر است."),
    # سرویس
    "PAYLOAD_TOO_LARGE": (413, "حجم درخواست بیش از حد مجاز است."),
    "RATE_LIMITED": (429, "تعداد درخواست‌های شما زیاد بود. کمی بعد دوباره تلاش کنید."),
    "MODEL_UNAVAILABLE": (503, "دستیار در دسترس نیست. کمی بعد دوباره تلاش کنید."),
    "DB_UNAVAILABLE": (503, "ارتباط با دیتابیس برقرار نشد. کمی بعد دوباره تلاش کنید."),
    "INTERNAL_ERROR": (500, "خطای غیرمنتظره‌ای رخ داد. لطفاً بعداً تلاش کنید."),
}


class AppError(Exception):
    """خطای دامنه‌ای با کد مشخص و پیام فارسی."""

    def __init__(
        self,
        error_code: str,
        message: str | None = None,
        status_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ):
        fallback = ERROR_CATALOG.get(error_code) or ERROR_CATALOG["INTERNAL_ERROR"]
        self.error_code = error_code
        self.status_code = status_code or fallback[0]
        self.message = message or fallback[1]
        self.extra = extra or {}
        super().__init__(self.message)


def error_body(error_code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error_code": error_code, "message": message}
    if extra:
        body.update(extra)
    return body


_FIELD_FA: dict[str, str] = {
    "username": "نام کاربری",
    "password": "رمز عبور",
    "password_confirm": "تکرار رمز عبور",
    "first_name": "نام",
    "last_name": "نام خانوادگی",
    "full_name": "نام و نام خانوادگی",
    "student_code": "کد دانشجویی",
    "personnel_code": "شماره پرسنلی",
    "group_id": "گروه",
    "email": "ایمیل",
    "message": "پیام",
    "session_id": "شناسه گفتگو",
    "current_page": "صفحه فعلی",
    "title": "عنوان",
    "body": "متن",
    "slug": "شناسه",
    "url": "لینک",
    "event_date": "تاریخ",
    "subject": "موضوع",
    "refresh_token": "توکن تازه‌سازی",
    "target_groups": "گروه‌های هدف",
}


def _field_label(loc: list[Any]) -> str:
    parts = [str(x) for x in loc if x not in {"body", "query", "path", "header"}]
    if not parts:
        return "اطلاعات ارسالی"
    key = parts[-1]
    return _FIELD_FA.get(key, key)


def _validation_message(err: dict[str, Any]) -> str:
    field = _field_label(list(err.get("loc") or []))
    typ = str(err.get("type", ""))
    ctx = err.get("ctx") or {}

    if typ == "missing":
        return f"{field} الزامی است."
    if "too_short" in typ or "min_length" in typ:
        limit = ctx.get("min_length")
        return f"{field} کوتاه است." if limit is None else f"{field} باید حداقل {limit} کاراکتر باشد."
    if "too_long" in typ or "max_length" in typ:
        limit = ctx.get("max_length")
        return f"{field} بلند است." if limit is None else f"{field} باید حداکثر {limit} کاراکتر باشد."
    if "pattern" in typ or "string_pattern" in typ:
        return f"قالب {field} درست نیست."
    if "email" in typ:
        return "قالب ایمیل درست نیست."
    if "int" in typ or "float" in typ or "number" in typ:
        return f"{field} باید عدد باشد."
    if "bool" in typ:
        return f"{field} باید بله/خیر باشد."
    if "date" in typ:
        return f"قالب {field} درست نیست."
    if "greater_than" in typ:
        return f"{field} باید بزرگ‌تر باشد."
    if "less_than" in typ:
        return f"{field} باید کوچک‌تر باشد."
    if "enum" in typ or "literal" in typ:
        return f"مقدار {field} مجاز نیست."
    return f"مقدار {field} نامعتبر است."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.error_code, exc.message, exc.extra),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [_validation_message(e) for e in exc.errors()]
        message = "؛ ".join(dict.fromkeys(details)) or ERROR_CATALOG["VALIDATION_ERROR"][1]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", message, {"fields": details}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        # پیام‌های دستی فارسی را نگه می‌داریم؛ بقیه از کاتالوگ می‌آید
        by_status = {
            401: "AUTH_REQUIRED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "VALIDATION_ERROR",
            409: "ALREADY_EXISTS",
            413: "FILE_TOO_LARGE",
            415: "FILE_TYPE_NOT_ALLOWED",
            429: "RATE_LIMITED",
        }
        code = by_status.get(exc.status_code, "INTERNAL_ERROR")
        detail = exc.detail if isinstance(exc.detail, str) else ""
        has_persian = any("\u0600" <= ch <= "\u06ff" for ch in detail)
        message = detail if has_persian else ERROR_CATALOG.get(code, ERROR_CATALOG["INTERNAL_ERROR"])[1]
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
        )

    @app.exception_handler(HTTPException)
    async def _fastapi_http(request: Request, exc: HTTPException):
        return await _http(request, exc)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("خطای مدیریت‌نشده در %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", ERROR_CATALOG["INTERNAL_ERROR"][1]),
        )
