from __future__ import annotations

import logging
from dataclasses import dataclass

from chonkie import RecursiveChunker
from chonkie.tokenizer import WordTokenizer

from core.config import get_settings

logger = logging.getLogger(__name__)

_chunker_cache: dict[int, RecursiveChunker] = {}


def _get_chunker(chunk_size: int) -> RecursiveChunker:
    if chunk_size not in _chunker_cache:
        _chunker_cache[chunk_size] = RecursiveChunker(
            tokenizer=WordTokenizer(),
            chunk_size=chunk_size,
        )
    return _chunker_cache[chunk_size]


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    index: int
    word_count: int


def _add_manual_overlap(texts: list[str], overlap_words: int) -> list[str]:
    if overlap_words <= 0 or len(texts) < 2:
        return texts

    result = [texts[0]]
    for i in range(1, len(texts)):
        prev_words = texts[i - 1].split()
        if len(prev_words) > overlap_words:
            tail = " ".join(prev_words[-overlap_words:])
        else:
            tail = texts[i - 1]
        result.append(f"{tail} {texts[i]}".strip())
    return result


def _fallback_split(text: str, chunk_size_words: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    size = max(1, chunk_size_words)
    return [
        " ".join(words[i : i + size])
        for i in range(0, len(words), size)
    ]


def _normalize(text: str) -> str:
    if not text:
        return ""
    return text.replace("\x00", "").strip()


def split_into_chunks(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    settings = get_settings()
    resolved_size = chunk_size if chunk_size is not None else settings.chunk_size_words
    resolved_overlap = overlap if overlap is not None else settings.chunk_overlap_words

    if resolved_size <= 0:
        raise ValueError("chunk_size باید بزرگ‌تر از صفر باشد")
    if resolved_overlap < 0:
        raise ValueError("overlap نمی‌تواند منفی باشد")
    if resolved_overlap >= resolved_size:
        raise ValueError("overlap باید کوچک‌تر از chunk_size باشد")

    text = _normalize(text)
    if not text:
        return []

    try:
        chunker = _get_chunker(resolved_size)
        raw_texts = [c.text.strip() for c in chunker(text) if c.text.strip()]
    except Exception as exc:
        logger.warning("chonkie شکست خورد؛ fallback فعال شد: %s", exc)
        raw_texts = _fallback_split(text, resolved_size)

    if not raw_texts:
        return []

    final_texts = _add_manual_overlap(raw_texts, resolved_overlap)
    return [
        TextChunk(text=t, index=i, word_count=len(t.split()))
        for i, t in enumerate(final_texts)
    ]
