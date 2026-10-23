"use client";

import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { fetchCalendar } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";
import { PushOptIn } from "@/components/PushOptIn";
import { DateTimeCard } from "@/components/DateTimeCard";
import { displayDate } from "@/lib/jalali";

export default function CalendarPage() {
  const [data, setData] = useState<{ title: string; events: any[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCalendar()
      .then(setData)
      .catch((e) => setError(e.message || "خطا"));
  }, []);

  const events = [...(data?.events || [])].sort((a, b) =>
    String(a.date || "").localeCompare(String(b.date || ""))
  );

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title={data?.title || "تقویم آموزشی"} />
        <PushOptIn />
      </header>

      <DateTimeCard />

      {error ? (
        <div className="empty-state glass">{error}</div>
      ) : !events.length ? (
        <div className="empty-state glass">
          <CalendarDays size={18} /> هنوز رویدادی برای گروه شما ثبت نشده است.
        </div>
      ) : (
        <section className="list-stack">
          {events.map((ev) => (
            <article className="list-item glass" key={ev.id}>
              <div className="prof-row">
                <div>
                  <h4>{ev.label || ev.title}</h4>
                  {ev.description ? <p>{ev.description}</p> : null}
                </div>
                <span className="score-pill">{displayDate(ev.date)}</span>
              </div>
              {ev.time ? <div className="meta">ساعت {ev.time}</div> : null}
            </article>
          ))}
        </section>
      )}

      <SiteDock />
    </div>
  );
}
