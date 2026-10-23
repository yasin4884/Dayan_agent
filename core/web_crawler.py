from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".mp4", ".mp3", ".css", ".js", ".ico", ".woff", ".woff2",
)


@dataclass(frozen=True, slots=True)
class CrawledPage:
    url: str
    title: str
    text: str


def _normalize_url(url: str) -> str:
    clean, _ = urldefrag(url.strip())
    return clean.rstrip("/") or clean


def _same_domain(base: str, candidate: str) -> bool:
    b = urlparse(base)
    c = urlparse(candidate)
    return c.netloc.lower() == b.netloc.lower() and c.scheme in {"http", "https"}


def _should_skip(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _SKIP_EXTENSIONS)


def _extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return title, text.strip()


def _extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = _normalize_url(urljoin(base_url, href))
        if _same_domain(base_url, absolute) and not _should_skip(absolute):
            links.append(absolute)
    return links


def query_relevance(text: str, query: str) -> float:
    """امتیاز ساده کلمه کلیدی برای اولویت‌بندی صفحات کرال‌شده."""
    if not text or not query:
        return 0.0
    hay = text.lower()
    tokens = [t for t in re.split(r"\s+", query.lower()) if len(t) > 1]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in hay)
    return hits / len(tokens)


class WebCrawler:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def crawl(
        self,
        start_url: str | None = None,
        max_pages: int | None = None,
        query: str | None = None,
    ) -> list[CrawledPage]:
        base = (start_url or self.settings.web_base_url or "").strip()
        if not base:
            logger.warning("WEB_BASE_URL خالی است؛ کرال انجام نشد")
            return []

        limit = max_pages or self.settings.web_max_pages
        timeout = self.settings.web_timeout_seconds
        headers = {"User-Agent": self.settings.web_user_agent}

        start = _normalize_url(base)
        queue: deque[str] = deque([start])
        seen: set[str] = set()
        pages: list[CrawledPage] = []

        session = requests.Session()
        session.headers.update(headers)

        while queue and len(pages) < limit:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            try:
                response = session.get(url, timeout=timeout, allow_redirects=True)
                if response.status_code != 200:
                    logger.info("رد صفحه %s با کد %s", url, response.status_code)
                    continue
                content_type = response.headers.get("Content-Type", "")
                if "html" not in content_type.lower() and not url.endswith(("/", ".html", ".htm", ".php", ".aspx")):
                    continue

                title, text = _extract_text(response.text)
                if text and len(text) > 40:
                    pages.append(CrawledPage(url=url, title=title, text=text))

                for link in _extract_links(url, response.text):
                    if link not in seen:
                        queue.append(link)
            except requests.RequestException as exc:
                logger.warning("خطا در کرال %s: %s", url, exc)

        if query:
            pages.sort(key=lambda p: query_relevance(f"{p.title}\n{p.text}", query), reverse=True)

        logger.info("کرال تمام شد: %s صفحه از %s", len(pages), start)
        return pages

    def pages_to_context(self, pages: list[CrawledPage], max_chars: int = 12000) -> str:
        parts: list[str] = []
        total = 0
        for i, page in enumerate(pages, start=1):
            block = f"[{i}] منبع وب: {page.url}\nعنوان: {page.title}\n{page.text}"
            if total + len(block) > max_chars:
                remain = max_chars - total
                if remain > 200:
                    parts.append(block[:remain])
                break
            parts.append(block)
            total += len(block)
        return "\n\n".join(parts)


def get_web_crawler() -> WebCrawler:
    return WebCrawler()
