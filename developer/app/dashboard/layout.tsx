"use client";

import { AdminSiteProvider } from "@/lib/AdminSiteContext";
import { AdminShell } from "@/components/AdminShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminSiteProvider>
      <AdminShell>{children}</AdminShell>
    </AdminSiteProvider>
  );
}
