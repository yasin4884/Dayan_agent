"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  API_URL,
  SiteConfig,
  listGroups,
  patchSite,
  uploadMedia,
} from "@/lib/api";

type Group = { id: string; name: string; is_active?: boolean };

type Ctx = {
  token: string;
  site: SiteConfig;
  groups: Group[];
  groupList: Group[];
  msg: string;
  saving: boolean;
  setMsg: (v: string) => void;
  setSite: (site: SiteConfig) => void;
  patchLocal: (patch: Partial<SiteConfig>) => void;
  persist: (keys?: (keyof SiteConfig)[]) => Promise<void>;
  reload: () => Promise<void>;
  reloadGroups: () => Promise<void>;
  pickAndUpload: (kind: string, onDone: (url: string) => void, accept?: string) => void;
  uploadFile: (file: File, kind: string) => Promise<{ url: string; filename: string }>;
};

const AdminSiteCtx = createContext<Ctx | null>(null);

export function AdminSiteProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [site, setSite] = useState<SiteConfig | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async (t?: string) => {
    const auth = t || token || localStorage.getItem("admin_token") || "";
    const res = await fetch(`${API_URL}/api/admin/site`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${auth}` },
    });
    if (res.status === 401) {
      router.push("/");
      return;
    }
    if (!res.ok) throw new Error("خطا در دریافت تنظیمات");
    setSite(await res.json());
  }, [router, token]);

  const reloadGroups = useCallback(async (t?: string) => {
    const auth = t || token || localStorage.getItem("admin_token") || "";
    setGroups(await listGroups(auth));
  }, [token]);

  useEffect(() => {
    const t = localStorage.getItem("admin_token");
    if (!t) {
      router.push("/");
      return;
    }
    setToken(t);
    reload(t).catch((e) => setMsg(e.message));
    reloadGroups(t).catch(() => setGroups([]));
  }, [reload, reloadGroups, router]);

  const patchLocal = useCallback((patch: Partial<SiteConfig>) => {
    setSite((prev) => (prev ? { ...prev, ...patch } : prev));
  }, []);

  const persist = useCallback(
    async (keys?: (keyof SiteConfig)[]) => {
      if (!site || !token) return;
      setSaving(true);
      setMsg("");
      try {
        const payload = keys
          ? Object.fromEntries(keys.map((k) => [k, (site as any)[k]]))
          : {
              brand: site.brand,
              theme: site.theme,
              banners: site.banners,
              quick_actions: site.quick_actions,
              modules: site.quick_actions,
              calendar: site.calendar,
              notifications: site.notifications,
              circulars: site.circulars,
              forms: site.forms,
              professors: site.professors,
              telegram: site.telegram,
              links: site.links,
              comments: site.comments,
              login: site.login,
              nav: site.nav,
              hero_banner: site.hero_banner,
              faqs: (site as any).faqs || [],
              ai_rules: site.ai_rules,
            };
        const saved = await patchSite(token, payload);
        setSite(saved);
        setMsg("ذخیره شد و روی سایت اعمال شد.");
      } catch (e: any) {
        setMsg(e.message || "خطا در ذخیره");
      } finally {
        setSaving(false);
      }
    },
    [site, token]
  );

  const uploadFile = useCallback(
    async (file: File, kind: string) => {
      if (!token) throw new Error("وارد نشده‌اید");
      const info = await uploadMedia(token, file, kind);
      setMsg(`فایل «${info.filename}» بارگذاری شد.`);
      return info;
    },
    [token]
  );

  const pickAndUpload = useCallback(
    (kind: string, onDone: (url: string) => void, accept?: string) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = accept || (kind === "logo" || kind === "banner" ? "image/*" : "*/*");
      input.onchange = async () => {
        const f = input.files?.[0];
        if (!f) return;
        try {
          const info = await uploadFile(f, kind);
          onDone(info.url);
        } catch (e: any) {
          setMsg(e.message || "آپلود ناموفق");
        }
      };
      input.click();
    },
    [uploadFile]
  );

  const value = useMemo(() => {
    if (!site) return null;
    return {
      token,
      site,
      groups,
      groupList: groups.filter((g) => g.is_active !== false),
      msg,
      saving,
      setMsg,
      setSite,
      patchLocal,
      persist,
      reload: () => reload(),
      reloadGroups: () => reloadGroups(),
      pickAndUpload,
      uploadFile,
    } satisfies Ctx;
  }, [token, site, groups, msg, saving, patchLocal, persist, reload, reloadGroups, pickAndUpload, uploadFile]);

  if (!value) {
    return <div className="page-shell admin-loading" dir="rtl">در حال بارگذاری پنل...</div>;
  }

  return <AdminSiteCtx.Provider value={value}>{children}</AdminSiteCtx.Provider>;
}

export function useAdminSite() {
  const ctx = useContext(AdminSiteCtx);
  if (!ctx) throw new Error("AdminSiteProvider missing");
  return ctx;
}
