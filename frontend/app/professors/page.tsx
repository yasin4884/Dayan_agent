"use client";

import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { fetchProfessors } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";

export default function ProfessorsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchProfessors()
      .then((d) => setItems(Array.isArray(d) ? d : []))
      .catch((e) => setError(e.message || "خطا"));
  }, []);

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="اساتید و امتیازها" />
      </header>

      {error ? (
        <div className="empty-state glass">{error}</div>
      ) : !items.length ? (
        <div className="empty-state glass">
          <GraduationCap size={18} /> استادی برای گروه شما ثبت نشده است.
        </div>
      ) : (
        <section className="list-stack">
          {items.map((p, i) => (
            <article className="list-item glass" key={p.id || i}>
              <div className="prof-row">
                <div>
                  <h4>
                    {i + 1}. {p.full_name}
                  </h4>
                  {p.course ? <p>{p.course}</p> : null}
                  {p.note ? <div className="meta">{p.note}</div> : null}
                </div>
                <span className="score-pill">{p.score ?? "—"}</span>
              </div>
            </article>
          ))}
        </section>
      )}

      <SiteDock />
    </div>
  );
}
