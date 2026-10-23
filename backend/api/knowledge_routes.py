from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from backend.api.deps import CurrentAdmin
from backend.errors import AppError
from backend.services.audit import log_audit
from backend.services.knowledge import get_knowledge_service
from backend.services.media import save_upload
from backend.services.rate_limit import limit_default
from backend.services.security import client_ip

router = APIRouter(tags=["knowledge"])


class KnowledgeSettingsIn(BaseModel):
    web_base_url: str = Field(default="", max_length=400)
    crawl_url: str = Field(default="", max_length=400)
    crawl_enabled: bool = False


class KnowledgeRulesIn(BaseModel):
    rules: list[str] = Field(default_factory=list, max_length=80)


class KnowledgeCrawlIn(BaseModel):
    url: str | None = Field(default=None, max_length=400)
    max_pages: int | None = Field(default=None, ge=1, le=40)


@router.get("/admin/knowledge")
async def admin_knowledge(_: CurrentAdmin) -> dict[str, Any]:
    return get_knowledge_service().snapshot()


@router.patch("/admin/knowledge/settings")
async def admin_knowledge_settings(
    payload: KnowledgeSettingsIn,
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    saved = get_knowledge_service().save_settings(
        payload.web_base_url,
        payload.crawl_enabled,
        crawl_url=payload.crawl_url,
    )
    await log_audit(
        "knowledge.settings",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=payload.crawl_url or payload.web_base_url,
    )
    return saved


@router.put("/admin/knowledge/rules")
async def admin_knowledge_rules(
    payload: KnowledgeRulesIn,
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    saved = await asyncio.to_thread(get_knowledge_service().save_rules, payload.rules)
    await log_audit(
        "knowledge.rules",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target="ai_rules",
    )
    return saved


@router.post("/admin/knowledge/upload")
async def admin_knowledge_upload(
    request: Request,
    admin: CurrentAdmin,
    file: UploadFile = File(...),
    title: str = Form(""),
    kind: str = Form("knowledge"),
) -> dict[str, Any]:
    """Word / Excel / PDF → استخراج متن، چانک، امبد در Qdrant."""
    await limit_default(request, "admin_upload")
    if kind not in {"knowledge", "rule"}:
        kind = "knowledge"
    info = save_upload("knowledge", file.filename, await file.read())
    try:
        item = await asyncio.to_thread(
            get_knowledge_service().ingest_file,
            Path(info["path"]),
            title=title.strip() or info["filename"],
            kind=kind,
            filename=info["filename"],
            file_url=info["url"],
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "TEXT_EXTRACT_FAILED",
            message=f"فایل ذخیره شد ولی ایندکس نشد: {exc}",
        ) from exc

    await log_audit(
        "knowledge.upload",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=item.get("id"),
        detail={"kind": kind, "chunks": item.get("chunk_count")},
    )
    return item


@router.post("/admin/knowledge/crawl")
async def admin_knowledge_crawl(
    payload: KnowledgeCrawlIn,
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    result = await asyncio.to_thread(
        get_knowledge_service().crawl_and_index,
        payload.url,
        payload.max_pages,
    )
    await log_audit(
        "knowledge.crawl",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=payload.url or "",
        detail={"indexed_pages": result.get("indexed_pages")},
    )
    return result


@router.delete("/admin/knowledge/{document_id:path}")
async def admin_knowledge_delete(
    document_id: str,
    request: Request,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    await limit_default(request, "admin_write")
    saved = get_knowledge_service().delete(document_id)
    await log_audit(
        "knowledge.delete",
        actor_id=admin.id,
        actor_type="admin",
        ip=client_ip(request),
        target=document_id,
    )
    return saved
