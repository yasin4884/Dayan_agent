from __future__ import annotations

import re
from typing import Any

from ai_model.model import get_llm_service
from backend.services.cms import get_cms
from backend.services.faq import faq_suggestions, match_faq
from backend.services.page_context import describe_page
from core.config import get_settings
from databases.mongo.memory import get_memory

_SIMPLE_RE = re.compile(
    r"^(سلام|درود|صبح بخیر|عصر بخیر|شب بخیر|خداحافظ|مرسی|ممنون|thanks|hi|hello|hey)[\s!.،؟?]*$",
    re.IGNORECASE,
)
# فقط کمک کوتاه/صرفاً ناوبری — نه سؤال محتوایی مثل «ثبت‌نام دانشگاه کدوم بخش»
_PURE_HELP_RE = re.compile(
    r"^(کمک|راهنما|help|منو|بخش.?ها|کجا برم|کدوم بخش|کدام بخش)[\s!.،؟?]*$",
    re.IGNORECASE,
)
_HELP_HINT_RE = re.compile(
    r"(کمک|راهنما|کجا برم|کدوم بخش|کدام بخش|where|help)",
    re.IGNORECASE,
)
_SUBSTANTIVE_RE = re.compile(
    r"(ثبت.?نام|انتخاب.?واحد|کارآموزی|آیین.?نامه|بخشنامه|نمره|کارنامه|دانشگاه|ترم|"
    r"شهریه|اساتید|استاد|فرم|تیکت|پشتیبانی|مرخصی|انتقال|مهمان|فارغ.?التحصیل|"
    r"وام|خوابگاه|کلاس|برنامه|دروس|واحد|گروه)",
    re.IGNORECASE,
)
_FORM_RE = re.compile(r"(فرم|form|دانلود فرم|فایل فرم)", re.IGNORECASE)
_TICKET_RE = re.compile(r"(تیکت|پشتیبانی|شکایت|ticket)", re.IGNORECASE)
_ABOUT_UNI_RE = re.compile(
    r"(درباره|در مورد|راجع به|معرفی|چی میدونی|چه میدونی).{0,24}(دانشگاه|یونیورسیتی|university)"
    r"|(دانشگاه).{0,16}(چیه|چیست|کجاست|کدام|کدوم|محمودآباد)",
    re.IGNORECASE,
)
_RAG_HINT_RE = re.compile(
    r"(آیین.?نامه|بخشنامه|قانون|ماده|دستورالعمل|سند دانش|مقررات|syllabus|"
    r"ثبت.?نام|انتخاب.?واحد|کارآموزی|مرخصی|نمره|کارنامه|دانشگاه)",
    re.IGNORECASE,
)


class ChatService:
    """چت: مسیرهای قطعی (FAQ/فرم/راهنما) اول؛ مدل فقط وقتی لازم و بدون گیر کردن RAG."""

    def __init__(self):
        self.memory = get_memory()
        self.cms = get_cms()
        self.llm = get_llm_service()
        self._rag = None
        self._model_ok: bool | None = None

    @property
    def rag(self):
        if self._rag is None:
            from core.rag import get_rag_pipeline

            self._rag = get_rag_pipeline()
        return self._rag

    def _model_available(self) -> bool:
        try:
            ok = bool(self.llm.is_available())
        except Exception:
            ok = False
        self._model_ok = ok
        return ok

    def _file_abs(self, file_url: str | None) -> str:
        url = (file_url or "").strip()
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        # فرانت از NEXT_PUBLIC_API_URL می‌خواند؛ لینک نسبی /files هم در UI به API وصل می‌شود
        if url.startswith("/"):
            return url
        return f"/{url.lstrip('/')}"

    def _match_forms(self, message: str, group_id: str | None = None) -> list[dict[str, Any]]:
        forms = [
            f
            for f in (self.cms.public_view(group_id).get("forms") or [])
            if f.get("enabled", True) is not False
        ]
        if not forms:
            return []
        msg = (message or "").strip().lower()
        tokens = {t for t in re.split(r"\s+", msg) if len(t) > 3}
        scored: list[tuple[float, dict[str, Any]]] = []
        for f in forms:
            blob = " ".join(
                str(f.get(k) or "") for k in ("title", "slug", "description", "filename", "group")
            ).lower()
            score = 0.0
            title = str(f.get("title") or "").lower()
            if title and title in msg:
                score += 1.2
            elif any(tok in blob for tok in tokens):
                score += 0.55
            if _FORM_RE.search(message):
                score += 0.25
            if score >= 0.8:
                scored.append((score, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            return [f for _, f in scored[:5]]
        if _FORM_RE.search(message):
            return forms[:5]
        return []

    def _forms_answer(self, forms: list[dict[str, Any]]) -> str:
        if not forms:
            return (
                "الان فرمی در سامانه ثبت نشده است.\n"
                "از منوی پایین برو به بخش «فرم‌ها» (/forms). اگر چیزی نبود، از تیکت بپرس."
            )
        lines = ["این فرم‌ها را پیدا کردم:"]
        for f in forms:
            title = f.get("title") or "فرم"
            desc = (f.get("description") or "").strip()
            file_url = self._file_abs(f.get("file_url"))
            lines.append(f"• {title}" + (f" — {desc}" if desc else ""))
            if file_url:
                lines.append(f"  دانلود: {file_url}")
            else:
                lines.append("  فایل هنوز آپلود نشده؛ برو بخش فرم‌ها.")
        lines.append("")
        lines.append("همچنین می‌توانی از منوی پایین وارد «فرم‌ها» شوی: /forms")
        return "\n".join(lines)

    def _guide_answer(self, site: dict[str, Any], page_title: str | None = None) -> str:
        lines = [
            f"الان در «{page_title or 'سامانه'}» هستی. برای کارهایت این بخش‌ها را برو:",
        ]
        nav = site.get("nav") or []
        for n in nav[:8]:
            label = n.get("label") or n.get("title")
            href = n.get("href") or ""
            if label and href:
                lines.append(f"• {label} → {href}")
        actions = site.get("quick_actions") or site.get("modules") or []
        if actions:
            lines.append("")
            lines.append("دسترسی سریع:")
            for a in actions[:5]:
                title = a.get("title") or ""
                href = a.get("href") or ""
                if title:
                    lines.append(f"• {title}" + (f" → {href}" if href else ""))
        lines.append("")
        lines.append("اگر فرم می‌خواهی بگو نام فرم را؛ فایل را می‌دهم و مسیر /forms را هم می‌گویم.")
        lines.append("برای پشتیبانی انسانی برو /tickets")
        return "\n".join(lines)

    def _is_nav_help(self, query: str) -> bool:
        """فقط وقتی کاربر واقعاً منو/راهنمای بخش می‌خواهد — نه سؤال محتوایی."""
        q = (query or "").strip()
        if not q:
            return False
        if _PURE_HELP_RE.match(q):
            return True
        # کوتاه + اشاره به کمک، بدون موضوع محتوایی
        if len(q) <= 28 and _HELP_HINT_RE.search(q) and not _SUBSTANTIVE_RE.search(q):
            return True
        return False

    def _ticket_answer(self) -> str:
        return (
            "برای پشتیبانی انسانی از منوی پایین برو به «تیکت» (/tickets)، "
            "موضوع را بنویس و پیام بفرست. ادمین آنلاین جواب می‌دهد."
        )

    def _brand_context(self, site: dict[str, Any]) -> str:
        brand = site.get("brand") or {}
        name = (brand.get("name") or "").strip() or "دانشگاه"
        tagline = (brand.get("tagline") or "").strip()
        website = (brand.get("website_url") or "").strip()
        website_label = (brand.get("website_label") or "سایت دانشگاه").strip()
        lines = [
            f"نام دانشگاه/سامانه: {name}",
            "این پورتال دانشجویی «دایان» برای همین دانشگاه است.",
        ]
        if tagline:
            lines.append(f"شعار: {tagline}")
        if website:
            lines.append(f"{website_label}: {website}")
        nav = site.get("nav") or []
        if nav:
            parts = []
            for n in nav[:8]:
                label = n.get("label") or n.get("title")
                href = n.get("href") or ""
                if label:
                    parts.append(f"{label} ({href})" if href else str(label))
            if parts:
                lines.append("بخش‌های سامانه: " + "، ".join(parts))
        forms = [f for f in (site.get("forms") or []) if f.get("enabled", True) is not False]
        if forms:
            titles = "، ".join(str(f.get("title") or "فرم") for f in forms[:6])
            lines.append(f"فرم‌های موجود: {titles}")
        return "\n".join(lines)

    def _about_university_answer(self, site: dict[str, Any]) -> str:
        brand = site.get("brand") or {}
        name = (brand.get("name") or "").strip() or "دانشگاه"
        tagline = (brand.get("tagline") or "").strip()
        website = (brand.get("website_url") or "").strip()
        website_label = (brand.get("website_label") or "سایت دانشگاه").strip()
        lines = [
            f"این سامانه متعلق به «{name}» است.",
            "من دایان هستم؛ دستیار دانشجویی همین پورتال.",
        ]
        if tagline:
            lines.append(tagline)
        if website:
            lines.append(f"برای اطلاعات عمومی دانشگاه برو به {website_label}: {website}")
        else:
            lines.append(
                "آدرس سایت رسمی هنوز در تنظیمات ادمین ثبت نشده؛ "
                "جزئیات بیشتر را از اطلاعیه‌ها یا تیکت بپرس."
            )
        lines.append("")
        lines.append("اینجا می‌توانی:")
        lines.append("• فرم‌ها را بگیری → /forms")
        lines.append("• اطلاعیه‌ها را ببینی → /notifications")
        lines.append("• مهلت‌ها را در تقویم چک کنی → /calendar")
        lines.append("• از پشتیبانی بپرسی → /tickets")
        lines.append("• پروفایل و رمز را مدیریت کنی → /profile")
        return "\n".join(lines)

    def _timeout_fallback(
        self,
        query: str,
        faqs: list[dict[str, Any]],
        site: dict[str, Any],
        group_id: str | None,
        page_title: str | None,
    ) -> str:
        forms = self._match_forms(query, group_id)
        if forms or _FORM_RE.search(query):
            return self._forms_answer(forms)
        if self._is_nav_help(query):
            return self._guide_answer(site, page_title)
        if _TICKET_RE.search(query):
            return self._ticket_answer()
        hit = match_faq(query, faqs, min_score=0.25)
        if hit:
            return str(hit.get("answer") or "")
        tips = faq_suggestions(faqs, limit=3)
        lines = [
            "مدل الان دیر جواب داد؛ فعلاً از مسیرهای سامانه استفاده کن:",
            "• فرم‌ها → /forms",
            "• تیکت پشتیبانی → /tickets",
            "• تقویم → /calendar",
            "• اطلاع‌رسانی → /notifications",
        ]
        if tips:
            lines.append("سوالات متداول:")
            lines.extend(f"• {t}" for t in tips)
        return "\n".join(lines)

    def _forms_context(self, message: str, group_id: str | None = None) -> str:
        forms = self._match_forms(message, group_id)
        if not forms and not _FORM_RE.search(message or ""):
            return ""
        use = forms or (self.cms.public_view(group_id).get("forms") or [])[:6]
        lines = ["فهرست فرم‌های سامانه (برای لینک دانلود از همین‌ها استفاده کن):"]
        for f in use:
            file_url = self._file_abs(f.get("file_url"))
            lines.append(
                f"- {f.get('title')} | slug={f.get('slug')} | file={file_url or '—'}\n"
                f"  {(f.get('description') or '')[:160]}"
            )
        lines.append("به کاربر بگو علاوه بر دانلود مستقیم، از بخش /forms هم می‌تواند بگیرد.")
        return "\n".join(lines)

    def _needs_rag(self, message: str, attachments: list[dict[str, Any]] | None) -> bool:
        settings = get_settings()
        if not getattr(settings, "rag_enabled", True):
            return False
        if attachments:
            return False
        msg = (message or "").strip()
        if len(msg) < 8:
            return False
        if _SIMPLE_RE.match(msg) or self._is_nav_help(msg) or _FORM_RE.search(msg):
            return False
        # سؤال محتوایی / آیین‌نامه / ثبت‌نام → RAG
        return bool(_RAG_HINT_RE.search(msg))

    def _retrieve_context(self, message: str, top_k: int) -> tuple[str, str, list[dict[str, Any]]]:
        settings = get_settings()
        try:
            top_k = min(top_k, int(getattr(settings, "rag_top_k", 4) or 4))
            results = self.rag.retrieve(query=message, top_k=top_k)
            context = self.rag.build_context(results)
            source_type = "documents" if results else "none"
            sources = [
                {
                    "document_id": s.document_id,
                    "score": s.score,
                    "payload": s.payload,
                }
                for s in results
            ]
            return context[:2500], source_type, sources
        except Exception:
            return "", "none", []

    def _offline_answer(self, faqs: list[dict[str, Any]], query: str, site: dict[str, Any]) -> str:
        hit = match_faq(query, faqs, min_score=0.28)
        if hit:
            return str(hit.get("answer") or "")
        forms = self._match_forms(query)
        if forms or _FORM_RE.search(query):
            return self._forms_answer(forms)
        if self._is_nav_help(query):
            return self._guide_answer(site)
        if _TICKET_RE.search(query):
            return self._ticket_answer()
        tips = faq_suggestions(faqs, limit=4)
        lines = [
            "الان مدل زبانی در دسترس نیست. می‌توانی از این‌ها استفاده کنی:",
            "• فرم‌ها → /forms",
            "• تیکت → /tickets",
            "• تقویم → /calendar",
        ]
        if tips:
            lines.append("سوالات متداول:")
            lines.extend(f"• {t}" for t in tips)
        return "\n".join(lines)

    def _finish(
        self,
        *,
        session_id: str,
        query: str,
        answer: str,
        source_type: str,
        user: dict[str, Any] | None,
        page_path: str | None,
        attachments: list[dict[str, Any]] | None,
        sources: list[dict[str, Any]],
        model_ok: bool | None,
        faqs_count: int,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.memory.append_turn(
            session_id,
            "user",
            query,
            meta={
                "user": user,
                "page_path": page_path,
                "attachments": [a.get("filename") for a in (attachments or [])],
            },
        )
        self.memory.append_turn(
            session_id,
            "assistant",
            answer,
            meta={"source_type": source_type},
        )
        out: dict[str, Any] = {
            "answer": answer,
            "source_type": source_type,
            "sources": sources,
            "session_id": session_id,
            "model_available": True if model_ok is None else bool(model_ok),
            "page_path": page_path,
            "faqs_available": faqs_count,
        }
        if extras:
            out.update(extras)
        return out

    def ask(
        self,
        message: str,
        session_id: str,
        user: dict[str, Any] | None = None,
        top_k: int = 4,
        page_path: str | None = None,
        page_title: str | None = None,
        page_text: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        group_id = (user or {}).get("group_id")
        site_full = self.cms.load()
        faqs = [f for f in (site_full.get("faqs") or []) if f.get("enabled", True)]
        site = self.cms.public_view(group_id)
        query = message.strip() or "لطفاً این صفحه / فایل پیوست را توضیح بده."
        sources: list[dict[str, Any]] = []

        # ---- مسیرهای قطعی (بدون مدل) ----
        if not attachments:
            faq_hit = match_faq(query, faqs)
            if faq_hit:
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=str(faq_hit.get("answer") or ""),
                    source_type="faq",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                )

            if _SIMPLE_RE.match(query):
                title = page_title or "همین صفحه"
                answer = (
                    f"سلام! من دایان هستم. الان در «{title}» هستید.\n"
                    "اگر فرم می‌خواهی نامش را بگو؛ برای راهنمای بخش‌ها بنویس «کمک»."
                )
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=answer,
                    source_type="greeting",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                )

            if _ABOUT_UNI_RE.search(query):
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=self._about_university_answer(site),
                    source_type="about",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                )

            forms = self._match_forms(query, group_id)
            # فقط با کلمهٔ «فرم» یا match قوی عنوان — نه هر سؤال عادی
            if _FORM_RE.search(query) or forms:
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=self._forms_answer(forms),
                    source_type="forms",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                    extras={
                        "forms": [
                            {
                                "title": f.get("title"),
                                "file_url": self._file_abs(f.get("file_url")),
                                "slug": f.get("slug"),
                            }
                            for f in forms
                        ]
                    },
                )

            if _TICKET_RE.search(query) and not self._is_nav_help(query):
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=self._ticket_answer(),
                    source_type="guide",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                )

            if self._is_nav_help(query):
                return self._finish(
                    session_id=session_id,
                    query=query,
                    answer=self._guide_answer(site, page_title),
                    source_type="guide",
                    user=user,
                    page_path=page_path,
                    attachments=attachments,
                    sources=sources,
                    model_ok=None,
                    faqs_count=len(faqs),
                )

        model_ok = self._model_available()
        if not model_ok and not attachments:
            return self._finish(
                session_id=session_id,
                query=query,
                answer=self._offline_answer(faqs, query, site),
                source_type="offline",
                user=user,
                page_path=page_path,
                attachments=attachments,
                sources=sources,
                model_ok=False,
                faqs_count=len(faqs),
            )

        page_text_cap = int(getattr(settings, "page_text_max_chars", 900) or 900)
        page_ctx = describe_page(
            path=page_path,
            title=page_title,
            page_text=(page_text or "")[:page_text_cap],
            cms_site=site,
        )
        memory_ctx = self.memory.build_memory_context(session_id)
        # کانتکست گفتگو را نگه دار تا با عوض شدن صفحه فراموش نشود
        if memory_ctx and len(memory_ctx) > 2400:
            memory_ctx = memory_ctx[-2400:]
        rules = self.cms.get_ai_rules_text()
        if rules and len(rules) > 300:
            rules = rules[:300]
        forms_ctx = self._forms_context(message, group_id=group_id)

        rag_context = ""
        source_type = "none"
        if model_ok and self._needs_rag(message, attachments):
            rag_context, source_type, sources = self._retrieve_context(message, top_k)

        attachment_parts: list[str] = []
        images: list[dict[str, str]] = []
        for att in attachments or []:
            text = att.get("text") or ""
            if text:
                attachment_parts.append(
                    f"پیوست ({att.get('kind')}: {att.get('filename')}):\n{text[:4000]}"
                )
            if att.get("image"):
                images.append(att["image"])
                source_type = "media" if source_type == "none" else source_type

        media_ctx = "\n\n".join(attachment_parts)
        nav_hint = self._guide_answer(site, page_title)
        brand_ctx = self._brand_context(site)
        context_parts = [
            p
            for p in [
                brand_ctx,
                page_ctx,
                rules,
                memory_ctx,
                forms_ctx,
                media_ctx,
                rag_context,
                "راهنمای بخش‌ها (اگر لازم بود به کاربر بگو کجا برود):\n" + nav_hint,
            ]
            if p
        ]
        context = "\n\n".join(context_parts).strip()

        prompt_vars = {
            "user_group": str(group_id or "عمومی"),
            "current_page": str(page_path or "/"),
        }
        raw = self.llm.generate(
            query=query,
            context=context,
            images=images or None,
            prompt_vars=prompt_vars,
        )
        if raw == "MODEL_OFFLINE":
            answer = self._offline_answer(faqs, query, site)
            source_type = "offline"
            model_ok = False
        elif raw == "MODEL_TIMEOUT":
            answer = self._timeout_fallback(query, faqs, site, group_id, page_title)
            source_type = "timeout_fallback"
        else:
            answer = raw or self._timeout_fallback(query, faqs, site, group_id, page_title)

        return self._finish(
            session_id=session_id,
            query=query,
            answer=answer,
            source_type=source_type,
            user=user,
            page_path=page_path,
            attachments=attachments,
            sources=sources,
            model_ok=model_ok,
            faqs_count=len(faqs),
        )

    def analyze_document(
        self,
        session_id: str,
        document_text: str,
        kind: str = "سند",
        user: dict[str, Any] | None = None,
        page_path: str | None = None,
    ) -> dict[str, Any]:
        return self.ask(
            message=f"این {kind} را تحلیل کن. نقاط قوت، ضعف، ریسک و پیشنهاد عملی بگو.",
            session_id=session_id,
            user=user,
            page_path=page_path,
            attachments=[
                {
                    "filename": kind,
                    "kind": "document",
                    "text": document_text[:12000],
                }
            ],
        )


_chat_singleton: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_singleton
    if _chat_singleton is None:
        _chat_singleton = ChatService()
    return _chat_singleton
