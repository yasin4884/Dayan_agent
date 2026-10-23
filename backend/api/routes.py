from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from backend.api.deps import CurrentAdmin, CurrentUserOptional
from backend.errors import AppError
from backend.services.audit import log_audit
from backend.services.cms import get_cms
from backend.services.chat_service import get_chat_service
from backend.services.media import save_upload
from backend.services.rate_limit import limit_chat, limit_default
from backend.services.security import client_ip
from core.config import get_settings
from core.documents import analyze_transcript_text, extract_text_from_file

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=8000)
    session_id: str = Field(min_length=3, max_length=80)
    top_k: int = Field(default=4, ge=1, le=12)
    page_path: str | None = Field(default=None, max_length=200)
    page_title: str | None = Field(default=None, max_length=200)
    page_text: str | None = Field(default=None, max_length=12000)
    current_page: str | None = Field(default=None, max_length=80)


@router.get("/health")
async def health() -> dict[str, Any]:
    from ai_model.model import get_llm_service
    from backend.services.cms import get_cms
    from databases.mongo.memory import get_memory
    from databases.psql.base import db_health
    from databases.psql.client import check_postgres

    settings = get_settings()
    llm_ok = False
    model_name = ""
    try:
        llm = get_llm_service()
        llm_ok = llm.is_available()
        model_name = getattr(getattr(llm, "_provider", None), "model_name", "") or ""
    except Exception:
        llm_ok = False

    mongo_ok = False
    try:
        mem = get_memory()
        mongo_ok = mem._col is not None
    except Exception:
        mongo_ok = False

    pg_sync = check_postgres()
    orm = await db_health()

    qdrant_ok = False
    qdrant_count = 0
    try:
        from core.vector_db import get_vector_db

        vdb = get_vector_db()
        qdrant_count = int(vdb.count() or 0)
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    redis_ok = False
    try:
        from backend.services.rate_limit import _get_redis

        client = await _get_redis()
        redis_ok = client is not None
    except Exception:
        redis_ok = False

    kn = get_cms().load().get("knowledge") or {}
    crawl_url = str(kn.get("crawl_url") or kn.get("web_base_url") or "").strip()

    embedding_loaded = False
    embedding_dim = 0
    try:
        import core.embedding as emb_mod

        if emb_mod._instance is not None:
            embedding_loaded = True
            embedding_dim = int(getattr(emb_mod._instance, "dimension", 0) or 0)
    except Exception:
        embedding_loaded = False

    temporal_live = {"ok": False}
    try:
        from backend.services.temporal_client import temporal_ping

        temporal_live = await temporal_ping()
    except Exception as exc:
        temporal_live = {"ok": False, "error": str(exc)[:120]}

    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_available": llm_ok,
        "model_name": model_name,
        "embedding": {
            "loaded": embedding_loaded,
            "model_name": settings.embedding_model_name,
            "dimension": embedding_dim,
            "chunk_size_words": settings.chunk_size_words,
            "chunk_overlap_words": settings.chunk_overlap_words,
            "note": "با استارت API گرم می‌شود؛ ایندکس از چانکینگ + امبد استفاده می‌کند",
        },
        "mongo": {"ok": mongo_ok, "fallback_file": not mongo_ok},
        "postgres": pg_sync,
        "database": orm,
        "redis": {"ok": redis_ok, "url": settings.redis_url or None},
        "qdrant": {"ok": qdrant_ok, "chunks": qdrant_count},
        "search": {
            "engine": settings.search_engine,
            "crawl_enabled": bool(kn.get("crawl_enabled")),
            "crawl_url": crawl_url,
        },
        "rag": {"enabled": bool(settings.rag_enabled)},
        "temporal": {
            "configured": bool(settings.temporal_host),
            "ok": bool(temporal_live.get("ok")),
            "host": settings.temporal_host,
            "namespace": settings.temporal_namespace,
            "task_queue": settings.temporal_task_queue,
            "detail": temporal_live,
            "note": "worker: python -m temporal.worker",
        },
    }


@router.get("/public/site")
async def public_site(
    group_id: str | None = None,
    user: CurrentUserOptional = None,  # Depends از Annotated می‌آید
) -> dict[str, Any]:
    gid = group_id or (user.group_id if user else None)
    return get_cms().public_view(gid)


@router.get("/admin/site")
async def admin_get_site(_: CurrentAdmin) -> dict[str, Any]:
    return get_cms().load()


@router.put("/admin/site")
async def admin_put_site(
    payload: dict[str, Any],
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    saved = get_cms().save(payload)
    await log_audit(
        "cms.replace",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target="site",
        detail={"keys": sorted(payload.keys())},
    )
    return saved


@router.patch("/admin/site")
async def admin_patch_site(
    payload: dict[str, Any],
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    saved = get_cms().patch(payload)
    await log_audit(
        "cms.patch",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target="site",
        detail={"keys": sorted(payload.keys())},
    )
    return saved


@router.post("/admin/upload")
async def admin_upload_media(
    request: Request,
    admin: CurrentAdmin,
    file: UploadFile = File(...),
    kind: str = Form("media"),
) -> dict[str, Any]:
    """آپلود لوگو / تصویر بنر / سند بخشنامه — نوع فایل با امضای بایتی بررسی می‌شود."""
    await limit_default(request, "admin_upload")
    allowed_kinds = {"logo", "banner", "circular", "form", "media", "knowledge"}
    subdir = kind if kind in allowed_kinds else "media"
    info = save_upload(subdir, file.filename, await file.read())
    await log_audit(
        "media.upload",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=info["url"],
        detail={"kind": subdir, "mime": info["mime"], "size": info["size"]},
    )
    return info


@router.post("/admin/forms")
async def admin_upload_form(
    request: Request,
    admin: CurrentAdmin,
    title: str = Form(..., min_length=2, max_length=250),
    slug: str = Form(..., min_length=2, max_length=120),
    description: str = Form("", max_length=600),
    group_ids: str = Form(""),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """آپلود فرم — ایجنت بعداً همین‌ها را به کاربر می‌دهد."""
    await limit_default(request, "admin_upload")
    info = save_upload("form", file.filename, await file.read())

    text = ""
    try:
        text = extract_text_from_file(Path(info["path"]))
    except Exception:
        text = ""

    groups = [g.strip() for g in group_ids.split(",") if g.strip()]
    cms = get_cms()
    site = cms.load()
    forms = [f for f in (site.get("forms") or []) if f.get("slug") != slug]
    item = {
        "id": slug,
        "slug": slug,
        "title": title,
        "description": description,
        "group_ids": groups,
        "filename": info["filename"],
        "file_url": info["url"],
        "enabled": True,
        "text_preview": text[:2000],
    }
    forms.append(item)
    site["forms"] = forms
    cms.save(site)

    if text.strip():
        try:
            from backend.services.knowledge import get_knowledge_service

            get_knowledge_service().ingest_text(
                document_id=f"form:{slug}",
                text=f"عنوان فرم: {title}\nتوضیح: {description}\nمسیر دانلود: {info['url']}\n\n{text}",
                title=title,
                kind="form",
                extra={"slug": slug, "file_url": info["url"], "source": "form"},
            )
            item["indexed"] = True
        except Exception as exc:
            item["indexed"] = False
            item["index_error"] = str(exc)[:200]
    else:
        # حتی بدون استخراج متن، عنوان/توضیح را ایندکس کن تا ربات فرم را بشناسد
        try:
            from backend.services.knowledge import get_knowledge_service

            get_knowledge_service().ingest_text(
                document_id=f"form:{slug}",
                text=f"عنوان فرم: {title}\nتوضیح: {description}\nمسیر دانلود: {info['url']}\nفایل: {info['filename']}",
                title=title,
                kind="form",
                extra={"slug": slug, "file_url": info["url"], "source": "form"},
            )
            item["indexed"] = True
            item["index_note"] = "متن فایل استخراج نشد؛ عنوان و توضیح ایندکس شد."
        except Exception as exc:
            item["indexed"] = False
            item["index_error"] = str(exc)[:200]

    # لیست را دوباره ذخیره کن با وضعیت ایندکس
    site = cms.load()
    forms = [f for f in (site.get("forms") or []) if f.get("slug") != slug]
    forms.append(item)
    site["forms"] = forms
    cms.save(site)

    await log_audit(
        "form.upload",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=slug,
        detail={"indexed": item.get("indexed")},
    )
    return item


@router.post("/admin/forms/reindex")
async def admin_reindex_forms(request: Request, admin: CurrentAdmin) -> dict[str, Any]:
    """ایندکس دوباره همه فرم‌ها در دانش ربات (همان پروسس API / Qdrant)."""
    await limit_default(request, "admin_upload")
    from backend.services.knowledge import get_knowledge_service

    cms = get_cms()
    site = cms.load()
    forms = list(site.get("forms") or [])
    ks = get_knowledge_service()
    ok = 0
    failed = 0
    for item in forms:
        slug = str(item.get("slug") or item.get("id") or "").strip()
        if not slug:
            continue
        title = str(item.get("title") or slug)
        description = str(item.get("description") or "")
        url = str(item.get("file_url") or "")
        preview = str(item.get("text_preview") or "")
        text = (
            f"عنوان فرم: {title}\nتوضیح: {description}\nمسیر دانلود: {url}\n\n{preview}"
        ).strip()
        try:
            ks.ingest_text(
                document_id=f"form:{slug}",
                text=text,
                title=title,
                kind="form",
                extra={"slug": slug, "file_url": url, "source": "form"},
            )
            item["indexed"] = True
            item.pop("index_error", None)
            ok += 1
        except Exception as exc:
            item["indexed"] = False
            item["index_error"] = str(exc)[:200]
            failed += 1

    site["forms"] = forms
    cms.save(site)
    await log_audit(
        "form.reindex",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        detail={"ok": ok, "failed": failed},
    )
    return {"ok": ok, "failed": failed, "forms": forms}


@router.get("/admin/logs")
async def admin_logs(_: CurrentAdmin, limit: int = 100) -> list[dict[str, Any]]:
    """لاگ عملیات حساس برای پنل ادمین."""
    from backend.services.audit import get_audit

    return get_audit().recent(min(max(limit, 1), 500))


@router.get("/forms")
async def list_forms(
    user: CurrentUserOptional = None,
    group_id: str | None = None,
) -> list[dict[str, Any]]:
    gid = group_id or (user.group_id if user else None)
    return get_cms().public_view(gid).get("forms") or []


@router.get("/notifications")
async def list_notifications(
    user: CurrentUserOptional = None,
    group_id: str | None = None,
    sort: str = "newest",
) -> list[dict[str, Any]]:
    """اطلاع‌رسانی‌های گروه کاربر — قابل مرتب‌سازی."""
    gid = group_id or (user.group_id if user else None)
    items = list(get_cms().public_view(gid).get("notifications") or [])
    reverse = sort != "oldest"
    items.sort(key=lambda n: (not n.get("pinned"), str(n.get("created_at") or "")), reverse=False)
    if reverse:
        pinned = [n for n in items if n.get("pinned")]
        rest = sorted(
            [n for n in items if not n.get("pinned")],
            key=lambda n: str(n.get("created_at") or ""),
            reverse=True,
        )
        return pinned + rest
    return items


@router.get("/circulars")
async def list_circulars(
    user: CurrentUserOptional = None,
    group_id: str | None = None,
) -> list[dict[str, Any]]:
    gid = group_id or (user.group_id if user else None)
    return get_cms().public_view(gid).get("circulars") or []


@router.get("/professors")
async def list_professors(
    user: CurrentUserOptional = None,
    group_id: str | None = None,
) -> list[dict[str, Any]]:
    gid = group_id or (user.group_id if user else None)
    items = list(get_cms().public_view(gid).get("professors") or [])
    items.sort(key=lambda p: float(p.get("score") or 0), reverse=True)
    return items


@router.get("/calendar")
async def get_calendar(
    user: CurrentUserOptional = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    gid = group_id or (user.group_id if user else None)
    return get_cms().public_view(gid).get("calendar") or {"title": "", "events": []}


@router.get("/forms/{slug}")
async def get_form(slug: str) -> dict[str, Any]:
    for item in get_cms().load().get("forms") or []:
        if item.get("slug") == slug:
            return item
    raise AppError("NOT_FOUND", message="فرم پیدا نشد.")


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    user: CurrentUserOptional = ...,
) -> dict[str, Any]:
    if not (body.message or "").strip():
        raise AppError("VALIDATION_ERROR", message="پیام خالی است.")
    identity = user.id if user else None
    await limit_chat(request, identity=identity)

    page_path = body.page_path or body.current_page or "/"
    service = get_chat_service()
    user_payload = None
    if user is not None:
        user_payload = {
            "id": user.id,
            "full_name": user.full_name,
            "group_id": user.group_id,
            "role": "user",
        }
    return service.ask(
        message=body.message,
        session_id=body.session_id,
        user=user_payload,
        top_k=body.top_k,
        page_path=page_path,
        page_title=body.page_title,
        page_text=body.page_text,
    )


@router.post("/chat/upload")
async def chat_upload(
    request: Request,
    user: CurrentUserOptional = ...,
    session_id: str = Form(..., min_length=3, max_length=80),
    message: str = Form(""),
    page_path: str = Form("/"),
    page_title: str = Form(""),
    page_text: str = Form(""),
    current_page: str = Form(""),
    top_k: int = Form(4),
    files: Annotated[list[UploadFile], File()] = [],
) -> dict[str, Any]:
    """چت با پیوست تصویر/PDF/سند."""
    from backend.services.media import process_attachment, save_chat_upload

    identity = user.id if user else None
    await limit_chat(request, identity=identity)

    upload_files = list(files or [])
    if not upload_files and not (message or "").strip():
        raise AppError("VALIDATION_ERROR", message="پیام یا فایل لازم است.")

    settings = get_settings()
    max_bytes = settings.upload_max_mb * 1024 * 1024
    attachments: list[dict[str, Any]] = []
    for f in upload_files:
        raw = await f.read()
        if not raw:
            continue
        if len(raw) > max_bytes:
            raise AppError("FILE_TOO_LARGE")
        path = save_chat_upload(f.filename, raw)
        attachments.append(process_attachment(path))

    service = get_chat_service()
    user_payload = None
    if user is not None:
        user_payload = {
            "id": user.id,
            "full_name": user.full_name,
            "group_id": user.group_id,
            "role": "user",
        }
    return service.ask(
        message=message or "این فایل / تصویر پیوست را بررسی و توضیح بده.",
        session_id=session_id,
        user=user_payload,
        top_k=top_k,
        page_path=page_path or current_page or "/",
        page_title=page_title or None,
        page_text=page_text or None,
        attachments=attachments,
    )


@router.post("/transcript/analyze")
async def analyze_transcript(
    request: Request,
    user: CurrentUserOptional = ...,
    file: UploadFile = File(...),
    session_id: str = Form("transcript-session"),
) -> dict[str, Any]:
    await limit_chat(request, identity=user.id if user else None)
    settings = get_settings()
    out_dir = settings.uploads_root / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = await file.read()
    if not raw:
        raise AppError("FILE_EMPTY")
    if len(raw) > settings.upload_max_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE")
    dest = out_dir / (file.filename or "transcript.bin")
    dest.write_bytes(raw)
    text = extract_text_from_file(dest)
    stats = analyze_transcript_text(text)
    chat_svc = get_chat_service()
    user_payload = None
    if user is not None:
        user_payload = {
            "id": user.id,
            "full_name": user.full_name,
            "group_id": user.group_id,
            "role": "user",
        }
    analysis = chat_svc.analyze_document(
        session_id=session_id,
        user=user_payload,
        document_text=text,
        kind="کارنامه",
    )
    return {"stats": stats, "analysis": analysis}
