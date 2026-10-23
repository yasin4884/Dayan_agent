"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { AnimatePresence, animate, motion, useMotionValue } from "framer-motion";
import { Bot, History, Maximize2, Minimize2, Plus, Paperclip, Send, X } from "lucide-react";
import { chat, chatWithFiles, fetchSite } from "@/lib/api";

type Msg = { role: "user" | "bot"; text: string; files?: string[] };
type Side = "left" | "right";
type FaqItem = { id: string; question: string; answer?: string };
type ConvMeta = { id: string; title: string; updatedAt: number };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const WELCOME: Msg = {
  role: "bot",
  text: "سلام! من دایان هستم. می‌توانی عکس کارنامه، PDF یا فرم را با دکمه گیره‌کاغذ پیوست کنی؛ یا بکش و اینجا رها کن. سوالت را هم بنویس.",
};
const STORAGE_ACTIVE = "dayan_chat_active";
const STORAGE_LIST = "dayan_chat_list";
const msgKey = (id: string) => `dayan_chat_msgs_${id}`;

function renderBotText(text: string) {
  const parts = text.split(/(\/?files\/[^\s]+|https?:\/\/[^\s]+|\/[a-z][\w\-\/]*)/gi);
  return parts.map((part, i) => {
    if (!part) return null;
    const isFile = /^\/?files\//i.test(part);
    const isHttp = /^https?:\/\//i.test(part);
    const isRoute = /^\/[a-z][\w\-\/]*$/i.test(part) && part.length > 1;
    if (isFile || isHttp) {
      const href = isFile
        ? `${API_BASE}${part.startsWith("/") ? part : `/${part}`}`
        : part;
      return (
        <a key={i} href={href} target="_blank" rel="noreferrer" className="agent-inline-link">
          {isFile ? "دانلود فایل" : part}
        </a>
      );
    }
    if (isRoute) {
      return (
        <a key={i} href={part} className="agent-inline-link">
          {part}
        </a>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

const BUBBLE = 60;
const EDGE = 16;
const MAX_FILES = 5;
const ACCEPT = "image/*,.pdf,.doc,.docx,.xlsx,.xls,.txt,.md,.csv,.heic,.heif";

const PAGE_TITLES: Record<string, string> = {
  "/": "صفحه اصلی",
  "/login": "ورود و ثبت‌نام",
  "/notifications": "اطلاع‌رسانی‌ها",
  "/calendar": "تقویم آموزشی",
  "/forms": "فرم‌ها",
  "/circulars": "بخشنامه‌ها",
  "/professors": "اساتید",
  "/tickets": "تیکت و پشتیبانی",
  "/transcript": "کارنامه تحلیلی",
  "/survey": "نظرسنجی",
  "/profile": "پروفایل",
  "/library": "منابع",
  "/courses": "دروس",
  "/search": "جستجو",
  "/chat": "گفتگو",
};

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

async function compressImage(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || file.type === "image/gif") return file;
  if (file.size < 700_000) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const maxEdge = 1280;
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
    const w = Math.max(1, Math.round(bitmap.width * scale));
    const h = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close();
    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.82)
    );
    if (!blob) return file;
    const name = file.name.replace(/\.\w+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg" });
  } catch {
    return file;
  }
}

async function prepareFiles(list: File[]): Promise<File[]> {
  const prepared: File[] = [];
  for (const f of list) prepared.push(await compressImage(f));
  return prepared;
}

function pageSnippet(): string {
  if (typeof document === "undefined") return "";
  const main = document.querySelector(".page-shell") || document.body;
  const text = (main as HTMLElement).innerText || "";
  return text.replace(/\s+/g, " ").trim().slice(0, 900);
}

function loadList(): ConvMeta[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_LIST) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function loadMsgs(id: string): Msg[] {
  try {
    const raw = JSON.parse(localStorage.getItem(msgKey(id)) || "null");
    if (Array.isArray(raw) && raw.length) return raw;
  } catch {}
  return [WELCOME];
}

function saveMsgs(id: string, msgs: Msg[]) {
  localStorage.setItem(msgKey(id), JSON.stringify(msgs.slice(-80)));
}

function upsertList(list: ConvMeta[], entry: ConvMeta): ConvMeta[] {
  const next = [entry, ...list.filter((c) => c.id !== entry.id)].slice(0, 20);
  localStorage.setItem(STORAGE_LIST, JSON.stringify(next));
  return next;
}

export function AgentBubble() {
  const pathname = usePathname() || "/";
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [side, setSide] = useState<Side>("right");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [faqs, setFaqs] = useState<FaqItem[]>([]);
  const [modelHint, setModelHint] = useState("");
  const [convList, setConvList] = useState<ConvMeta[]>([]);
  const [sessionId, setSessionId] = useState("web-session");
  const [msgs, setMsgs] = useState<Msg[]>([WELCOME]);
  const hydrated = useRef(false);

  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const dragging = useRef(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

  const pageTitle = PAGE_TITLES[pathname] || "این صفحه";
  const hideOnLogin = pathname === "/login";

  useEffect(() => {
    if (typeof window === "undefined") return;
    let id = localStorage.getItem(STORAGE_ACTIVE) || localStorage.getItem("chat_session");
    if (!id) {
      id = `web-${crypto.randomUUID()}`;
    }
    localStorage.setItem(STORAGE_ACTIVE, id);
    localStorage.setItem("chat_session", id);
    setSessionId(id);
    setMsgs(loadMsgs(id));
    setConvList(loadList());
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current || !sessionId || sessionId === "web-session") return;
    saveMsgs(sessionId, msgs);
    const title =
      msgs.find((m) => m.role === "user")?.text?.slice(0, 40) ||
      "گفتگوی جدید";
    setConvList((prev) =>
      upsertList(prev, { id: sessionId, title, updatedAt: Date.now() })
    );
  }, [msgs, sessionId]);

  const snapTo = useCallback(
    (nextSide: Side, nextY: number, smooth: boolean) => {
      const targetX = nextSide === "left" ? EDGE : window.innerWidth - BUBBLE - EDGE;
      const targetY = clamp(nextY, EDGE, window.innerHeight - BUBBLE - EDGE);
      if (smooth) {
        animate(x, targetX, { type: "spring", stiffness: 420, damping: 30, mass: 0.7 });
        animate(y, targetY, { type: "spring", stiffness: 420, damping: 30, mass: 0.7 });
      } else {
        x.set(targetX);
        y.set(targetY);
      }
      setSide(nextSide);
      localStorage.setItem("agent_dock", JSON.stringify({ side: nextSide, y: targetY }));
    },
    [x, y]
  );

  useEffect(() => {
    let saved: { side?: Side; y?: number } = {};
    try {
      saved = JSON.parse(localStorage.getItem("agent_dock") || "{}");
    } catch {}
    const initialSide: Side = saved.side === "left" ? "left" : "right";
    const initialY = typeof saved.y === "number" ? saved.y : window.innerHeight - 180;
    snapTo(initialSide, initialY, false);
  }, [snapTo]);

  useEffect(() => {
    const onResize = () => snapTo(side, y.get(), false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [side, snapTo, y]);

  useEffect(() => {
    fetchSite()
      .then((site) => {
        const list = ((site as { faqs?: FaqItem[] }).faqs || []).filter((f) => f?.question);
        setFaqs(list.slice(0, 8));
      })
      .catch(() => setFaqs([]));
  }, []);

  useEffect(() => {
    if (!open) return;
    document.getElementById("agent-msg-end")?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open, loading, expanded]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  function startNewChat() {
    const id = `web-${crypto.randomUUID()}`;
    localStorage.setItem(STORAGE_ACTIVE, id);
    localStorage.setItem("chat_session", id);
    setSessionId(id);
    setMsgs([WELCOME]);
    setShowHistory(false);
    setModelHint("");
    setFiles([]);
    setText("");
  }

  function openConversation(id: string) {
    localStorage.setItem(STORAGE_ACTIVE, id);
    localStorage.setItem("chat_session", id);
    setSessionId(id);
    setMsgs(loadMsgs(id));
    setShowHistory(false);
    setModelHint("");
  }

  function addFiles(list: FileList | File[] | null) {
    if (!list) return;
    const arr = Array.from(list as ArrayLike<File>);
    if (!arr.length) return;
    setFiles((prev) => [...prev, ...arr].slice(0, MAX_FILES));
  }

  async function sendMessage(raw: string, withFiles: File[] = files) {
    const message = raw.trim();
    if ((!message && !withFiles.length) || loading) return;

    const attached = withFiles.map((f) => f.name);
    setText("");
    setFiles([]);
    setMsgs((m) => [
      ...m,
      { role: "user", text: message || "این فایل را بررسی کن.", files: attached },
    ]);
    setLoading(true);

    const meta = {
      page_path: pathname,
      page_title: pageTitle,
      page_text: pageSnippet(),
      current_page: pathname,
    };

    try {
      const token = localStorage.getItem("token") || undefined;
      let data;
      if (withFiles.length) {
        const prepared = await prepareFiles(withFiles);
        data = await chatWithFiles(message, sessionId, prepared, token, meta);
      } else {
        data = await chat(message, sessionId, token, meta);
      }
      setMsgs((m) => [...m, { role: "bot", text: data.answer || "پاسخی دریافت نشد." }]);
      if (data.source_type === "faq") {
        setModelHint("پاسخ از سوالات متداول");
      } else if (data.model_available === false) {
        setModelHint("مدل قطع است");
      } else if (withFiles.length) {
        setModelHint("فایل بررسی شد");
      } else {
        setModelHint("");
      }
    } catch (err: any) {
      setMsgs((m) => [...m, { role: "bot", text: err?.message || "خطا در دریافت پاسخ" }]);
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await sendMessage(text, files);
  }

  const panelStyle: React.CSSProperties = useMemo(() => {
    if (expanded) {
      return {
        inset: 0,
        width: "100vw",
        height: "100vh",
        maxWidth: "100vw",
        maxHeight: "100vh",
        borderRadius: 0,
        transformOrigin: "center",
        zIndex: 120,
      };
    }
    return side === "left"
      ? { left: EDGE, bottom: 96, transformOrigin: "bottom left" }
      : { right: EDGE, bottom: 96, transformOrigin: "bottom right" };
  }, [expanded, side]);

  if (hideOnLogin) return null;

  return (
    <>
      {!expanded && (
        <motion.button
          type="button"
          className="agent-fab"
          aria-label="دستیار دایان"
          style={{ x, y }}
          drag
          dragMomentum={false}
          dragElastic={0.12}
          whileDrag={{ scale: 1.12 }}
          onDragStart={() => {
            dragging.current = true;
          }}
          onDragEnd={(_, info) => {
            if (!dragging.current) return;
            dragging.current = false;
            const nextSide: Side = info.point.x < window.innerWidth / 2 ? "left" : "right";
            snapTo(nextSide, info.point.y - BUBBLE / 2, true);
          }}
          onTap={() => {
            if (dragging.current) return;
            setOpen((v) => !v);
          }}
        >
          <Bot size={26} />
        </motion.button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            className={`agent-panel glass${expanded ? " agent-panel-expanded" : ""}${dragOver ? " agent-drop-active" : ""}`}
            style={panelStyle}
            initial={{ opacity: 0, scale: 0.86, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 12 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            onDragEnter={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              if (e.currentTarget === e.target) setDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              addFiles(e.dataTransfer.files);
            }}
          >
            <div className="agent-panel-head">
              <div>
                <strong>دایان</strong>
                <div className="agent-page-hint">شما در «{pageTitle}» هستید — کانتکست صفحه حفظ می‌شود</div>
                {modelHint ? <div className="agent-page-hint">{modelHint}</div> : null}
              </div>
              <div className="agent-head-actions">
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShowHistory((v) => !v)}
                  aria-label="تاریخچه"
                  title="تاریخچه گفتگو"
                >
                  <History size={16} />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={startNewChat}
                  aria-label="گفتگوی جدید"
                  title="گفتگوی جدید"
                >
                  <Plus size={16} />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setExpanded((v) => !v)}
                  aria-label={expanded ? "خروج از تمام‌صفحه" : "بزرگ کردن"}
                  title={expanded ? "کوچک کردن" : "تمام‌صفحه"}
                >
                  {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => {
                    setExpanded(false);
                    setOpen(false);
                  }}
                  aria-label="بستن"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {showHistory && (
              <div className="agent-history" aria-label="تاریخچه گفتگوها">
                {convList.length === 0 ? (
                  <p className="agent-page-hint">هنوز گفتگویی ذخیره نشده.</p>
                ) : (
                  convList.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`agent-history-item${c.id === sessionId ? " active" : ""}`}
                      onClick={() => openConversation(c.id)}
                    >
                      <span>{c.title}</span>
                      <small>{new Date(c.updatedAt).toLocaleDateString("fa-IR")}</small>
                    </button>
                  ))
                )}
              </div>
            )}

            {faqs.length > 0 && !showHistory ? (
              <div className="agent-faq-chips" aria-label="سوالات متداول">
                {faqs.map((f) => (
                  <button
                    key={f.id || f.question}
                    type="button"
                    className="agent-faq-chip"
                    disabled={loading}
                    onClick={() => sendMessage(f.question, [])}
                  >
                    {f.question}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="agent-messages">
              {msgs.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.role === "bot" ? renderBotText(m.text) : m.text}
                  {m.files?.length ? (
                    <div className="file-chips" style={{ marginTop: 8 }}>
                      {m.files.map((name) => (
                        <span className="file-chip" key={name}>
                          {name}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
              {loading && <div className="bubble bot thinking">دایان در حال بررسی است...</div>}
              <div id="agent-msg-end" />
            </div>

            {files.length > 0 && (
              <div className="file-chips agent-attach-preview">
                {files.map((f, i) => (
                  <span className="file-chip" key={`${f.name}-${i}`}>
                    {f.type.startsWith("image/") ? (
                      <img
                        className="agent-attach-thumb"
                        src={URL.createObjectURL(f)}
                        alt={f.name}
                      />
                    ) : null}
                    {f.name}
                    <button
                      type="button"
                      onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                      aria-label="حذف فایل"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {dragOver ? <div className="agent-drop-hint">فایل را اینجا رها کن</div> : null}

            <form className="composer" onSubmit={onSubmit}>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPT}
                multiple
                hidden
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                className="icon-btn agent-attach-btn"
                onClick={() => fileInput.current?.click()}
                aria-label="پیوست فایل"
                title="عکس کارنامه، PDF، ورد یا اکسل"
                disabled={loading}
              >
                <Paperclip size={17} />
              </button>
              <input
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onPaste={(e) => {
                  const items = e.clipboardData?.files;
                  if (items?.length) {
                    e.preventDefault();
                    addFiles(items);
                  }
                }}
                placeholder={
                  files.length
                    ? "توضیح بده یا همین الان بفرست..."
                    : expanded
                      ? "سوال بنویس یا عکس/فایل پیوست کن..."
                      : "سوال یا پیوست فایل..."
                }
                disabled={loading}
              />
              <button
                className="icon-btn send"
                disabled={loading || (!text.trim() && !files.length)}
                aria-label="ارسال"
              >
                <Send size={17} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
