"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

type Theme = "light" | "dark";

type ThemeCtx = {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
};

const STORAGE_KEY = "theme";
const Ctx = createContext<ThemeCtx | null>(null);

function readStoredTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {}
  return "light";
}

function applyTheme(next: Theme, animate: boolean) {
  const root = document.documentElement;
  if (animate) {
    root.classList.remove("theme-switching");
    // force reflow so re-adding class retriggers transition
    void root.offsetWidth;
    root.classList.add("theme-switching");
    window.setTimeout(() => root.classList.remove("theme-switching"), 480);
  }
  root.setAttribute("data-theme", next);
  root.style.colorScheme = next;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const [hydrated, setHydrated] = useState(false);
  const ready = useRef(false);

  useEffect(() => {
    const saved = readStoredTheme();
    setThemeState(saved);
    applyTheme(saved, false);
    setHydrated(true);
    // بعد از یک تیک، انیمیشن برای تغییرهای بعدی فعال شود
    const t = window.setTimeout(() => {
      ready.current = true;
    }, 50);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    applyTheme(theme, ready.current);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {}
  }, [theme, hydrated]);

  const value = useMemo(
    () => ({
      theme,
      setTheme: (t: Theme) => setThemeState(t),
      toggle: () => setThemeState((t) => (t === "light" ? "dark" : "light")),
    }),
    [theme]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("ThemeProvider missing");
  return ctx;
}
