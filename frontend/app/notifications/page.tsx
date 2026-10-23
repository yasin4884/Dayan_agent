"use client";

import { useEffect, useMemo, useState } from "react";
import { Bell } from "lucide-react";
import { fetchNotifications } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";
import { PushOptIn } from "@/components/PushOptIn";

type Sort = "newest" | "oldest" | "pinned";

export default function NotificationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [sort, setSort] = useState<Sort>("newest");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchNotifications()
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message || "خطا"))
      .finally(() => setLoading(false));
  }, []);

  const sorted = useMemo(() => {
    const list = [...items];
    if (sort === "pinned") {
      return list.sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));
    }
    list.sort((a, b) =>
      String(a.created_at || "").localeCompare(String(b.created_at || ""))
    );
    return sort === "newest" ? list.reverse() : list;
  }, [items, sort]);

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="اطلاع‌رسانی‌ها" />
        <div className="topbar-actions">
          <PushOptIn />
        </div>
      </header>

      <div className="chip-toggle" style={{ margin: "6px 4px 14px" }}>
        <button className={sort === "newest" ? "on" : ""} onClick={() => setSort("newest")}>
          جدیدترین
        </button>
        <button className={sort === "oldest" ? "on" : ""} onClick={() => setSort("oldest")}>
          قدیمی‌ترین
        </button>
        <button className={sort === "pinned" ? "on" : ""} onClick={() => setSort("pinned")}>
          مهم‌ها
        </button>
      </div>

      {loading ? (
        <div className="empty-state glass">در حال بارگذاری...</div>
      ) : error ? (
        <div className="empty-state glass">{error}</div>
      ) : !sorted.length ? (
        <div className="empty-state glass">
          <Bell size={18} /> اطلاعیه‌ای برای گروه شما ثبت نشده است.
        </div>
      ) : (
        <section className="list-stack">
          {sorted.map((n) => (
            <article className="list-item glass" key={n.id}>
              <h4>
                {n.title}
                {n.pinned ? <span className="pin"> • مهم</span> : null}
              </h4>
              {n.body ? <p>{n.body}</p> : null}
              {n.created_at ? <div className="meta">{n.created_at}</div> : null}
            </article>
          ))}
        </section>
      )}

      <SiteDock />
    </div>
  );
}
