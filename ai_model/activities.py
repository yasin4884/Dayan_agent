from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from core.chunking import split_into_chunks
from core.config import get_settings
from core.embedding import get_embedding_model
from core.rag import get_rag_pipeline
from core.search_engine import get_web_search_service
from core.vector_db import get_vector_db
from core.web_crawler import get_web_crawler

logger = logging.getLogger(__name__)


@activity.defn(name="chunk_text")
async def chunk_text_activity(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict[str, Any]]:
    """متن خام را با core.chunking به چانک تبدیل می‌کند."""
    activity.logger.info("شروع chunking")
    chunks = split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
    return [
        {
            "text": c.text,
            "index": c.index,
            "word_count": c.word_count,
        }
        for c in chunks
    ]


@activity.defn(name="embed_passages")
async def embed_passages_activity(texts: list[str]) -> list[list[float]]:
    """لیست متن‌ها را embed می‌کند (برای ایندکس سند)."""
    activity.logger.info("embed passages: %s قطعه", len(texts))
    embedder = get_embedding_model()
    return embedder.embed_passages(texts)


@activity.defn(name="embed_query")
async def embed_query_activity(query: str) -> list[float]:
    """کوئری کاربر را embed می‌کند."""
    embedder = get_embedding_model()
    return embedder.embed_query(query)


@activity.defn(name="upsert_chunks")
async def upsert_chunks_activity(
    document_id: str,
    texts: list[str],
    vectors: list[list[float]],
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """چانک‌ها را در Qdrant ذخیره می‌کند."""
    embedder = get_embedding_model()
    vdb = get_vector_db(vector_size=embedder.dimension)
    vdb.delete_document(document_id)
    count = vdb.upsert_chunks(
        document_id=document_id,
        texts=texts,
        vectors=vectors,
        extra_payload=extra_payload,
    )
    return {"document_id": document_id, "chunk_count": count}


@activity.defn(name="index_document")
async def index_document_activity(
    document_id: str,
    text: str,
    extra_payload: dict[str, Any] | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> dict[str, Any]:
    """
    پایپلاین کامل ایندکس:
    chunking -> embedding -> upsert در Qdrant
    """
    activity.logger.info("ایندکس سند: %s", document_id)

    chunks = split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise ValueError("بعد از chunking هیچ قطعه‌ای باقی نماند")

    texts = [c.text for c in chunks]
    embedder = get_embedding_model()
    vectors = embedder.embed_passages(texts)

    vdb = get_vector_db(vector_size=embedder.dimension)
    vdb.delete_document(document_id)
    count = vdb.upsert_chunks(
        document_id=document_id,
        texts=texts,
        vectors=vectors,
        extra_payload=extra_payload,
    )
    return {
        "document_id": document_id,
        "chunk_count": count,
        "chunks": [
            {"index": c.index, "word_count": c.word_count}
            for c in chunks
        ],
    }


@activity.defn(name="retrieve")
async def retrieve_activity(
    query: str,
    top_k: int = 8,
    document_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """جست‌وجوی برداری روی اسناد ایندکس‌شده."""
    rag = get_rag_pipeline()
    results = rag.retrieve(query=query, top_k=top_k, document_ids=document_ids)
    return [
        {
            "text": r.text,
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "score": r.score,
            "payload": r.payload,
        }
        for r in results
    ]


@activity.defn(name="crawl_web")
async def crawl_web_activity(
    query: str | None = None,
    start_url: str | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """کرال سایت تعریف‌شده در config (یا start_url اختیاری)."""
    crawler = get_web_crawler()
    pages = crawler.crawl(start_url=start_url, max_pages=max_pages, query=query)
    context = crawler.pages_to_context(pages)
    return {
        "page_count": len(pages),
        "context": context,
        "pages": [
            {"url": p.url, "title": p.title, "text": p.text[:1000]}
            for p in pages
        ],
    }


@activity.defn(name="web_search")
async def web_search_activity(query: str) -> dict[str, Any]:
    """جست‌وجو با موتور تعریف‌شده در SEARCH_ENGINE."""
    service = get_web_search_service()
    context, sources = service.search_and_collect(query)
    return {
        "engine": get_settings().search_engine,
        "context": context,
        "sources": sources,
    }


@activity.defn(name="ask_rag")
async def ask_rag_activity(
    query: str,
    top_k: int = 8,
    document_ids: list[str] | None = None,
    allow_web_fallback: bool = True,
) -> dict[str, Any]:
    """retrieve + در صورت نبود سند، کرال وب + تولید پاسخ."""
    rag = get_rag_pipeline()
    result = rag.ask(
        query=query,
        top_k=top_k,
        document_ids=document_ids,
        allow_web_fallback=allow_web_fallback,
    )
    return {
        "answer": result.answer,
        "context": result.context,
        "source_type": result.source_type,
        "sources": [
            {
                "text": s.text,
                "document_id": s.document_id,
                "chunk_index": s.chunk_index,
                "score": s.score,
                "payload": s.payload,
            }
            for s in result.sources
        ],
    }
