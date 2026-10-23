"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { usePathname, useRouter } from "next/navigation";

const TOUR_KEY = "dayan_tour_done";

const STEPS = [
  {
    path: "/",
    title: "صفحه اصلی",
    body: "بنرها، میانبرها و آخرین اطلاعیه‌ها اینجاست. از اینجا سریع به بخش‌های مهم می‌روی.",
  },
  {
    path: "/calendar",
    title: "تقویم آموزشی",
    body: "رویدادها و مهلت‌ها به شمسی نمایش داده می‌شوند.",
  },
  {
    path: "/forms",
    title: "فرم‌ها",
    body: "فرم‌های آموزشی را دانلود کن. اگر از دایان بپرسی، لینک همان فرم را می‌دهد.",
  },
  {
    path: "/circulars",
    title: "بخشنامه‌ها",
    body: "آیین‌نامه‌ها و اطلاعیه‌های رسمی اینجا جمع شده‌اند.",
  },
  {
    path: "/tickets",
    title: "تیکت",
    body: "اگر مشکل حل نشد، از اینجا برای پشتیبانی تیکت بساز.",
  },
  {
    path: "/profile",
    title: "پروفایل",
    body: "اطلاعات حساب و گروه تحصیلی‌ات اینجاست.",
  },
];

export function OnboardingTour() {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (pathname === "/login") return;
    const token = localStorage.getItem("token");
    if (!token) return;
    if (localStorage.getItem(TOUR_KEY) === "1") return;
    setActive(true);
    setStep(0);
  }, [pathname]);

  useEffect(() => {
    if (!active) return;
    const target = STEPS[step]?.path;
    if (target && pathname !== target) {
      router.push(target);
    }
  }, [active, step, pathname, router]);

  function finish() {
    localStorage.setItem(TOUR_KEY, "1");
    setActive(false);
  }

  function next() {
    if (step >= STEPS.length - 1) {
      finish();
      return;
    }
    setStep((s) => s + 1);
  }

  if (!active) return null;
  const current = STEPS[step];

  return (
    <AnimatePresence>
      <motion.div
        className="tour-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="tour-card glass"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 280, damping: 24 }}
        >
          <p className="tour-step">
            معرفی بخش‌ها · {step + 1} از {STEPS.length}
          </p>
          <h2>{current.title}</h2>
          <p>{current.body}</p>
          <p className="tour-hint">حباب دایان همیشه گوشه صفحه است؛ می‌توانی تمام‌صفحه هم بازش کنی.</p>
          <div className="tour-actions">
            <button type="button" className="btn ghost" onClick={finish}>
              رد کردن (Skip)
            </button>
            <button type="button" className="btn teal" onClick={next}>
              {step >= STEPS.length - 1 ? "تمام" : "بعدی"}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
