from __future__ import annotations

import logging
import os

from core.config import get_settings

logger = logging.getLogger(__name__)

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

try:
    import torch
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    logger.exception(
        "پکیج‌های embedding نصب نیست. اجرا کن: pip install torch sentence-transformers"
    )
    torch = None
    SentenceTransformer = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

_MAX_BATCH_SIZE = 64


class EmbeddingModel:
    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ):
        if _IMPORT_ERROR is not None:
            raise RuntimeError(
                "برای embedding باید torch و sentence-transformers نصب باشند. "
                "pip install torch sentence-transformers"
            ) from _IMPORT_ERROR

        settings = get_settings()
        resolved_name = model_name or settings.embedding_model_name
        resolved_device = device or settings.embedding_device
        if not resolved_device:
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"

        # بهینه CPU
        if resolved_device == "cpu":
            threads = int(getattr(settings, "embedding_cpu_threads", 4) or 4)
            try:
                torch.set_num_threads(threads)
            except Exception:
                pass

        logger.info("در حال لود مدل embedding: %s روی %s", resolved_name, resolved_device)

        try:
            self._model = SentenceTransformer(resolved_name, device=resolved_device)
        except Exception as exc:
            logger.exception("لود مدل embedding '%s' شکست خورد", resolved_name)
            raise RuntimeError(
                f"لود مدل embedding شکست خورد. اگر اولین اجراست، یک‌بار اینترنت لازم است "
                f"تا مدل از HuggingFace دانلود شود. خطای اصلی: {exc}"
            ) from exc

        self._model_name = resolved_name
        self._device = resolved_device
        self._dimension = int(
            getattr(self._model, "get_embedding_dimension", None)()
            if hasattr(self._model, "get_embedding_dimension")
            else self._model.get_sentence_embedding_dimension()
        )
        self._default_batch = int(getattr(settings, "embedding_batch_size", 8) or 8)
        if self._device == "cpu":
            self._default_batch = min(self._default_batch, 8)
        logger.info("مدل embedding لود شد. بعد وکتور: %s", self._dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    def embed_passages(
        self,
        texts: list[str],
        batch_size: int | None = None,
    ) -> list[list[float]]:
        bs = batch_size if batch_size is not None else self._default_batch
        return self._embed(texts, prefix="passage: ", batch_size=bs)

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text], prefix="query: ", batch_size=1)
        if not vectors:
            raise ValueError("متن کوئری برای embed خالی است")
        return vectors[0]

    def _embed(
        self,
        texts: list[str],
        prefix: str,
        batch_size: int,
    ) -> list[list[float]]:
        if not texts:
            return []

        safe_batch = max(1, min(batch_size, _MAX_BATCH_SIZE))
        safe_texts = [t if t and t.strip() else "(empty)" for t in texts]
        prefixed = [f"{prefix}{t}" for t in safe_texts]

        try:
            vectors = self._model.encode(
                prefixed,
                batch_size=safe_batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            logger.exception("خطا در embed کردن %s متن", len(texts))
            raise RuntimeError(f"خطا در embed کردن {len(texts)} متن: {exc}") from exc

        return vectors.tolist()


_instance: EmbeddingModel | None = None


def get_embedding_model() -> EmbeddingModel:
    global _instance
    if _instance is None:
        _instance = EmbeddingModel()
    return _instance


def reset_embedding_model() -> None:
    """برای تست یا تعویض مدل در runtime."""
    global _instance
    _instance = None
