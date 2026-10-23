"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Paperclip, Plus, Send } from "lucide-react";
import { API_URL, authFetch } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";

type Ticket = {
  id: string;
  subject: string;
  status: string;
  unread_for_user?: number;
  last_message_at?: string;
};
type Message = {
  id: string;
  sender_type: string;
  body: string;
  file_url?: string;
  file_name?: string;
  created_at?: string;
};

function wsUrl(path: string, token: string) {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}${path}?token=${encodeURIComponent(token)}`;
}

function fileHref(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

function fmtTime(iso?: string) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("fa-IR", {
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

async function api(path: string, init?: RequestInit) {
  const res = await authFetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "خطا");
  return data;
}

function appendUnique(prev: Message[], msg: Message) {
  if (prev.some((m) => m.id === msg.id)) return prev;
  return [...prev, msg];
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ ticket?: Ticket; messages: Message[] } | null>(null);
  const [subject, setSubject] = useState("");
  const [firstMsg, setFirstMsg] = useState("");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [typing, setTyping] = useState("");
  const [adminOnline, setAdminOnline] = useState(false);
  const [wsState, setWsState] = useState<"off" | "connecting" | "live">("off");
  const [composing, setComposing] = useState(false);
  const [authed, setAuthed] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const createRef = useRef<HTMLFormElement | null>(null);

  async function loadList() {
    const list = await api("/api/tickets");
    setTickets(Array.isArray(list) ? list : []);
  }

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      setAuthed(false);
      return;
    }
    loadList().catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!active) {
      setWsState("off");
      setAdminOnline(false);
      setTyping("");
      return;
    }
    const token = localStorage.getItem("token") || "";
    setWsState("connecting");
    api(`/api/tickets/${active}`)
      .then((d) => setDetail({ ticket: d, messages: d.messages || [] }))
      .catch((e) => setError(e.message));

    wsRef.current?.close();
    const ws = new WebSocket(wsUrl(`/api/ws/tickets/${active}`, token));
    wsRef.current = ws;
    ws.onopen = () => {
      setWsState("live");
      try {
        ws.send(JSON.stringify({ type: "ping" }));
      } catch {}
    };
    ws.onclose = () => setWsState("off");
    ws.onerror = () => setWsState("off");
    ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data);
        if (event.type === "message" && event.message) {
          setDetail((prev) =>
            prev ? { ...prev, messages: appendUnique(prev.messages, event.message) } : prev
          );
          loadList().catch(() => null);
        }
        if (event.type === "typing") {
          setTyping(
            event.typing && event.actor_type === "admin"
              ? `${event.actor_name || "ادمین"} در حال نوشتن است...`
              : ""
          );
        }
        if (event.type === "presence" || event.type === "pong") {
          const members = event.members || [];
          setAdminOnline(members.some((m: any) => m.actor_type === "admin"));
        }
        if (event.type === "status" && event.ticket) {
          setDetail((prev) => (prev ? { ...prev, ticket: event.ticket } : prev));
          loadList().catch(() => null);
        }
      } catch {}
    };
    const beat = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "ping" }));
        } catch {}
      }
    }, 15000);
    return () => {
      window.clearInterval(beat);
      ws.close();
      wsRef.current = null;
    };
  }, [active]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail?.messages, typing]);

  function startNewChat() {
    setActive(null);
    setDetail(null);
    setComposing(true);
    setTyping("");
    setAdminOnline(false);
    setTimeout(() => createRef.current?.querySelector("input")?.focus(), 50);
  }

  async function createTicket(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const t = await api("/api/tickets", {
        method: "POST",
        body: JSON.stringify({ subject, body: firstMsg }),
      });
      setSubject("");
      setFirstMsg("");
      setComposing(false);
      await loadList();
      setActive(t.id);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function sendTyping(on: boolean) {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: "typing", typing: on }));
    }
  }

  function onDraftChange(value: string) {
    setDraft(value);
    sendTyping(true);
    if (typingTimer.current) clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => sendTyping(false), 1200);
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!active || !draft.trim()) return;
    const body = draft.trim();
    setDraft("");
    setError("");
    sendTyping(false);
    try {
      const msg = await api(`/api/tickets/${active}/messages`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setDetail((prev) => (prev ? { ...prev, messages: appendUnique(prev.messages, msg) } : prev));
      await loadList();
    } catch (err: any) {
      setDraft(body);
      setError(err.message || "ارسال ناموفق بود");
    }
  }

  async function sendFile(file: File) {
    if (!active) return;
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("body", "");
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${API_URL}/api/tickets/${active}/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.message || "آپلود ناموفق");
      setDetail((prev) => (prev ? { ...prev, messages: appendUnique(prev.messages, data) } : prev));
    } catch (err: any) {
      setError(err.message || "آپلود ناموفق");
    }
  }

  if (!authed) {
    return (
      <div className="page-shell" dir="rtl">
        <div className="empty-state glass">
          برای تیکت باید وارد حساب شوید.
          <div style={{ marginTop: 12 }}>
            <Link className="btn teal" href="/login">
              ورود
            </Link>
          </div>
        </div>
        <SiteDock />
      </div>
    );
  }

  const statusLabel =
    detail?.ticket?.status === "closed"
      ? "بسته"
      : detail?.ticket?.status === "pending"
        ? "در انتظار شما"
        : "باز";

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="تیکت و پشتیبانی" />
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {active ? (
            <>
              <span className={`file-chip ${adminOnline ? "" : ""}`}>
                {adminOnline ? "ادمین آنلاین" : "ادمین آفلاین"}
              </span>
              <span className="file-chip">
                {wsState === "live" ? "زنده" : wsState === "connecting" ? "در حال اتصال..." : "آفلاین"}
              </span>
            </>
          ) : null}
          <button className="btn teal" type="button" onClick={startNewChat}>
            <Plus size={15} /> گفتگوی جدید
          </button>
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      <section className="bottom-grid">
        <div className="list-stack">
          {(composing || !tickets.length) && (
            <form ref={createRef} className="list-item glass" onSubmit={createTicket}>
              <h4>گفتگوی جدید</h4>
              <label className="field">
                <span>موضوع</span>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} required minLength={3} />
              </label>
              <label className="field">
                <span>پیام اول</span>
                <textarea rows={3} value={firstMsg} onChange={(e) => setFirstMsg(e.target.value)} />
              </label>
              <button className="btn teal">شروع گفتگو</button>
            </form>
          )}

          {tickets.map((t) => (
            <button
              key={t.id}
              type="button"
              className="list-item glass"
              style={{
                textAlign: "right",
                cursor: "pointer",
                borderColor: active === t.id ? "var(--accent)" : undefined,
              }}
              onClick={() => {
                setComposing(false);
                setActive(t.id);
              }}
            >
              <h4>{t.subject}</h4>
              <div className="meta">
                <span>{t.status === "closed" ? "بسته" : t.status === "pending" ? "در انتظار شما" : "باز"}</span>
                <span>{fmtTime(t.last_message_at)}</span>
                {t.unread_for_user ? <span className="pin">{t.unread_for_user} خوانده‌نشده</span> : null}
              </div>
            </button>
          ))}
        </div>

        <div
          className="glass"
          style={{ borderRadius: 24, padding: 12, minHeight: 420, display: "flex", flexDirection: "column" }}
        >
          {!active ? (
            <div className="empty-state" style={{ margin: "auto" }}>
              <p className="json-hint">یک گفتگو را از لیست انتخاب کن یا «گفتگوی جدید» بساز.</p>
              <button className="btn teal" type="button" onClick={startNewChat}>
                <Plus size={15} /> گفتگوی جدید
              </button>
            </div>
          ) : (
            <>
              <div className="agent-panel-head">
                <div>
                  <strong>{detail?.ticket?.subject || "گفتگو"}</strong>
                  <div className="json-hint" style={{ margin: 0 }}>
                    {statusLabel}
                    {adminOnline ? " · ادمین آنلاین" : " · ادمین آفلاین"}
                    {typing ? ` · ${typing}` : ""}
                  </div>
                </div>
                {detail?.ticket?.status !== "closed" ? (
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() =>
                      api(`/api/tickets/${active}/close`, { method: "POST" })
                        .then(loadList)
                        .then(() =>
                          api(`/api/tickets/${active}`).then((d) =>
                            setDetail({ ticket: d, messages: d.messages || [] })
                          )
                        )
                    }
                  >
                    بستن
                  </button>
                ) : (
                  <span className="file-chip">بسته شده</span>
                )}
              </div>
              <div className="agent-messages" style={{ flex: 1 }}>
                {(detail?.messages || []).map((m) => (
                  <div key={m.id} className={`bubble ${m.sender_type === "user" ? "user" : "bot"}`}>
                    {m.body}
                    {m.file_url ? (
                      <div>
                        <a href={fileHref(m.file_url)} target="_blank" rel="noreferrer">
                          {m.file_name || "فایل"}
                        </a>
                      </div>
                    ) : null}
                    {m.created_at ? (
                      <div style={{ fontSize: ".7rem", opacity: 0.65, marginTop: 4 }}>{fmtTime(m.created_at)}</div>
                    ) : null}
                  </div>
                ))}
                {typing ? <div className="bubble bot thinking">{typing}</div> : null}
                <div ref={endRef} />
              </div>
              <form className="composer" onSubmit={send}>
                <input
                  ref={fileRef}
                  type="file"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) sendFile(f);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => fileRef.current?.click()}
                  aria-label="پیوست"
                >
                  <Paperclip size={16} />
                </button>
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => onDraftChange(e.target.value)}
                  onBlur={() => sendTyping(false)}
                  placeholder="پیام..."
                  disabled={detail?.ticket?.status === "closed"}
                />
                <button
                  className="icon-btn send"
                  disabled={detail?.ticket?.status === "closed"}
                  aria-label="ارسال"
                >
                  <Send size={16} />
                </button>
              </form>
            </>
          )}
        </div>
      </section>
      <SiteDock />
    </div>
  );
}
