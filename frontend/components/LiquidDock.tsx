"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  Bell,
  BookOpen,
  Calendar,
  FileText,
  Home,
  LifeBuoy,
  Search,
  ScrollText,
  User,
  Users,
} from "lucide-react";

const icons: Record<string, LucideIcon> = {
  home: Home,
  bell: Bell,
  calendar: Calendar,
  file: FileText,
  document: ScrollText,
  ticket: LifeBuoy,
  user: User,
  users: Users,
  book: BookOpen,
  search: Search,
};

export type DockItem = {
  id: string;
  label: string;
  href: string;
  icon: string;
  dot?: boolean;
};

export function LiquidDock({ items }: { items: DockItem[] }) {
  const pathname = usePathname();
  const visible = (items || []).filter((i) => i.id !== "chat" && i.href !== "/chat");
  if (!visible.length) return null;

  return (
    <div className="dock-wrap">
      <nav className="dock" dir="rtl">
        {visible.map((item) => {
          const Icon = icons[item.icon] || Home;
          const active = pathname === item.href;
          return (
            <Link
              key={item.id}
              href={item.href}
              className={`dock-item ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {active && (
                <motion.span
                  className="dock-blob"
                  layoutId="dock-blob"
                  transition={{ type: "spring", stiffness: 420, damping: 32, mass: 0.6 }}
                />
              )}
              <Icon size={19} />
              <span className="dock-label">{item.label}</span>
              {item.dot && <span className="dock-dot" />}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
