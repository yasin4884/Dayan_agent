"use client";

import { SiteDock } from "@/components/SiteDock";

export default function Placeholder({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="page-shell" dir="rtl">
      <section className="glass" style={{ borderRadius: 26, padding: 20 }}>
        <h1 style={{ marginTop: 0, fontSize: "1.3rem" }}>{title}</h1>
        <p style={{ color: "var(--muted)", lineHeight: 1.9 }}>{body}</p>
      </section>
      <SiteDock />
    </div>
  );
}
