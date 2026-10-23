"use client";

import Link from "next/link";
import { BookOpen, Home, LifeBuoy, Sparkles, Users } from "lucide-react";
import { useAdminSite } from "@/lib/AdminSiteContext";

const CARDS = [
  {
    href: "/dashboard/chat",
    title: "گفتگوی زنده",
    text: "تیکت دانشجویان را همین‌جا جواب بده.",
    icon: LifeBuoy,
  },
  {
    href: "/dashboard/appearance",
    title: "صفحه اصلی",
    text: "لوگو، بنر متحرک، دسترسی سریع و منو.",
    icon: Home,
  },
  {
    href: "/dashboard/content",
    title: "محتوا",
    text: "تقویم، اطلاعیه، بخشنامه، فرم و اساتید.",
    icon: BookOpen,
  },
  {
    href: "/dashboard/knowledge",
    title: "دانش ربات",
    text: "قوانین، فایل Word/Excel/PDF و سایت دانشگاه.",
    icon: Sparkles,
  },
  {
    href: "/dashboard/groups",
    title: "گروه‌ها",
    text: "گروه‌هایی که دانشجو موقع ثبت‌نام می‌بیند.",
    icon: Users,
  },
];

export default function DashboardHome() {
  const { site } = useAdminSite();
  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>سلام{site.brand?.name ? `، ${site.brand.name}` : ""}</h1>
          <p>از اینجا سایت دانشجو و دانش ربات را مدیریت می‌کنید. لاگ سیستم در این پنل نیست.</p>
        </div>
      </header>
      <div className="admin-home-grid">
        {CARDS.map((c) => {
          const Icon = c.icon;
          return (
            <Link key={c.href} href={c.href} className="admin-home-card glass">
              <Icon size={22} />
              <h2>{c.title}</h2>
              <p>{c.text}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
