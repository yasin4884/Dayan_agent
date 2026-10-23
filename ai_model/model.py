from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)

MessageContent = str | list[dict[str, Any]]

_FALLBACK_PROMPT = (
    "تو دستیار هوشمند سامانه دانشگاهی هستی. فارسی، کوتاه و دقیق جواب بده. "
    "اگر کاربر گفت «اینجا»، منظورش موقعیت صفحه داخل متن مرجع است. "
    "پاسخ نهایی را مستقیم بنویس؛ توضیح طولانی لازم نیست."
)

# کش وضعیت مدل تا هر درخواست چند ثانیه روی /v1/models نماند
_avail_cache: dict[str, Any] = {"at": 0.0, "ok": False}


class BaseLLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        query: str,
        context: str,
        images: list[dict[str, str]] | None = None,
    ) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseLLMProvider):
    """LM Studio / OpenAI-compatible — بهینه برای CPU و مدل‌های thinking."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.model_url.rstrip("/")
        self.chat_url = settings.chat_completions_url
        self._configured_model = settings.model_name
        self._model_name: str | None = None
        self.temperature = settings.temperature
        self.max_tokens = min(int(settings.max_tokens), 768)
        self.system_prompt = self._load_system_prompt(settings)

    @property
    def model_name(self) -> str:
        if self._model_name is None:
            self._model_name = self._resolve_model_name(self._configured_model)
        return self._model_name

    def _list_model_ids(self) -> list[str]:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=0.6)
            response.raise_for_status()
            data = response.json().get("data") or []
            return [str(m.get("id")) for m in data if m.get("id")]
        except Exception as exc:
            logger.warning("خواندن لیست مدل‌ها ناموفق: %s", exc)
            return []

    def is_available(self) -> bool:
        now = time.time()
        cached_ok = bool(_avail_cache["ok"])
        age = now - float(_avail_cache["at"])
        # موفقیت را طولانی‌تر نگه دار؛ شکست کوتاه — تا تایم‌اوت کوتاه مدل را «قطع» نکند
        if age < (45 if cached_ok else 8):
            return cached_ok
        ok = False
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=1.5)
            ok = response.status_code == 200
        except Exception as exc:
            logger.error("خطا در بررسی LLM: %s", exc)
            ok = False
        _avail_cache["at"] = now
        _avail_cache["ok"] = ok
        return ok

    def _load_system_prompt(self, settings: Settings) -> str:
        path = settings.system_prompt_file
        if not path.exists() or path.stat().st_size == 0:
            return _FALLBACK_PROMPT
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            prompt = data.get("system_prompt")
            if not prompt or not isinstance(prompt, str):
                raise ValueError("system_prompt نامعتبر")
            text = prompt.strip()
            limit = int(getattr(settings, "system_prompt_max_chars", 2500) or 2500)
            if len(text) > limit:
                text = text[:limit] + "\n..."
            return text
        except Exception as exc:
            logger.warning("خواندن system prompt ناموفق (%s)؛ fallback", exc)
            return _FALLBACK_PROMPT

    def _resolve_model_name(self, configured: str) -> str:
        ids = self._list_model_ids()
        if not ids:
            return configured
        if configured in ids:
            return configured
        chat_ids = [i for i in ids if "embed" not in i.lower()]
        chosen = (chat_ids or ids)[0]
        logger.info("MODEL_NAME=%s نبود؛ استفاده از %s", configured, chosen)
        return chosen

    def _build_user_content(
        self,
        query: str,
        context: str,
        images: list[dict[str, str]] | None,
    ) -> MessageContent:
        ctx = (context or "").strip()
        limit = int(getattr(self.settings, "llm_context_max_chars", 3500) or 3500)
        if len(ctx) > limit:
            ctx = ctx[:limit] + "\n…(کوتاه‌شده)"
        text = (
            "متن مرجع (خلاصه):\n"
            f"{ctx or '(خالی)'}\n\n"
            f"سوال کاربر: {query}\n\n"
            "فقط پاسخ نهایی کوتاه فارسی بده."
        )
        if not images:
            return text
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for img in images:
            mime = img.get("mime") or "image/jpeg"
            b64 = img.get("base64") or ""
            if not b64:
                continue
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
        return parts

    def _render_system_prompt(self, prompt_vars: dict[str, str] | None = None) -> str:
        text = self.system_prompt
        vars_ = {
            "user_group": "عمومی",
            "current_page": "/",
            **(prompt_vars or {}),
        }
        for key, value in vars_.items():
            text = text.replace("{" + key + "}", str(value or ""))
        return text

    def _build_payload(
        self,
        query: str,
        context: str,
        images: list[dict[str, str]] | None,
        max_tokens: int,
        prompt_vars: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self._render_system_prompt(prompt_vars)},
                {
                    "role": "user",
                    "content": self._build_user_content(query, context, images),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        # غیرفعال‌کردن thinking در مدل‌های سازگار (Qwen3 / LM Studio)
        if getattr(self.settings, "llm_disable_thinking", True):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["enable_thinking"] = False
        return payload

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str:
        choice = (result.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = (msg.get("content") or "").strip()
        if content:
            return content
        # بعضی مدل‌ها فقط reasoning پر می‌کنند
        reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
        if not reasoning:
            return ""
        # تلاش برای بیرون کشیدن پاسخ فارسی از انتهای reasoning
        lines = [ln.strip() for ln in reasoning.splitlines() if ln.strip()]
        persian = [
            ln
            for ln in lines
            if re.search(r"[\u0600-\u06FF]", ln)
            and not ln.lower().startswith("option")
            and "analyze" not in ln.lower()
        ]
        if persian:
            return persian[-1][:500]
        return ""

    def generate(
        self,
        query: str,
        context: str,
        images: list[dict[str, str]] | None = None,
        prompt_vars: dict[str, str] | None = None,
    ) -> str:
        max_tokens = min(max(int(self.max_tokens), 128), 512)
        timeout = float(getattr(self.settings, "llm_timeout_seconds", 90) or 90)
        try:
            payload = self._build_payload(query, context, images, max_tokens, prompt_vars)
            response = requests.post(self.chat_url, json=payload, timeout=timeout)
            if response.status_code >= 400 and images:
                logger.warning("vision رد شد؛ فقط متن")
                payload = self._build_payload(query, context, None, max_tokens, prompt_vars)
                response = requests.post(self.chat_url, json=payload, timeout=timeout)

            # اگر پارامتر thinking ناشناخته بود، بدون آن دوباره بفرست
            if response.status_code >= 400 and "thinking" in (response.text or "").lower():
                payload.pop("chat_template_kwargs", None)
                payload.pop("enable_thinking", None)
                response = requests.post(self.chat_url, json=payload, timeout=timeout)

            response.raise_for_status()
            result = response.json()
            output = self._extract_text(result)

            # اگر thinking همه توکن‌ها را بلعید → یک‌بار با توکن بیشتر و context کوتاه‌تر
            if not output:
                choice = (result.get("choices") or [{}])[0]
                finish = choice.get("finish_reason")
                usage = result.get("usage") or {}
                details = usage.get("completion_tokens_details") or {}
                reasoning_tokens = int(details.get("reasoning_tokens") or 0)
                if finish == "length" or reasoning_tokens > 0:
                    logger.warning(
                        "content خالی (finish=%s reasoning_tokens=%s)؛ retry با توکن بیشتر",
                        finish,
                        reasoning_tokens,
                    )
                    short_ctx = (context or "")[:1000]
                    retry_tokens = min(max_tokens * 2, 768)
                    payload = self._build_payload(query, short_ctx, None, retry_tokens, prompt_vars)
                    payload["chat_template_kwargs"] = {"enable_thinking": False}
                    payload["enable_thinking"] = False
                    response = requests.post(self.chat_url, json=payload, timeout=timeout)
                    if response.status_code < 400:
                        output = self._extract_text(response.json())

            if output:
                _avail_cache["at"] = time.time()
                _avail_cache["ok"] = True
                return output
            q = query.strip()
            if q in {"سلام", "درود", "هی", "hello", "hi"} or q.startswith("سلام"):
                return "سلام! چطور می‌تونم کمکت کنم؟"
            return "MODEL_TIMEOUT"
        except requests.exceptions.ConnectionError:
            _avail_cache["at"] = time.time()
            _avail_cache["ok"] = False
            return "MODEL_OFFLINE"
        except requests.exceptions.Timeout:
            logger.warning("تایم‌اوت مدل بعد از %.0fs", timeout)
            return "MODEL_TIMEOUT"
        except requests.exceptions.HTTPError as exc:
            body = ""
            try:
                body = (exc.response.text or "")[:300]
            except Exception:
                pass
            logger.error(
                "HTTP مدل: %s %s",
                getattr(exc.response, "status_code", "?"),
                body,
            )
            return "متاسفم، خطایی در پردازش مدل رخ داد."
        except Exception as exc:
            logger.error("خطای generate: %s", exc)
            return "متاسفم، خطایی رخ داد."


def build_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider in {"lm_studio", "openai", "ollama"}:
        return OpenAICompatibleProvider(settings)
    raise ValueError(f"LLM provider پشتیبانی نمی‌شود: {settings.llm_provider}")


_llm_singleton: LLMService | None = None


class LLMService:
    def __init__(self, provider: BaseLLMProvider | None = None):
        self._provider = provider or build_llm_provider()

    def is_available(self) -> bool:
        return self._provider.is_available()

    def generate(
        self,
        query: str,
        context: str,
        images: list[dict[str, str]] | None = None,
        prompt_vars: dict[str, str] | None = None,
    ) -> str:
        return self._provider.generate(
            query=query,
            context=context,
            images=images,
            prompt_vars=prompt_vars,
        )

    def get_welcome_message(self) -> str:
        return "سلام. من دستیار هوشمند دانشگاه هستم. چه سوالی دارید؟"


def get_llm_service() -> LLMService:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMService()
    return _llm_singleton


model_config = LLMService
