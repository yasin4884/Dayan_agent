"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  Bell,
  Calendar,
  ExternalLink,
  FileText,
  GraduationCap,
  LogIn,
  Moon,
  ScrollText,
  Send,
  Sun,
  Ticket,
  UserRound,
} from "lucide-react";
import { fetchSite, SiteConfig } from "@/lib/api";
import { BannerSlider } from "@/components/BannerSlider";
import { BrandMark, mediaUrl } from "@/components/BrandMark";
import { DateTimeCard } from "@/components/DateTimeCard";
import { LiquidDock } from "@/components/LiquidDock";
import { useTheme } from "@/components/ThemeProvider";
import { displayDate } from "@/lib/jalali";

const quickIcons: Record<string, LucideIcon> = {
  bell: Bell,
  calendar: Calendar,
  file: FileText,
  document: ScrollText,
  graduation: GraduationCap,
  user: UserRound,
  ticket: Ticket,
  home: FileText,
};

const DEFAULT_QUICK = [
  { id: "n", title: "اطلاع‌رسانی", href: "/notifications", icon: "bell", color: "teal", button_label: "ورود" },
  { id: "c", title: "تقویم", href: "/calendar", icon: "calendar", color: "blue", button_label: "ورود" },
  { id: "f", title: "فرم‌ها", href: "/forms", icon: "file", color: "orange", button_label: "ورود" },
  { id: "t", title: "تیکت", href: "/tickets", icon: "ticket", color: "green", button_label: "ورود" },
];

export default function HomePage() {
  const [site, setSite] = useState<SiteConfig | null>(null);
  const [error, setError] = useState("");
  const [user, setUser] = useState<any>(null);
  const { theme, toggle } = useTheme();

  useEffect(() => {
    fetchSite()
      .then(setSite)
      .catch((e) => setError(e.message || "خطا"));
    try {
      const raw = localStorage.getItem("user");
      if (raw) setUser(JSON.parse(raw));
    } catch {}
  }, []);

  if (error) {
    return (
      <div className="page-shell" dir="rtl">
        <div className="empty-state glass">
          ارتباط با سرور برقرار نشد.
          <p style={{ marginTop: 8 }}>{error}</p>
        </div>
      </div>
    );
  }

  if (!site) {
    return (
      <div className="page-shell" dir="rtl">
        <div className="empty-state glass">در حال بارگذاری...</div>
      </div>
    );
  }

  const brand = site.brand?.name || site.brand?.product_title || "دایان";
  const websiteUrl = site.brand?.website_url || "";
  const websiteLabel = site.brand?.website_label || "سایت دانشگاه";
  const banners = site.banners || [];
  const fromCms = (site.quick_actions || site.modules || []).filter((m: any) => m.enabled !== false);
  const quickActions = fromCms.length ? fromCms : DEFAULT_QUICK;
  const calendarEvents = site.calendar?.events || [];
  const notifications = (site.notifications || []).slice(0, 4);
  const circulars = (site.circulars || []).slice(0, 3);
  const professors = (site.professors || []).slice(0, 5);
  const comments = site.comments || [];

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark showTagline />

        <div className="topbar-actions">
          {websiteUrl ? (
            <a className="icon-btn" href={websiteUrl} target="_blank" rel="noreferrer" aria-label={websiteLabel} title={websiteLabel}>
              <ExternalLink size={17} />
            </a>
          ) : null}
          <button className="icon-btn" onClick={toggle} aria-label="تغییر تم">
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          {user ? (
            <Link className="btn ghost" href="/profile">
              <UserRound size={16} />
              {user.first_name || "پروفایل"}
            </Link>
          ) : (
            <Link className="btn teal" href="/login">
              <LogIn size={16} />
              ورود / ثبت‌نام
            </Link>
          )}
        </div>
      </header>

      {/* بنر همیشه در جای قبلی — اگر خالی باشد پیام پنل ادمین */}
      <BannerSlider banners={banners} />

      {/* ساعت/تاریخ شمسی؛ جمع‌وجور زیر بنر */}
      <DateTimeCard />

      <div className="section-head">
        <h2>دسترسی سریع</h2>
      </div>
      <section className="quick-grid">
        {quickActions.map((mod: any, idx: number) => {
          const Icon = quickIcons[mod.icon] || FileText;
          return (
            <motion.article
              key={mod.id || idx}
              className={`quick-card glass ${mod.color || "teal"}`}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 * idx }}
            >
              {mod.badge ? <span className="badge">{mod.badge}</span> : null}
              <div className="qa-icon">
                <Icon size={19} />
              </div>
              <h3>{mod.title}</h3>
              <Link className={`btn ${mod.color || "teal"}`} href={mod.href || "/"}>
                {mod.button_label || "ورود"}
              </Link>
            </motion.article>
          );
        })}
      </section>

      <div className="section-head">
        <h2>{site.calendar?.title || "تقویم آموزشی"}</h2>
        <Link href="/calendar">همه</Link>
      </div>
      {calendarEvents.length ? (
        <section className="calendar glass">
          <div className="timeline">
            {calendarEvents.map((ev: any) => (
              <div className="event" key={ev.id}>
                <strong>{ev.label || ev.title}</strong>
                <span>{displayDate(ev.date)}</span>
                {ev.time ? <span>{ev.time}</span> : null}
              </div>
            ))}
          </div>
        </section>
      ) : (
        <div className="empty-state glass">هنوز رویدادی در تقویم ثبت نشده است.</div>
      )}

      <div className="section-head">
        <h2>اطلاع‌رسانی‌ها</h2>
        <Link href="/notifications">همه</Link>
      </div>
      {notifications.length ? (
        <section className="list-stack">
          {notifications.map((n: any) => (
            <article className="list-item glass" key={n.id}>
              <h4>
                {n.title}
                {n.pinned ? <span className="pin"> • مهم</span> : null}
              </h4>
              {n.body ? <p>{n.body}</p> : null}
              {n.created_at ? <div className="meta">{displayDate(n.created_at)}</div> : null}
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-state glass">اطلاعیه‌ای برای گروه شما ثبت نشده است.</div>
      )}

      <div className="section-head">
        <h2>بخشنامه‌ها</h2>
        <Link href="/circulars">همه</Link>
      </div>
      {circulars.length ? (
        <section className="list-stack">
          {circulars.map((c: any) => (
            <article className="list-item glass" key={c.id}>
              <h4>{c.title}</h4>
              {c.body ? <p>{c.body}</p> : null}
              {c.file_url ? (
                <a className="meta" href={mediaUrl(c.file_url)} target="_blank" rel="noreferrer">
                  دریافت فایل
                </a>
              ) : null}
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-state glass">بخشنامه‌ای ثبت نشده است.</div>
      )}

      <div className="section-head">
        <h2>اساتید و امتیازها</h2>
        <Link href="/professors">همه</Link>
      </div>
      {professors.length ? (
        <section className="list-stack">
          {professors.map((p: any) => (
            <article className="list-item glass" key={p.id}>
              <div className="prof-row">
                <div>
                  <h4>{p.full_name}</h4>
                  {p.course ? <p>{p.course}</p> : null}
                </div>
                <span className="score-pill">{p.score ?? "—"}</span>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-state glass">هنوز استادی برای گروه شما ثبت نشده است.</div>
      )}

      <div className="section-head">
        <h2>ارتباط با ما</h2>
      </div>
      <section className="bottom-grid">
        {site.telegram?.enabled && (site.telegram.title || site.telegram.url) ? (
          <div className="telegram-card">
            <h3>{site.telegram.title || "کانال تلگرام"}</h3>
            {site.telegram.description ? <p>{site.telegram.description}</p> : null}
            <a className="btn" href={site.telegram.url || "#"} target="_blank" rel="noreferrer">
              <Send size={16} />
              {site.telegram.button_label || "عضویت"}
            </a>
          </div>
        ) : (
          <div className="empty-state glass">لینک کانال تلگرام از پنل ادمین تنظیم نشده است.</div>
        )}

        <div className="glass" style={{ borderRadius: 24, padding: 16 }}>
          <h3 style={{ margin: "0 0 10px", fontSize: ".98rem" }}>نظرات کاربران</h3>
          {comments.length ? (
            comments.slice(0, 3).map((c: any) => (
              <div key={c.id} style={{ marginBottom: 12 }}>
                <strong style={{ fontSize: ".9rem" }}>{c.author}</strong>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", lineHeight: 1.8, fontSize: ".88rem" }}>
                  {c.text}
                </p>
              </div>
            ))
          ) : (
            <p style={{ color: "var(--muted)", fontSize: ".9rem", margin: 0 }}>
              هنوز نظری تایید نشده است.
            </p>
          )}
        </div>
      </section>

      <LiquidDock
        items={(site.nav || []).map((n: any) => ({
          ...n,
          dot: n.id === "notifications" && notifications.length > 0,
        }))}
      />
    </div>
  );
}
