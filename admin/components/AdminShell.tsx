"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Home,
  LayoutGrid,
  LifeBuoy,
  LogOut,
  Save,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import { useAdminSite } from "@/lib/AdminSiteContext";
import { useTheme } from "@/components/ThemeProvider";

const NAV = [
  { href: "/dashboard/chat", label: "گفتگوی زنده", icon: LifeBuoy },
  { href: "/dashboard", label: "نمای کلی", icon: LayoutGrid, exact: true },
  { href: "/dashboard/appearance", label: "صفحه اصلی", icon: Home },
  { href: "/dashboard/content", label: "محتوا", icon: BookOpen },
  { href: "/dashboard/knowledge", label: "دانش ربات", icon: Sparkles },
  { href: "/dashboard/groups", label: "گروه‌ها", icon: Users },
  { href: "/dashboard/settings", label: "تنظیمات", icon: Settings },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { persist, saving, msg, site } = useAdminSite();
  const { theme, toggle } = useTheme();

  const showSave = pathname !== "/dashboard/chat" && pathname !== "/dashboard/knowledge";

  return (
    <div className="admin-shell" dir="rtl">
      <aside className="admin-rail glass">
        <div className="admin-rail-brand">
          <div className="brand-mark">
            <span /><span /><span /><span />
          </div>
          <div>
            <strong>{site.brand?.name || "دایان"}</strong>
            <p>پنل مدیریت</p>
          </div>
        </div>

        <nav className="admin-rail-nav">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href} className={`admin-rail-link ${active ? "active" : ""}`}>
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="admin-rail-foot">
          {showSave ? (
            <button className="btn teal" type="button" onClick={() => persist()} disabled={saving}>
              <Save size={15} /> {saving ? "در حال ذخیره..." : "ذخیره تغییرات"}
            </button>
          ) : null}
          <button className="btn ghost" type="button" onClick={toggle}>
            {theme === "dark" ? "حالت روشن" : "حالت تیره"}
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              localStorage.removeItem("admin_token");
              localStorage.removeItem("admin_refresh_token");
              localStorage.removeItem("admin_user");
              router.push("/");
            }}
          >
            <LogOut size={15} /> خروج
          </button>
          {msg ? <p className="json-hint">{msg}</p> : null}
        </div>
      </aside>
      <main className="admin-canvas">{children}</main>
    </div>
  );
}
