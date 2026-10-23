from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from core.config import Settings, get_settings
from core.web_crawler import CrawledPage, WebCrawler, get_web_crawler, query_relevance

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SearchHit:
    title: str
    url: str
    snippet: str


class BaseSearchEngine(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int) -> list[SearchHit]:
        raise NotImplementedError


class NoneSearchEngine(BaseSearchEngine):
    def search(self, query: str, max_results: int) -> list[SearchHit]:
        return []


class SiteCrawlSearchEngine(BaseSearchEngine):
    """کرال همان سایت WEB_BASE_URL (بدون موتور خارجی)."""

    def __init__(self, settings: Settings, crawler: WebCrawler | None = None):
        self.settings = settings
        self.crawler = crawler or get_web_crawler()

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        pages = self.crawler.crawl(query=query, max_pages=max_results)
        return [
            SearchHit(title=p.title or p.url, url=p.url, snippet=p.text[:300])
            for p in pages[:max_results]
        ]


class DuckDuckGoSearchEngine(BaseSearchEngine):
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        q = _with_site_filter(query, self.settings.search_site_filter)
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "برای SEARCH_ENGINE=duckduckgo نصب کن: pip install ddgs"
                ) from exc

        hits: list[SearchHit] = []
        with DDGS() as ddgs:
            results = ddgs.text(q, max_results=max_results) or []
            for item in results:
                hits.append(
                    SearchHit(
                        title=str(item.get("title") or ""),
                        url=str(item.get("href") or item.get("link") or ""),
                        snippet=str(item.get("body") or item.get("snippet") or ""),
                    )
                )
        return [h for h in hits if h.url]


class BingSearchEngine(BaseSearchEngine):
    ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.search_api_key:
            raise ValueError("برای bing باید SEARCH_API_KEY در .env ست شود")

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        q = _with_site_filter(query, self.settings.search_site_filter)
        headers = {"Ocp-Apim-Subscription-Key": self.settings.search_api_key}
        params = {"q": q, "count": max_results, "mkt": "fa-IR", "textDecorations": False}
        response = requests.get(
            self.ENDPOINT,
            headers=headers,
            params=params,
            timeout=self.settings.web_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        hits: list[SearchHit] = []
        for item in data.get("webPages", {}).get("value", []):
            hits.append(
                SearchHit(
                    title=str(item.get("name") or ""),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("snippet") or ""),
                )
            )
        return [h for h in hits if h.url]


class GoogleSearchEngine(BaseSearchEngine):
    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.search_api_key or not settings.search_cx:
            raise ValueError("برای google باید SEARCH_API_KEY و SEARCH_CX در .env ست شوند")

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        q = _with_site_filter(query, self.settings.search_site_filter)
        params = {
            "key": self.settings.search_api_key,
            "cx": self.settings.search_cx,
            "q": q,
            "num": min(max_results, 10),
            "hl": "fa",
        }
        response = requests.get(
            self.ENDPOINT,
            params=params,
            timeout=self.settings.web_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        hits: list[SearchHit] = []
        for item in data.get("items", []):
            hits.append(
                SearchHit(
                    title=str(item.get("title") or ""),
                    url=str(item.get("link") or ""),
                    snippet=str(item.get("snippet") or ""),
                )
            )
        return [h for h in hits if h.url]


def _with_site_filter(query: str, site_filter: str) -> str:
    site = (site_filter or "").strip()
    if not site:
        return query
    # اگر کاربر کامل URL داده، فقط host را بگیر
    if "://" in site:
        site = urlparse(site).netloc or site
    if f"site:{site}" in query.lower():
        return query
    return f"{query} site:{site}"


def build_search_engine(settings: Settings | None = None) -> BaseSearchEngine:
    settings = settings or get_settings()
    engine = settings.search_engine

    if engine == "none":
        return NoneSearchEngine()
    if engine == "site_crawl":
        return SiteCrawlSearchEngine(settings)
    if engine == "duckduckgo":
        return DuckDuckGoSearchEngine(settings)
    if engine == "bing":
        return BingSearchEngine(settings)
    if engine == "google":
        return GoogleSearchEngine(settings)
    raise ValueError(f"SEARCH_ENGINE پشتیبانی نمی‌شود: {engine}")


class WebSearchService:
    """سرچ با موتور انتخاب‌شده + اختیاری خواندن محتوای صفحات."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: BaseSearchEngine | None = None,
        crawler: WebCrawler | None = None,
    ):
        self.settings = settings or get_settings()
        self.engine = engine or build_search_engine(self.settings)
        self.crawler = crawler or get_web_crawler()

    def search_and_collect(self, query: str) -> tuple[str, list[dict[str, Any]]]:
        max_results = self.settings.search_max_results
        hits = self.engine.search(query=query, max_results=max_results)
        if not hits:
            return "", []

        sources: list[dict[str, Any]] = []
        context_parts: list[str] = []

        # site_crawl خودش متن صفحه دارد؛ برای بقیه در صورت نیاز fetch می‌کنیم
        if self.settings.search_engine == "site_crawl" or not self.settings.search_fetch_pages:
            for i, hit in enumerate(hits, start=1):
                block = (
                    f"[{i}] عنوان: {hit.title}\n"
                    f"آدرس: {hit.url}\n"
                    f"{hit.snippet}"
                )
                context_parts.append(block)
                sources.append(
                    {
                        "title": hit.title,
                        "url": hit.url,
                        "snippet": hit.snippet,
                        "text": hit.snippet,
                        "score": query_relevance(f"{hit.title}\n{hit.snippet}", query),
                    }
                )
        else:
            pages = self._fetch_hit_pages(hits)
            if pages:
                for i, page in enumerate(pages, start=1):
                    block = (
                        f"[{i}] منبع وب: {page.url}\n"
                        f"عنوان: {page.title}\n"
                        f"{page.text}"
                    )
                    context_parts.append(block)
                    sources.append(
                        {
                            "title": page.title,
                            "url": page.url,
                            "snippet": page.text[:300],
                            "text": page.text[:500],
                            "score": query_relevance(f"{page.title}\n{page.text}", query),
                        }
                    )
            else:
                # اگر fetch شکست خورد، حداقل snippet سرچ را بده
                for i, hit in enumerate(hits, start=1):
                    block = f"[{i}] عنوان: {hit.title}\nآدرس: {hit.url}\n{hit.snippet}"
                    context_parts.append(block)
                    sources.append(
                        {
                            "title": hit.title,
                            "url": hit.url,
                            "snippet": hit.snippet,
                            "text": hit.snippet,
                            "score": query_relevance(f"{hit.title}\n{hit.snippet}", query),
                        }
                    )

        context = "\n\n".join(context_parts)
        return context, sources

    def _fetch_hit_pages(self, hits: list[SearchHit]) -> list[CrawledPage]:
        pages: list[CrawledPage] = []
        timeout = self.settings.web_timeout_seconds
        headers = {"User-Agent": self.settings.web_user_agent}
        session = requests.Session()
        session.headers.update(headers)

        for hit in hits:
            try:
                response = session.get(hit.url, timeout=timeout, allow_redirects=True)
                if response.status_code != 200:
                    continue
                from core.web_crawler import _extract_text

                title, text = _extract_text(response.text)
                if text and len(text) > 40:
                    pages.append(
                        CrawledPage(
                            url=hit.url,
                            title=title or hit.title,
                            text=text,
                        )
                    )
            except requests.RequestException as exc:
                logger.warning("خواندن صفحه سرچ شکست خورد %s: %s", hit.url, exc)
        return pages


def get_web_search_service() -> WebSearchService:
    return WebSearchService()
