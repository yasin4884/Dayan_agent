"use client";

import { FormEvent, useState } from "react";
import { API_URL } from "@/lib/api";
import { SiteDock } from "@/components/SiteDock";

export default function TranscriptPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("session_id", localStorage.getItem("chat_session") || `tr-${Date.now()}`);
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/transcript/analyze`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || data.detail || "تحلیل ناموفق");
      setResult(data);
    } catch (err: any) {
      setError(err.message || "خطا");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell" dir="rtl">
      <section className="glass" style={{ borderRadius: 24, padding: 18 }}>
        <h1>کارنامه تحلیلی</h1>
        <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>
          فایل کارنامه (PDF / Excel / Word) را بارگذاری کن تا وضعیت تحصیلی‌ات تحلیل شود.
        </p>
        <form onSubmit={onSubmit} className="admin-section">
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.xls,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button className="btn green" disabled={loading || !file}>
            {loading ? "در حال تحلیل..." : "شروع تحلیل"}
          </button>
        </form>
        {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
        {result && (
          <div style={{ marginTop: 16 }}>
            <h3>خلاصه آماری</h3>
            <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(result.stats, null, 2)}</pre>
            <h3>تحلیل هوشمند</h3>
            <p style={{ lineHeight: 1.8, whiteSpace: "pre-wrap" }}>{result.analysis?.answer}</p>
          </div>
        )}
      </section>
      <SiteDock />
    </div>
  );
}
