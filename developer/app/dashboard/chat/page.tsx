"use client";

import { TicketsDesk } from "@/components/TicketsDesk";
import { useAdminSite } from "@/lib/AdminSiteContext";

export default function ChatPage() {
  const { token } = useAdminSite();
  return (
    <div className="admin-stack admin-stack-fill">
      <header className="admin-page-head">
        <div>
          <h1>گفتگوی زنده</h1>
          <p>تیکت‌های دانشجویان اینجا به صورت لحظه‌ای می‌آید.</p>
        </div>
      </header>
      <TicketsDesk token={token} />
    </div>
  );
}
