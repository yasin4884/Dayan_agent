export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type GroupTargeted = { group_ids?: string[]; enabled?: boolean; sort_order?: number };

export type SiteConfig = {
  brand: {
    name: string;
    product_title: string;
    tagline: string;
    logo_url?: string;
    favicon_url?: string;
    website_url?: string;
    website_label?: string;
  };
  theme: Record<string, string>;
  banners: Array<
    GroupTargeted & {
      id: string;
      title?: string;
      subtitle?: string;
      image_url?: string;
      link_url?: string;
    }
  >;
  quick_actions: Array<
    GroupTargeted & {
      id: string;
      title: string;
      description?: string;
      button_label?: string;
      href?: string;
      color?: string;
      icon?: string;
      badge?: string;
    }
  >;
  /** نام قدیمی quick_actions — برای سازگاری */
  modules: SiteConfig["quick_actions"];
  calendar: {
    title: string;
    events: Array<
      GroupTargeted & {
        id: string;
        label?: string;
        title?: string;
        date: string;
        time?: string;
        description?: string;
        remind_days?: number;
      }
    >;
  };
  notifications: Array<
    GroupTargeted & {
      id: string;
      title: string;
      body?: string;
      pinned?: boolean;
      push?: boolean;
      created_at?: string;
    }
  >;
  circulars: Array<
    GroupTargeted & {
      id: string;
      title: string;
      body?: string;
      file_url?: string;
      file_name?: string;
      created_at?: string;
    }
  >;
  forms: Array<
    GroupTargeted & {
      id: string;
      slug: string;
      title: string;
      description?: string;
      file_url?: string;
      filename?: string;
    }
  >;
  professors: Array<
    GroupTargeted & {
      id: string;
      full_name: string;
      course?: string;
      score?: number;
      rank?: number;
      note?: string;
    }
  >;
  telegram: {
    enabled: boolean;
    title: string;
    description?: string;
    button_label: string;
    url: string;
  };
  links: Array<GroupTargeted & { id: string; title: string; url: string }>;
  comments: Array<GroupTargeted & { id: string; author: string; text: string }>;
  hero_banner: {
    enabled: boolean;
    title: string;
    subtitle: string;
    background: string;
    image_url?: string;
  };
  login: Record<
    string,
    { title: string; subtitle: string; banner_text: string; banner_url?: string }
  >;
  nav: Array<{ id: string; label: string; href: string; icon: string }>;
  ai_rules: string[];
  faqs?: Array<{ id: string; question: string; answer?: string }>;
  groups?: Array<{ id: string; name: string }>;
};

async function readError(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (typeof data.message === "string" && data.message) return data.message;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.fields) && data.fields.length) return data.fields.join("؛ ");
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d: any) => (typeof d?.msg === "string" ? d.msg : "مقدار نامعتبر"))
      .join("؛ ");
  }
  return "درخواست ناموفق بود";
}

function storeTokens(data: any) {
  if (data?.access_token) localStorage.setItem("token", data.access_token);
  if (data?.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
  if (data?.user) localStorage.setItem("user", JSON.stringify(data.user));
}

function clearTokens() {
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

let refreshInFlight: Promise<boolean> | null = null;

export async function refreshSession(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      clearTokens();
      return false;
    }
    storeTokens(data);
    return true;
  } catch {
    return false;
  }
}

function isAuthExpiredPayload(data: any) {
  const code = String(data?.error_code || "");
  const msg = String(data?.message || data?.detail || "");
  return (
    code === "TOKEN_EXPIRED" ||
    code === "TOKEN_INVALID" ||
    /منقضی|معتبر نیست|Unauthorized/i.test(msg)
  );
}

/** fetch با تمدید خودکار توکن بعد از انقضا. */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const run = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers = new Headers(init?.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return fetch(`${API_URL}${path}`, { ...init, headers });
  };

  let res = await run();
  if (res.status !== 401) return res;

  const data = await res.clone().json().catch(() => ({}));
  if (!isAuthExpiredPayload(data)) return res;

  if (!refreshInFlight) {
    refreshInFlight = refreshSession().finally(() => {
      refreshInFlight = null;
    });
  }
  const ok = await refreshInFlight;
  if (!ok) return res;
  return run();
}

export async function fetchSite(): Promise<SiteConfig> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const userRaw = typeof window !== "undefined" ? localStorage.getItem("user") : null;
  let groupQuery = "";
  if (userRaw) {
    try {
      const u = JSON.parse(userRaw);
      if (u.group_id) groupQuery = `?group_id=${encodeURIComponent(u.group_id)}`;
    } catch {}
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const res = await fetch(`${API_URL}/api/public/site${groupQuery}`, {
      cache: "no-store",
      signal: ctrl.signal,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("سرور پاسخ نداد. API را چک کن.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/** لیست‌های فیلترشده بر اساس گروه کاربر (توکن را می‌فرستد). */
async function getList<T>(path: string): Promise<T> {
  const res = await authFetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export const fetchNotifications = () => getList<any[]>("/api/notifications?sort=newest");
export const fetchCirculars = () => getList<any[]>("/api/circulars");
export const fetchForms = () => getList<any[]>("/api/forms");
export const fetchProfessors = () => getList<any[]>("/api/professors");
export const fetchCalendar = () => getList<{ title: string; events: any[] }>("/api/calendar");

export async function authStatus() {
  const res = await fetch(`${API_URL}/api/auth/status`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function login(identifier: string, password: string) {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ورود ناموفق"));
  storeTokens(data);
  return data;
}

export async function register(payload: {
  first_name: string;
  last_name: string;
  username: string;
  student_code: string;
  password: string;
  password_confirm: string;
  group_id: string;
}) {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ثبت‌نام ناموفق"));
  storeTokens(data);
  return data;
}

export async function changePassword(
  current_password: string,
  new_password: string,
  new_password_confirm: string
) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (!token) throw new Error("وارد حساب شو.");
  const res = await authFetch("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password, new_password_confirm }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "عوض کردن رمز ناموفق"));
  return data;
}

export async function chat(
  message: string,
  sessionId: string,
  token?: string,
  meta?: { page_path?: string; page_title?: string; page_text?: string; current_page?: string }
) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 100000);
  try {
    const res = await authFetch("/api/chat", {
      method: "POST",
      signal: ctrl.signal,
      body: JSON.stringify({
        message,
        session_id: sessionId,
        page_path: meta?.page_path,
        page_title: meta?.page_title,
        page_text: meta?.page_text,
        current_page: meta?.current_page,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "خطا در گفتگو"));
    return data;
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("پاسخ دیر آمد. دوباره کوتاه‌تر بپرس.");
    const msg = String(e?.message || e || "");
    if (/Failed to fetch|NetworkError|fetch failed|Load failed/i.test(msg)) {
      throw new Error("ارتباط با سرور قطع شد. چند ثانیه صبر کن و دوباره بپرس.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function chatWithFiles(
  message: string,
  sessionId: string,
  files: File[],
  token?: string,
  meta?: { page_path?: string; page_title?: string; page_text?: string }
) {
  const form = new FormData();
  form.append("message", message);
  form.append("session_id", sessionId);
  form.append("page_path", meta?.page_path || "/");
  form.append("page_title", meta?.page_title || "");
  form.append("page_text", meta?.page_text || "");
  for (const f of files) form.append("files", f);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  try {
    const res = await authFetch("/api/chat/upload", {
      method: "POST",
      signal: ctrl.signal,
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "خطا در گفتگو"));
    return data;
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("بررسی فایل طول کشید. عکس کوچک‌تر بفرست یا دوباره امتحان کن.");
    const msg = String(e?.message || e || "");
    if (/Failed to fetch|NetworkError|fetch failed|Load failed/i.test(msg)) {
      throw new Error("ارتباط با سرور قطع شد. چند ثانیه صبر کن و دوباره بپرس.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function saveSite(site: SiteConfig, token: string) {
  const res = await fetch(`${API_URL}/api/admin/site`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(site),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ذخیره نشد"));
  return data;
}
