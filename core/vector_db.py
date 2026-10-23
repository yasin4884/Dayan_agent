from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from core.config import get_settings


@dataclass(frozen=True, slots=True)
class SearchResult:
    text: str
    document_id: str
    chunk_index: int
    score: float
    payload: dict


def _deterministic_point_id(document_id: str, chunk_index: int) -> str:
    """UUID پایدار از document_id+chunk_index (idempotent upsert)."""
    raw = f"{document_id}:{chunk_index}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest))


class VectorDB:
    def __init__(
        self,
        collection_name: str,
        vector_size: int,
        path: str | None = None,
        url: str | None = None,
    ):
        if url:
            self.client = QdrantClient(url=url)
        else:
            path_obj = Path(path or "./data/qdrant")
            path_obj.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path_obj))
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._ensure_collection(vector_size)

    def _ensure_collection(self, vector_size: int) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        document_id: str,
        texts: list[str],
        vectors: list[list[float]],
        extra_payload: dict | None = None,
    ) -> int:
        if len(texts) != len(vectors):
            raise ValueError(
                f"تعداد متن‌ها ({len(texts)}) با تعداد وکتورها ({len(vectors)}) یکی نیست"
            )
        if not document_id.strip():
            raise ValueError("document_id خالی است")

        points = [
            qmodels.PointStruct(
                id=_deterministic_point_id(document_id, i),
                vector=vector,
                payload={
                    "document_id": document_id,
                    "chunk_index": i,
                    "text": text,
                    **(extra_payload or {}),
                },
            )
            for i, (text, vector) in enumerate(zip(texts, vectors))
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 8,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k باید بزرگ‌تر از صفر باشد")

        query_filter = None
        if document_ids:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchAny(any=document_ids),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        hits = response.points
        results: list[SearchResult] = []
        for h in hits:
            payload = h.payload or {}
            results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    document_id=payload.get("document_id", ""),
                    chunk_index=int(payload.get("chunk_index", -1)),
                    score=float(h.score),
                    payload=payload,
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def count(self) -> int:
        return int(self.client.count(collection_name=self.collection_name).count)


_instance: VectorDB | None = None


def get_vector_db(vector_size: int | None = None) -> VectorDB:
    global _instance
    if _instance is None:
        settings = get_settings()
        size = vector_size if vector_size is not None else 384
        url = (settings.qdrant_url or "").strip() or None
        if url:
            try:
                import requests

                requests.get(f"{url.rstrip('/')}/readyz", timeout=1.5)
            except Exception:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("Qdrant سرور در دسترس نیست؛ از مسیر محلی استفاده می‌شود")
                url = None
        _instance = VectorDB(
            collection_name=settings.qdrant_collection,
            vector_size=size,
            url=url,
            path=None if url else str(settings.qdrant_abs_path),
        )
    return _instance


def reset_vector_db() -> None:
    global _instance
    _instance = None
