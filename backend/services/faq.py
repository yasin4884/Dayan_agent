from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = re.sub(r"[^\w\u0600-\u06FF\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(text: str) -> set[str]:
    return {tok for tok in _norm(text).split() if len(tok) > 1}


def match_faq(message: str, faqs: list[dict[str, Any]], *, min_score: float = 0.34) -> dict[str, Any] | None:
    """بهترین سوال متداول را با شباهت ساده توکن پیدا می‌کند."""
    q_tokens = _tokens(message)
    if not q_tokens or not faqs:
        return None

    best: dict[str, Any] | None = None
    best_score = 0.0
    msg_norm = _norm(message)

    for item in faqs:
        if item.get("enabled") is False:
            continue
        question = str(item.get("question") or "")
        answer = str(item.get("answer") or "")
        if not question.strip() or not answer.strip():
            continue

        keys = str(item.get("keywords") or "")
        bag = _tokens(question) | _tokens(keys)
        if not bag:
            continue

        overlap = len(q_tokens & bag) / max(len(q_tokens), 1)
        # اگر سوال کامل داخل پیام بود امتیاز بالا
        if _norm(question) and _norm(question) in msg_norm:
            overlap = max(overlap, 0.95)
        # اشتراک از سمت سوال
        cover = len(q_tokens & bag) / max(len(bag), 1)
        score = max(overlap, cover * 0.85)

        if score > best_score:
            best_score = score
            best = item

    if best is None or best_score < min_score:
        return None
    return best


def faq_suggestions(faqs: list[dict[str, Any]], limit: int = 5) -> list[str]:
    out: list[str] = []
    for item in faqs:
        if item.get("enabled") is False:
            continue
        q = str(item.get("question") or "").strip()
        if q:
            out.append(q)
        if len(out) >= limit:
            break
    return out
