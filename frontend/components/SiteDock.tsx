"use client";

import { useEffect, useState } from "react";
import { fetchSite, SiteConfig } from "@/lib/api";
import { LiquidDock } from "@/components/LiquidDock";

/** داک پایین که آیتم‌هایش از پنل ادمین می‌آید. */
export function SiteDock() {
  const [site, setSite] = useState<SiteConfig | null>(null);

  useEffect(() => {
    fetchSite().then(setSite).catch(() => null);
  }, []);

  const items = site?.nav || [];
  const hasNotif = (site?.notifications || []).length > 0;

  return (
    <LiquidDock
      items={items.map((n) => ({
        ...n,
        dot: n.id === "notifications" && hasNotif,
      }))}
    />
  );
}
