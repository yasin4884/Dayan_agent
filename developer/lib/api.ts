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
  faqs?: Array<{
    id: string;
    question: string;
    answer: string;
    keywords?: string;
    enabled?: boolean;
  }>;
  groups?: Array<{ id: string; name: string }>;
  knowledge?: {
    web_base_url?: string;
    crawl_enabled?: boolean;
    documents?: KnowledgeDoc[];
  };
};

export type KnowledgeDoc = {
  id: string;
  title: string;
  kind: string;
  filename?: string;
  file_url?: string;
  source_url?: string;
  chunk_count?: number;
  created_at?: string;
};

export type KnowledgeSnapshot = {
  web_base_url: string;
  crawl_url?: string;
  crawl_enabled: boolean;
  documents: KnowledgeDoc[];
  rules: string[];
  crawled_pages?: number;
  indexed_pages?: number;
  home_website_url?: string;
};

async function readError(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (typeof data.message === "string" && data.message) return data.message;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.fields) && data.fields.length) return data.fields.join("؛ ");
  return "درخواست ناموفق بود";
}

function storeAdminTokens(data: any) {
  if (data?.access_token) localStorage.setItem("admin_token", data.access_token);
  if (data?.refresh_token) localStorage.setItem("admin_refresh_token", data.refresh_token);
  if (data?.user) localStorage.setItem("admin_user", JSON.stringify(data.user));
}

export async function fetchSite(): Promise<SiteConfig> {
  const token = typeof window !== "undefined" ? localStorage.getItem("admin_token") : null;
  const res = await fetch(`${API_URL}/api/admin/site`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    // قبل از لاگین، سایت عمومی
    const pub = await fetch(`${API_URL}/api/public/site`, { cache: "no-store" });
    if (!pub.ok) throw new Error(await readError(pub));
    return pub.json();
  }
  return res.json();
}

export async function authStatus() {
  const res = await fetch(`${API_URL}/api/auth/status`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function login(personnel_code: string, password: string) {
  const res = await fetch(`${API_URL}/api/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ personnel_code, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ورود ناموفق"));
  storeAdminTokens(data);
  return data;
}

export async function setupAdmin(
  full_name: string,
  personnel_code: string,
  password: string,
  password_confirm: string
) {
  const res = await fetch(`${API_URL}/api/admin/auth/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name, personnel_code, password, password_confirm }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ساخت ادمین ناموفق"));
  storeAdminTokens(data);
  return data;
}

export async function listGroups(token: string) {
  const res = await fetch(`${API_URL}/api/admin/groups`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function updateGroup(token: string, id: string, patch: Record<string, unknown>) {
  const res = await fetch(`${API_URL}/api/admin/groups/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

/** آپلود لوگو / تصویر بنر / سند — نوع فایل سمت سرور با امضای بایتی بررسی می‌شود. */
export async function uploadMedia(token: string, file: File, kind = "media") {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  const res = await fetch(`${API_URL}/api/admin/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<{ url: string; filename: string; mime: string; size: number }>;
}

export async function registerAdmin(
  token: string,
  payload: {
    full_name: string;
    personnel_code: string;
    password: string;
    password_confirm: string;
  }
) {
  const res = await fetch(`${API_URL}/api/admin/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function changeAdminPassword(
  token: string,
  payload: {
    current_password: string;
    new_password: string;
    new_password_confirm: string;
  }
) {
  const res = await fetch(`${API_URL}/api/admin/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchLogs(token: string, limit = 100) {
  const res = await fetch(`${API_URL}/api/admin/logs?limit=${limit}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function createGroup(token: string, name: string, description = "") {
  const res = await fetch(`${API_URL}/api/admin/groups`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name, description }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ساخت گروه ناموفق"));
  return data;
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

export async function patchSite(token: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_URL}/api/admin/site`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ذخیره نشد"));
  return data as SiteConfig;
}

export function mediaUrl(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export async function fetchKnowledge(token: string): Promise<KnowledgeSnapshot> {
  const res = await fetch(`${API_URL}/api/admin/knowledge`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function saveKnowledgeSettings(
  token: string,
  payload: { web_base_url: string; crawl_enabled: boolean; crawl_url?: string }
) {
  const res = await fetch(`${API_URL}/api/admin/knowledge/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<KnowledgeSnapshot>;
}

export async function saveKnowledgeRules(token: string, rules: string[]) {
  const res = await fetch(`${API_URL}/api/admin/knowledge/rules`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ rules }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<KnowledgeSnapshot>;
}

export async function uploadKnowledge(token: string, file: File, title: string, kind: "knowledge" | "rule") {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  form.append("kind", kind);
  const res = await fetch(`${API_URL}/api/admin/knowledge/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<KnowledgeDoc>;
}

export async function crawlUniversity(token: string, url?: string) {
  const res = await fetch(`${API_URL}/api/admin/knowledge/crawl`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ url: url || null }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<KnowledgeSnapshot>;
}

export async function deleteKnowledge(token: string, documentId: string) {
  const res = await fetch(`${API_URL}/api/admin/knowledge/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<KnowledgeSnapshot>;
}

export async function uploadForm(
  token: string,
  payload: { title: string; slug: string; description: string; group: string; file: File }
) {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("slug", payload.slug);
  form.append("description", payload.description);
  form.append("group_ids", payload.group);
  form.append("file", payload.file);
  const res = await fetch(`${API_URL}/api/admin/forms`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "آپلود فرم ناموفق"));
  return data;
}

export async function reindexForms(token: string) {
  const res = await fetch(`${API_URL}/api/admin/forms/reindex`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ایندکس فرم‌ها ناموفق"));
  return data as { ok: number; failed: number };
}

export async function fetchDevBootstrap() {
  const res = await fetch(`${API_URL}/api/dev/bootstrap`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<{ ok?: boolean }>;
}

export async function loginDeveloper(username: string, password: string) {
  const res = await fetch(`${API_URL}/api/dev/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ورود ناموفق"));
  storeAdminTokens(data);
  return data;
}

export async function changeDevCredentials(
  token: string,
  payload: {
    current_password: string;
    new_username?: string;
    new_password: string;
    new_password_confirm: string;
  }
) {
  const res = await fetch(`${API_URL}/api/dev/auth/change-credentials`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ناموفق"));
  if (data.user) localStorage.setItem("admin_user", JSON.stringify(data.user));
  return data;
}

export async function listDevUsers(token: string) {
  const res = await fetch(`${API_URL}/api/dev/users`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function createDevUser(
  token: string,
  payload: { username: string; display_name: string; password: string; password_confirm: string }
) {
  const res = await fetch(`${API_URL}/api/dev/users`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ساخت کاربر ناموفق"));
  return data;
}

export async function fetchDevServices(token: string) {
  const res = await fetch(`${API_URL}/api/dev/services`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function restartService(token: string, service: string) {
  const res = await fetch(`${API_URL}/api/dev/services/restart`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ service }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(await readError(res).catch(() => data.message || "ری‌استارت ناموفق"));
  return data;
}

export async function fetchDevLogs(token: string, service: string, lines = 200) {
  const res = await fetch(`${API_URL}/api/dev/logs/${encodeURIComponent(service)}?lines=${lines}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<{ id: string; lines: string[]; path?: string }>;
}
