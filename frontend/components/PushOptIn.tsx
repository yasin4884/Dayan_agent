"use client";

import { useEffect, useState } from "react";
import { Bell, BellOff } from "lucide-react";

/** درخواست اجازه اعلان PWA — پایه ارسال یادآوری تقویم آموزشی. */
export function PushOptIn() {
  const [state, setState] = useState<NotificationPermission | "unsupported">("default");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setState("unsupported");
      return;
    }
    setState(Notification.permission);
  }, []);

  async function ask() {
    if (state === "unsupported" || busy) return;
    setBusy(true);
    try {
      const result = await Notification.requestPermission();
      setState(result);
      if (result === "granted" && "serviceWorker" in navigator) {
        await navigator.serviceWorker.register("/sw.js").catch(() => null);
      }
    } finally {
      setBusy(false);
    }
  }

  if (state === "unsupported") return null;

  if (state === "granted") {
    return (
      <span className="file-chip" title="اعلان‌ها فعال است">
        <Bell size={13} /> اعلان فعال
      </span>
    );
  }

  return (
    <button className="btn ghost" onClick={ask} disabled={busy} type="button">
      {state === "denied" ? <BellOff size={15} /> : <Bell size={15} />}
      {state === "denied" ? "اعلان مسدود شده" : busy ? "..." : "فعال‌سازی اعلان"}
    </button>
  );
}
