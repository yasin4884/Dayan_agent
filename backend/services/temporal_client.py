"""کلاینت Temporal برای ایندکس و کارهای پس‌زمینه."""

from __future__ import annotations

import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

_client = None
_client_failed = False


async def get_temporal_client():
    global _client, _client_failed
    if _client_failed:
        return None
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.temporal_host:
        _client_failed = True
        return None
    try:
        from temporalio.client import Client

        _client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        return _client
    except Exception as exc:
        logger.warning("اتصال Temporal ناموفق: %s", exc)
        _client_failed = True
        return None


def reset_temporal_client() -> None:
    global _client, _client_failed
    _client = None
    _client_failed = False


async def start_index_document(
    *,
    document_id: str,
    text: str,
    extra_payload: dict[str, Any] | None = None,
    stepwise: bool = True,
) -> dict[str, Any] | None:
    """اگر Temporal بالا باشد، ایندکس را از طریق workflow اجرا می‌کند."""
    client = await get_temporal_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        handle = await client.start_workflow(
            "IndexDocumentWorkflow",
            {
                "document_id": document_id,
                "text": text,
                "extra_payload": extra_payload or {},
                "chunk_size": settings.chunk_size_words,
                "overlap": settings.chunk_overlap_words,
                "stepwise": stepwise,
            },
            id=f"index-{document_id}-{int(__import__('time').time())}",
            task_queue=settings.temporal_task_queue,
        )
        return await handle.result()
    except Exception as exc:
        logger.warning("workflow ایندکس شکست: %s — fallback sync", exc)
        return None


async def temporal_ping() -> dict[str, Any]:
    settings = get_settings()
    info: dict[str, Any] = {
        "host": settings.temporal_host,
        "namespace": settings.temporal_namespace,
        "task_queue": settings.temporal_task_queue,
        "ok": False,
    }
    reset_temporal_client()
    client = await get_temporal_client()
    if client is None:
        info["error"] = "unreachable"
        return info
    info["ok"] = True
    return info
