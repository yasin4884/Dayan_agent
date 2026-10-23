"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchDevLogs, fetchDevServices, restartService } from "@/lib/api";

const LOG_SOURCES = ["api", "frontend", "admin", "developer", "audit"] as const;

export default function OpsPage() {
  const [token, setToken] = useState("");
  const [services, setServices] = useState<any[]>([]);
  const [dbs, setDbs] = useState<Record<string, any>>({});
  const [logSource, setLogSource] = useState<(typeof LOG_SOURCES)[number]>("api");
  const [lines, setLines] = useState<string[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setToken(localStorage.getItem("admin_token") || "");
  }, []);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchDevServices(token);
      setServices(data.services || []);
      setDbs(data.databases || {});
    } catch (e: any) {
      setMsg(e.message || "خطا");
    }
  }, [token]);

  const loadLogs = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchDevLogs(token, logSource, 250);
      setLines(data.lines || []);
    } catch (e: any) {
      setLines([e.message || "خطای لاگ"]);
    }
  }, [token, logSource]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    loadLogs();
    const t = setInterval(loadLogs, 5000);
    return () => clearInterval(t);
  }, [loadLogs]);

  async function onRestart(id: string) {
    setBusy(id);
    setMsg("");
    try {
      const r = await restartService(token, id);
      setMsg(r.message || `ری‌استارت ${id} انجام شد`);
      await refresh();
    } catch (e: any) {
      setMsg(e.message || "ناموفق");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>عملیات سیستم</h1>
          <p>وضعیت سرویس‌ها، دیتابیس‌ها، لاگ زنده و ری‌استارت</p>
        </div>
        <button className="btn ghost" type="button" onClick={() => { refresh(); loadLogs(); }}>
          تازه‌سازی
        </button>
      </header>

      {msg ? <p className="json-hint">{msg}</p> : null}

      <section className="admin-card">
        <h3>دیتابیس‌ها</h3>
        <div className="admin-pills" style={{ flexWrap: "wrap" }}>
          {Object.entries(dbs).map(([k, v]) => (
            <span key={k} className="file-chip">
              {k}: {v?.ok ? "OK" : "DOWN"}
              {v?.chunks != null ? ` · ${v.chunks} chunk` : ""}
            </span>
          ))}
        </div>
      </section>

      <section className="admin-card">
        <h3>سرویس‌ها</h3>
        <div className="admin-stack">
          {services.map((s) => (
            <div key={s.id} className="repeat-item" style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div>
                <strong>{s.label}</strong>
                <p className="json-hint">
                  :{s.port} · {s.running ? `running pid=${s.pid}` : "stopped"}
                </p>
              </div>
              <button className="btn teal" type="button" disabled={busy === s.id} onClick={() => onRestart(s.id)}>
                {busy === s.id ? "..." : "ری‌استارت"}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="admin-card">
        <h3>لاگ‌ها</h3>
        <div className="admin-pills">
          {LOG_SOURCES.map((s) => (
            <button key={s} type="button" className={`btn ${logSource === s ? "teal" : "ghost"}`} onClick={() => setLogSource(s)}>
              {s}
            </button>
          ))}
        </div>
        <pre
          style={{
            marginTop: 12,
            maxHeight: 420,
            overflow: "auto",
            direction: "ltr",
            textAlign: "left",
            fontSize: 12,
            lineHeight: 1.5,
            padding: 12,
            borderRadius: 12,
            background: "rgba(0,0,0,.35)",
            whiteSpace: "pre-wrap",
          }}
        >
          {lines.length ? lines.join("\n") : "(خالی — سرویس را از همین پنل استارت/ری‌استارت کن تا لاگ ثبت شود)"}
        </pre>
      </section>
    </div>
  );
}
