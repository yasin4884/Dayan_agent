from __future__ import annotations

import logging
from dataclasses import dataclass

from ai_model.model import LLMService
from core.chunking import TextChunk, split_into_chunks
from core.config import get_settings
from core.embedding import EmbeddingModel, get_embedding_model
from core.vector_db import SearchResult, VectorDB, get_vector_db
from core.web_crawler import WebCrawler, get_web_crawler
from core.search_engine import WebSearchService, get_web_search_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IndexResult:
    document_id: str
    chunk_count: int


@dataclass(frozen=True, slots=True)
class RAGAnswer:
    answer: str
    sources: list[SearchResult]
    context: str
    source_type: str  # "documents" | "web" | "none"


class RAGPipeline:
    def __init__(
        self,
        embedder: EmbeddingModel | None = None,
        vector_db: VectorDB | None = None,
        llm: LLMService | None = None,
        crawler: WebCrawler | None = None,
        web_search: WebSearchService | None = None,
    ):
        self._embedder = embedder
        self._vector_db = vector_db
        self._llm = llm
        self._crawler = crawler
        self._web_search = web_search

    @property
    def embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = get_embedding_model()
        return self._embedder

    @property
    def vector_db(self) -> VectorDB:
        if self._vector_db is None:
            self._vector_db = get_vector_db(vector_size=self.embedder.dimension)
        return self._vector_db

    @property
    def llm(self) -> LLMService:
        if self._llm is None:
            from ai_model.model import get_llm_service

            self._llm = get_llm_service()
        return self._llm

    @property
    def crawler(self) -> WebCrawler:
        if self._crawler is None:
            self._crawler = get_web_crawler()
        return self._crawler

    @property
    def web_search(self) -> WebSearchService:
        if self._web_search is None:
            self._web_search = get_web_search_service()
        return self._web_search

    def index_document(
        self,
        document_id: str,
        text: str,
        extra_payload: dict | None = None,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> IndexResult:
        if not document_id or not document_id.strip():
            raise ValueError("document_id خالی است")
        if not text or not text.strip():
            raise ValueError("متن سند خالی است")

        chunks: list[TextChunk] = split_into_chunks(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        if not chunks:
            raise ValueError("بعد از chunking هیچ قطعه‌ای باقی نماند")

        texts = [c.text for c in chunks]
        vectors = self.embedder.embed_passages(texts)

        self.vector_db.delete_document(document_id)
        count = self.vector_db.upsert_chunks(
            document_id=document_id,
            texts=texts,
            vectors=vectors,
            extra_payload=extra_payload,
        )
        logger.info("سند %s ایندکس شد: %s چانک", document_id, count)
        return IndexResult(document_id=document_id, chunk_count=count)

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            raise ValueError("کوئری خالی است")
        query_vector = self.embedder.embed_query(query.strip())
        return self.vector_db.search(
            query_vector=query_vector,
            top_k=top_k,
            document_ids=document_ids,
        )

    def build_context(self, results: list[SearchResult]) -> str:
        if not results:
            return ""
        parts: list[str] = []
        for i, item in enumerate(results, start=1):
            parts.append(
                f"[{i}] document_id={item.document_id} | chunk={item.chunk_index} | score={item.score:.4f}\n"
                f"{item.text}"
            )
        return "\n\n".join(parts)

    def _docs_are_insufficient(self, results: list[SearchResult]) -> bool:
        if not results:
            return True
        settings = get_settings()
        best = max(r.score for r in results)
        return best < settings.web_min_doc_score

    def _fallback_web_context(
        self,
        query: str,
        start_url: str | None = None,
        max_pages: int | None = None,
    ) -> tuple[str, list[SearchResult]]:
        url = (start_url or get_settings().web_base_url or "").strip()
        if not url:
            logger.warning("آدرس سایت برای کرال خالی است")
            return "", []

        settings = get_settings()
        limit = max_pages or min(int(settings.web_max_pages or 10), 8)
        logger.info("fallback کرال سایت: %s", url)
        pages = self.crawler.crawl(start_url=url, query=query, max_pages=limit)
        if not pages:
            return "", []

        context = self.crawler.pages_to_context(pages, max_chars=2000)
        sources = [
            SearchResult(
                text=page.text[:800],
                document_id=f"web:{page.url}",
                chunk_index=0,
                score=0.0,
                payload={
                    "url": page.url,
                    "title": page.title,
                    "source": "web",
                },
            )
            for page in pages[:8]
        ]
        return context, sources

    def ask(
        self,
        query: str,
        top_k: int = 8,
        document_ids: list[str] | None = None,
        allow_web_fallback: bool = True,
    ) -> RAGAnswer:
        results = self.retrieve(query=query, top_k=top_k, document_ids=document_ids)
        context = self.build_context(results)
        source_type = "documents"

        if allow_web_fallback and self._docs_are_insufficient(results):
            logger.info("اسناد کافی نبود؛ fallback وب فعال شد")
            web_context, web_sources = self._fallback_web_context(query)
            if web_context.strip():
                context = web_context
                results = web_sources
                source_type = "web"

        if not context.strip():
            return RAGAnswer(
                answer="در منابع موجود پیدا نشد.",
                sources=[],
                context="",
                source_type="none",
            )

        answer = self.llm.generate(query=query, context=context)
        return RAGAnswer(
            answer=answer,
            sources=results,
            context=context,
            source_type=source_type,
        )


_instance: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    global _instance
    if _instance is None:
        _instance = RAGPipeline()
    return _instance


def reset_rag_pipeline() -> None:
    global _instance
    _instance = None
