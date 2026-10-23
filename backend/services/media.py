from __future__ import annotations

import base64
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.documents import extract_text_from_file

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".heif"}
DOC_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md", ".csv", ".pptx"}
ALLOWED_EXTS = IMAGE_EXTS | DOC_EXTS

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
}

# امضای بایتی فایل — روی پسوند اعتماد نمی‌کنیم
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),  # docx/xlsx/pptx
    (b"\xd0\xcf\x11\xe0", "application/msword"),  # doc/xls قدیمی
]

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9\u0600-\u06FF._-]+")


def sniff_mime(raw: bytes) -> str:
    """تشخیص نوع واقعی فایل از بایت‌های اول."""
    head = raw[:16]
    for signature, mime in _MAGIC:
        if head.startswith(signature):
            return mime
    if raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypmsf1"):
        return "image/heic"
    # متن ساده
    try:
        raw[:512].decode("utf-8")
        return "text/plain"
    except Exception:
        return "application/octet-stream"


def safe_filename(filename: str | None, fallback: str = "upload.bin") -> str:
    """جلوگیری از path traversal و نویسه‌های خطرناک."""
    raw = (filename or fallback).replace("\\", "/").split("/")[-1]
    cleaned = _SAFE_NAME_RE.sub("_", raw).strip("._") or fallback
    return cleaned[:120]


def validate_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    """(نام امن، mime واقعی) — در صورت مشکل AppError می‌اندازد."""
    from backend.errors import AppError

    settings = get_settings()
    if not content:
        raise AppError("FILE_EMPTY")
    if len(content) > settings.upload_max_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE")

    name = safe_filename(filename)
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        raise AppError("FILE_TYPE_NOT_ALLOWED")

    real_mime = sniff_mime(content)
    if suffix in IMAGE_EXTS and not real_mime.startswith("image/"):
        raise AppError("FILE_TYPE_NOT_ALLOWED", message="محتوای فایل با پسوند تصویر هم‌خوان نیست.")
    if suffix == ".pdf" and real_mime != "application/pdf":
        raise AppError("FILE_TYPE_NOT_ALLOWED", message="این فایل PDF معتبر نیست.")
    if suffix in {".docx", ".xlsx", ".pptx"} and real_mime != "application/zip":
        raise AppError("FILE_TYPE_NOT_ALLOWED", message="این فایل آفیس معتبر نیست.")

    return name, real_mime


def save_upload(subdir: str, filename: str | None, content: bytes) -> dict[str, Any]:
    """ذخیره امن فایل در data/uploads/<subdir> و برگرداندن آدرس عمومی."""
    settings = get_settings()
    name, mime = validate_upload(filename, content)
    out_dir = settings.uploads_root / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:10]}_{name}"
    dest = out_dir / stored
    dest.write_bytes(content)
    return {
        "filename": name,
        "stored_name": stored,
        "mime": mime,
        "size": len(content),
        "path": str(dest),
        "url": f"/files/{subdir}/{stored}",
    }


def save_chat_upload(filename: str | None, content: bytes) -> Path:
    info = save_upload("chat", filename, content)
    return Path(info["path"])


def process_attachment(path: Path) -> dict[str, Any]:
    """استخراج متن از سند یا آماده‌سازی تصویر برای مدل."""
    suffix = path.suffix.lower()
    item: dict[str, Any] = {
        "filename": path.name,
        "path": str(path),
        "suffix": suffix,
        "kind": "other",
        "text": "",
        "image": None,
    }

    if suffix in DOC_EXTS:
        item["kind"] = "document"
        try:
            item["text"] = extract_text_from_file(path)[:20000]
        except Exception as exc:
            logger.warning("استخراج متن ناموفق %s: %s", path.name, exc)
            item["text"] = f"(نتوانستم متن {path.name} را بخوانم: {exc})"
        return item

    if suffix in IMAGE_EXTS:
        item["kind"] = "image"
        raw = path.read_bytes()
        mime = _MIME_BY_EXT.get(suffix) or sniff_mime(raw)
        raw, mime = _shrink_image_bytes(raw, mime)
        if len(raw) > 4_000_000:
            item["text"] = f"تصویر {path.name} خیلی بزرگ است؛ لطفاً فایل کوچک‌تری بفرست."
            return item
        item["image"] = {
            "mime": mime,
            "base64": base64.b64encode(raw).decode("ascii"),
            "filename": path.name,
        }
        item["text"] = f"کاربر تصویر «{path.name}» پیوست کرده است. محتوا را از روی تصویر بخوان و توضیح بده."
        return item

    item["text"] = f"فایل پیوست‌شده: {path.name} (فرمت پشتیبانی‌نشده برای استخراج متن)"
    return item


def _shrink_image_bytes(raw: bytes, mime: str) -> tuple[bytes, str]:
    """کوچک‌کردن تصویر بزرگ تا مدل گیر نکند."""
    if len(raw) <= 900_000:
        return raw, mime
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(raw))
        img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as exc:
        logger.debug("فشرده‌سازی تصویر ناموفق: %s", exc)
        return raw, mime
