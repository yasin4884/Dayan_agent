"use client";

import { useEffect, useState } from "react";
import { formatJalaliDate, formatTime, tehranNow } from "@/lib/jalali";

/** نوار باریک تاریخ/ساعت شمسی — هم‌سبک گلس قبلی */
export function DateTimeCard() {
  const [now, setNow] = useState(() => tehranNow());

  useEffect(() => {
    const id = setInterval(() => setNow(tehranNow()), 1000);
    return () => clearInterval(id);
  }, []);

  const d = formatJalaliDate(now);
  const t = formatTime(now);

  return (
    <div className="datetime-strip glass" aria-live="polite">
      <span className="datetime-strip-date">{d.text}</span>
      <span className="datetime-strip-sep" aria-hidden>
        ·
      </span>
      <span className="datetime-strip-time" dir="ltr">
        {t}
      </span>
    </div>
  );
}
