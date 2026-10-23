from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.errors import AppError
from backend.services.cms import get_cms
from core.documents import extract_text_from_file
from core.rag import get_rag_pipeline
from core.web_crawler import get_web_crawler

logger = logging.getLogger(__name__)

_ALLOWED_KINDS = {"knowledge", "rule", "form", "web"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _knowledge(site: dict[str, Any]) -> dict[str, Any]:
    raw = site.get("knowledge")
    if not isinstance(raw, dict):
        raw = {}
    web = str(raw.get("web_base_url") or "").strip()
    crawl = str(raw.get("crawl_url") or "").strip() or web
    return {
        "web_base_url": web,
        "crawl_url": crawl,
        "crawl_enabled": bool(raw.get("crawl_enabled")),
        "documents": list(raw.get("documents") or []),
    }


class KnowledgeService:
    def __init__(self):
        self.cms = get_cms()

    def snapshot(self) -> dict[str, Any]:
        site = self.cms.load()
        kn = _knowledge(site)
        return {
            "web_base_url": kn["web_base_url"],
            "crawl_url": kn["crawl_url"],
            "crawl_enabled": kn["crawl_enabled"],
            "documents": kn["documents"],
            "rules": site.get("ai_rules") or [],
            "home_website_url": str((site.get("brand") or {}).get("website_url") or "").strip(),
        }

    def save_settings(
        self,
        web_base_url: str,
        crawl_enabled: bool,
        crawl_url: str | None = None,
    ) -> dict[str, Any]:
        def _ok(url: str) -> str:
            u = (url or "").strip()
            if not u:
                return ""
            parsed = urlparse(u)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise AppError("VALIDATION_ERROR", message="آدرس باید با http یا https شروع شود.")
            return u

        web = _ok(web_base_url)
        crawl = _ok(crawl_url if crawl_url is not None else "") or web
        site = self.cms.load()
        kn = _knowledge(site)
        kn["web_base_url"] = web
        kn["crawl_url"] = crawl
        kn["crawl_enabled"] = bool(crawl_enabled)
        site["knowledge"] = kn
        self.cms.save(site)
        return self.snapshot()

    def save_rules(self, rules: list[str]) -> dict[str, Any]:
        cleaned = [r.strip() for r in rules if isinstance(r, str) and r.strip()]
        site = self.cms.load()
        site["ai_rules"] = cleaned
        self.cms.save(site)
        text = "\n".join(cleaned)
        if text:
            self._index_text(
                document_id="cms:ai_rules",
                text=text,
                title="قوانین دستیار",
                kind="rule",
                extra={"source": "rules"},
                upsert_meta=True,
            )
        else:
            self.delete("cms:ai_rules")
        return self.snapshot()

    def ingest_file(
        self,
        path: Path,
        *,
        title: str,
        kind: str,
        filename: str,
        file_url: str = "",
        document_id: str | None = None,
    ) -> dict[str, Any]:
        kind = kind if kind in _ALLOWED_KINDS else "knowledge"
        try:
            text = extract_text_from_file(path)
        except ValueError as exc:
            raise AppError("TEXT_EXTRACT_FAILED", message=str(exc)) from exc
        except Exception as exc:
            logger.warning("extract failed %s: %s", path, exc)
            raise AppError("TEXT_EXTRACT_FAILED") from exc

        if not (text or "").strip():
            raise AppError("TEXT_EXTRACT_FAILED", message="متن قابل ایندکس در این فایل پیدا نشد.")

        doc_id = document_id or f"doc-{uuid.uuid4().hex[:12]}"
        return self._index_text(
            document_id=doc_id,
            text=text,
            title=title or filename or "سند",
            kind=kind,
            extra={"filename": filename, "file_url": file_url},
            upsert_meta=True,
            filename=filename,
            file_url=file_url,
        )

    def ingest_text(
        self,
        *,
        document_id: str,
        text: str,
        title: str,
        kind: str = "knowledge",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not (text or "").strip():
            return {}
        return self._index_text(
            document_id=document_id,
            text=text,
            title=title,
            kind=kind,
            extra=extra,
            upsert_meta=True,
        )

    def crawl_and_index(self, start_url: str | None = None, max_pages: int | None = None) -> dict[str, Any]:
        site = self.cms.load()
        kn = _knowledge(site)
        url = (start_url or kn.get("crawl_url") or kn.get("web_base_url") or "").strip()
        if not url:
            raise AppError("CRAWL_URL_REQUIRED")

        kn["crawl_url"] = url
        if not kn.get("web_base_url"):
            kn["web_base_url"] = url
        kn["crawl_enabled"] = True
        site["knowledge"] = kn
        self.cms.save(site)

        crawler = get_web_crawler()
        pages = crawler.crawl(start_url=url, max_pages=max_pages)
        indexed: list[dict[str, Any]] = []
        for page in pages:
            if not page.text.strip():
                continue
            doc_id = f"web:{page.url}"
            item = self._index_text(
                document_id=doc_id,
                text=page.text,
                title=page.title or page.url,
                kind="web",
                extra={"source_url": page.url, "source": "crawl"},
                upsert_meta=True,
                source_url=page.url,
            )
            indexed.append(item)
        snap = self.snapshot()
        snap["crawled_pages"] = len(pages)
        snap["indexed_pages"] = len(indexed)
        return snap

    def delete(self, document_id: str) -> dict[str, Any]:
        if not document_id:
            raise AppError("NOT_FOUND")
        try:
            get_rag_pipeline().vector_db.delete_document(document_id)
        except Exception as exc:
            logger.warning("delete vectors %s: %s", document_id, exc)
        site = self.cms.load()
        kn = _knowledge(site)
        kn["documents"] = [d for d in kn["documents"] if d.get("id") != document_id]
        site["knowledge"] = kn
        self.cms.save(site)
        return self.snapshot()

    def _index_text(
        self,
        *,
        document_id: str,
        text: str,
        title: str,
        kind: str,
        extra: dict[str, Any] | None = None,
        upsert_meta: bool = True,
        filename: str = "",
        file_url: str = "",
        source_url: str = "",
        use_temporal: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "title": title,
            "kind": kind,
            "source": (extra or {}).get("source") or kind,
            **(extra or {}),
        }
        chunk_count = 0
        via = "sync"
        if use_temporal:
            try:
                import asyncio

                from backend.services.temporal_client import start_index_document

                async def _run():
                    return await start_index_document(
                        document_id=document_id,
                        text=text,
                        extra_payload=payload,
                        stepwise=True,
                    )

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                result_t = None
                if loop and loop.is_running():
                    # از مسیر sync داخل event loop صدا زده شده — concurrent future
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        result_t = pool.submit(lambda: asyncio.run(_run())).result(timeout=600)
                else:
                    result_t = asyncio.run(_run())
                if result_t and result_t.get("chunk_count") is not None:
                    chunk_count = int(result_t["chunk_count"])
                    via = "temporal"
            except Exception as exc:
                logger.warning("ایندکس Temporal ناموفق؛ sync: %s", exc)
                via = "sync"

        if via == "sync":
            result = get_rag_pipeline().index_document(
                document_id=document_id,
                text=text,
                extra_payload=payload,
            )
            chunk_count = int(result.chunk_count or 0)

        meta = {
            "id": document_id,
            "title": title,
            "kind": kind,
            "filename": filename,
            "file_url": file_url,
            "source_url": source_url,
            "chunk_count": chunk_count,
            "indexed_via": via,
            "created_at": _now(),
        }
        if upsert_meta:
            self._upsert_document_meta(meta)
        return meta

    def _upsert_document_meta(self, meta: dict[str, Any]) -> None:
        site = self.cms.load()
        kn = _knowledge(site)
        docs = [d for d in kn["documents"] if d.get("id") != meta["id"]]
        docs.append(meta)
        kn["documents"] = docs
        site["knowledge"] = kn
        self.cms.save(site)


_svc: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _svc
    if _svc is None:
        _svc = KnowledgeService()
    return _svc
