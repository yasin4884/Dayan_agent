"use client";

import { useEffect, useState } from "react";
import { Download, ScrollText } from "lucide-react";
import { API_URL, fetchCirculars } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";

function fileHref(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export default function CircularsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCirculars()
      .then((d) => setItems(Array.isArray(d) ? d : []))
      .catch((e) => setError(e.message || "خطا"));
  }, []);

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="بخشنامه‌ها" />
      </header>

      {error ? (
        <div className="empty-state glass">{error}</div>
      ) : !items.length ? (
        <div className="empty-state glass">
          <ScrollText size={18} /> بخشنامه‌ای برای گروه شما ثبت نشده است.
        </div>
      ) : (
        <section className="list-stack">
          {items.map((c) => (
            <article className="list-item glass" key={c.id}>
              <h4>{c.title}</h4>
              {c.body ? <p>{c.body}</p> : null}
              <div className="meta">
                {c.created_at ? <span>{c.created_at}</span> : null}
                {c.file_url ? (
                  <a href={fileHref(c.file_url)} target="_blank" rel="noreferrer">
                    <Download size={13} /> دریافت فایل
                  </a>
                ) : null}
              </div>
            </article>
          ))}
        </section>
      )}

      <SiteDock />
    </div>
  );
}
