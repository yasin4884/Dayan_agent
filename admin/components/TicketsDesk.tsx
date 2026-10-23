"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Paperclip, Send } from "lucide-react";
import { API_URL } from "@/lib/api";

type Ticket = {
  id: string;
  subject: string;
  status: string;
  user_name?: string;
  student_code?: string;
  unread_for_admin?: number;
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
  return `${API_URL.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(token)}`;
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

async function api(token: string, path: string, init?: RequestInit) {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "خطا");
  return data;
}

function appendUnique(prev: Message[], msg: Message) {
  if (prev.some((m) => m.id === msg.id)) return prev;
  return [...prev, msg];
}

export function TicketsDesk({ token }: { token: string }) {
  const [list, setList] = useState<Ticket[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState("");
  const [userOnline, setUserOnline] = useState(false);
  const [wsState, setWsState] = useState<"off" | "live">("off");
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const inboxRef = useRef<WebSocket | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function reload() {
    const rows = await api(token, "/api/admin/tickets");
    setList(Array.isArray(rows) ? rows : []);
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message));
    const inbox = new WebSocket(wsUrl("/api/ws/admin/inbox", token));
    inboxRef.current = inbox;
    inbox.onmessage = () => reload().catch(() => null);
    return () => inbox.close();
  }, [token]);

  useEffect(() => {
    if (!active) return;
    api(token, `/api/admin/tickets/${active}`)
      .then((d) => {
        setTicket(d);
        setMessages(d.messages || []);
      })
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
    ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data);
        if (event.type === "message" && event.message) {
          setMessages((prev) => appendUnique(prev, event.message));
          reload().catch(() => null);
        }
        if (event.type === "typing" && event.actor_type === "user") {
          setTyping(event.typing ? `${event.actor_name || "کاربر"} در حال نوشتن است...` : "");
        }
        if (event.type === "presence" || event.type === "pong") {
          const members = event.members || [];
          setUserOnline(members.some((m: any) => m.actor_type === "user"));
        }
        if (event.type === "status") setTicket(event.ticket);
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
    };
  }, [active, token]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

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
      const msg = await api(token, `/api/admin/tickets/${active}/messages`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setMessages((prev) => appendUnique(prev, msg));
      await reload();
    } catch (err: any) {
      setDraft(body);
      setError(err.message || "ارسال ناموفق بود");
    }
  }

  const openCount = list.filter((t) => t.status !== "closed").length;

  return (
    <div className="chat-desk">
      <aside className="chat-desk-list">
        <div className="chat-desk-list-head">
          <h2>گفتگوها</h2>
          <span>{openCount} باز</span>
        </div>
        {error ? <p className="form-error">{error}</p> : null}
        {!list.length ? <p className="json-hint">هنوز تیکتی نیامده است.</p> : null}
        {list.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`chat-thread ${active === t.id ? "active" : ""}`}
            onClick={() => setActive(t.id)}
          >
            <strong>
              {t.subject}
              {t.unread_for_admin ? <em>{t.unread_for_admin}</em> : null}
            </strong>
            <span>
              {t.user_name} {t.student_code ? `· ${t.student_code}` : ""}
            </span>
            <small>
              {t.status === "closed" ? "بسته" : t.status === "pending" ? "در انتظار دانشجو" : "باز"}
              {t.last_message_at ? ` · ${fmtTime(t.last_message_at)}` : ""}
            </small>
          </button>
        ))}
      </aside>

      <section className="chat-desk-pane">
        {!active ? (
          <div className="chat-empty">یک گفتگو را از سمت راست انتخاب کنید.</div>
        ) : (
          <>
            <header className="chat-desk-head">
              <div>
                <strong>{ticket?.subject}</strong>
                <p>
                  {ticket?.user_name} {ticket?.student_code ? `· ${ticket.student_code}` : ""}
                  {" · "}
                  {userOnline ? "دانشجو آنلاین" : "دانشجو آفلاین"}
                  {" · "}
                  {wsState === "live" ? "زنده" : "آفلاین"}
                </p>
              </div>
              {ticket?.status !== "closed" ? (
                <button
                  className="btn ghost"
                  type="button"
                  onClick={() =>
                    api(token, `/api/admin/tickets/${active}`, {
                      method: "PATCH",
                      body: JSON.stringify({ status: "closed" }),
                    }).then(reload)
                  }
                >
                  بستن تیکت
                </button>
              ) : (
                <span className="file-chip">بسته شده</span>
              )}
            </header>
            <div className="chat-desk-messages">
              {messages.map((m) => (
                <div key={m.id} className={`bubble ${m.sender_type === "admin" ? "user" : "bot"}`}>
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
            <form className="composer chat-desk-composer" onSubmit={send}>
              <input
                ref={fileRef}
                type="file"
                hidden
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f || !active) return;
                  const form = new FormData();
                  form.append("file", f);
                  const res = await fetch(`${API_URL}/api/admin/tickets/${active}/upload`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                    body: form,
                  });
                  const data = await res.json().catch(() => ({}));
                  if (res.ok) setMessages((prev) => appendUnique(prev, data));
                  e.target.value = "";
                }}
              />
              <button type="button" className="icon-btn" onClick={() => fileRef.current?.click()}>
                <Paperclip size={16} />
              </button>
              <input
                value={draft}
                onChange={(e) => onDraftChange(e.target.value)}
                onBlur={() => sendTyping(false)}
                placeholder="پاسخ به دانشجو..."
                disabled={ticket?.status === "closed"}
              />
              <button className="icon-btn send" type="submit" disabled={ticket?.status === "closed"}>
                <Send size={16} />
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
