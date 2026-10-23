"use client";

import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";
import { API_URL, fetchForms } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";

function fileHref(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export default function FormsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchForms()
      .then((d) => setItems(Array.isArray(d) ? d : []))
      .catch((e) => setError(e.message || "خطا"));
  }, []);

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="فرم‌ها" />
      </header>

      {error ? (
        <div className="empty-state glass">{error}</div>
      ) : !items.length ? (
        <div className="empty-state glass">
          <FileText size={18} /> فرمی برای گروه شما بارگذاری نشده است.
        </div>
      ) : (
        <section className="list-stack">
          {items.map((f) => (
            <article className="list-item glass" key={f.id || f.slug}>
              <div className="prof-row">
                <div>
                  <h4>{f.title}</h4>
                  {f.description ? <p>{f.description}</p> : null}
                </div>
                {f.file_url ? (
                  <a className="btn teal" href={fileHref(f.file_url)} target="_blank" rel="noreferrer">
                    <Download size={15} />
                    دریافت
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
