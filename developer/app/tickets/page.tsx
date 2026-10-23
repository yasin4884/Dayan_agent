"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminTicketsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/chat");
  }, [router]);
  return <div className="page-shell" dir="rtl">در حال رفتن به گفتگوی زنده...</div>;
}
