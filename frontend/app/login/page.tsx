"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, Moon, Sun } from "lucide-react";
import { API_URL, fetchSite, login, register, SiteConfig } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";

type Group = { id: string; name: string };
type Mode = "login" | "register";

function logoUrl(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

const NAME_RE = /^[\u0600-\u06FFa-zA-Z\s'\-]{2,80}$/;
const USER_RE = /^[a-z0-9._]{3,30}$/;
const CODE_RE = /^\d{3,20}$/;
const PASS_RE = /^(?=.*[A-Za-z\u0600-\u06FF])(?=.*\d).{8,128}$/;

function validateRegister(form: {
  first_name: string;
  last_name: string;
  username: string;
  student_code: string;
  password: string;
  password_confirm: string;
  group_id: string;
}): string | null {
  if (!NAME_RE.test(form.first_name.trim())) return "نام فقط باید حروف باشد (حداقل ۲ حرف).";
  if (!NAME_RE.test(form.last_name.trim())) return "نام خانوادگی فقط باید حروف باشد (حداقل ۲ حرف).";
  if (!USER_RE.test(form.username.trim())) return "نام کاربری: فقط حروف کوچک انگلیسی، عدد، نقطه و زیرخط (۳ تا ۳۰).";
  if (!CODE_RE.test(form.student_code.trim())) return "کد دانشجویی فقط رقم است (۳ تا ۲۰ رقم).";
  if (!form.group_id) return "گروه تحصیلی را انتخاب کن.";
  if (!PASS_RE.test(form.password)) return "رمز باید حداقل ۸ کاراکتر و شامل حرف و عدد باشد.";
  if (form.password !== form.password_confirm) return "رمز و تکرار آن یکسان نیستند.";
  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [site, setSite] = useState<SiteConfig | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [mode, setMode] = useState<Mode>("login");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    username: "",
    student_code: "",
    group_id: "",
    identifier: "",
    password: "",
    password_confirm: "",
  });

  const setField = (key: keyof typeof form) => (v: string) =>
    setForm((f) => ({ ...f, [key]: v }));

  useEffect(() => {
    fetchSite().then(setSite).catch(() => setSite(null));
    fetch(`${API_URL}/api/public/groups`, { cache: "no-store" })
      .then((r) => r.json())
      .then((g) => {
        const list: Group[] = Array.isArray(g) ? g : [];
        setGroups(list);
        if (list[0]?.id) setForm((f) => ({ ...f, group_id: list[0].id }));
      })
      .catch(() => setGroups([]));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        if (form.identifier.trim().length < 3) {
          setError("نام کاربری یا کد دانشجویی را درست وارد کن.");
          return;
        }
        if (!form.password) {
          setError("رمز عبور را وارد کن.");
          return;
        }
        await login(form.identifier, form.password);
      } else {
        const v = validateRegister(form);
        if (v) {
          setError(v);
          return;
        }
        await register({
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          username: form.username.trim().toLowerCase(),
          student_code: form.student_code.trim(),
          password: form.password,
          password_confirm: form.password_confirm,
          group_id: form.group_id,
        });
      }
      router.push("/");
    } catch (err: any) {
      const msg = err?.message || "خطای نامشخص";
      if (/Failed to fetch|NetworkError|fetch/i.test(String(msg))) {
        setError("اتصال به سرور برقرار نشد. مطمئن شو API روی پورت ۸۰۰۰ روشن است.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  const copy = mode === "login" ? site?.login?.user : site?.login?.user;
  const brand = site?.brand?.name || "دایان";
  const logo = logoUrl(site?.brand?.logo_url);
  const noGroups = !groups.length;

  return (
    <div className="auth-shell" dir="rtl">
      <div className="auth-top">
        <Link className="icon-btn" href="/" aria-label="بازگشت به صفحه اصلی">
          <ArrowRight size={18} />
        </Link>
        <button className="icon-btn" onClick={toggle} aria-label="تغییر تم" type="button">
          {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>

      <motion.form
        className="auth-card glass"
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 22, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
      >
        <div className="auth-brand">
          {logo ? (
            <img className="brand-logo" src={logo} alt={brand} style={{ width: 54, height: 54 }} />
          ) : (
            <div className="brand-mark" style={{ width: 54, height: 54 }}>
              <span /><span /><span /><span />
            </div>
          )}
          <div>
            <strong style={{ fontSize: "1.05rem" }}>{brand}</strong>
            {site?.brand?.tagline ? (
              <div style={{ color: "var(--muted)", fontSize: ".78rem" }}>{site.brand.tagline}</div>
            ) : null}
          </div>
        </div>

        <h1>{mode === "login" ? copy?.title || "ورود" : "ثبت‌نام"}</h1>
        <p>
          {mode === "login"
            ? copy?.subtitle || "با نام کاربری یا کد دانشجویی وارد شو."
            : "برای ساخت حساب، اطلاعات زیر را کامل کن."}
        </p>

        <div className="role-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            ورود
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            ثبت‌نام
          </button>
        </div>

        {error && <p className="form-error">{error}</p>}

        {mode === "register" ? (
              <>
                <div className="field-row">
                  <label className="field">
                    <span>نام</span>
                    <input
                      value={form.first_name}
                      onChange={(e) =>
                        setField("first_name")(e.target.value.replace(/[^\u0600-\u06FFa-zA-Z\s'\-]/g, ""))
                      }
                      required
                      minLength={2}
                      maxLength={80}
                      pattern="[\u0600-\u06FFa-zA-Z\s'\-]{2,80}"
                      title="فقط حروف"
                      autoComplete="given-name"
                    />
                  </label>
                  <label className="field">
                    <span>نام خانوادگی</span>
                    <input
                      value={form.last_name}
                      onChange={(e) =>
                        setField("last_name")(e.target.value.replace(/[^\u0600-\u06FFa-zA-Z\s'\-]/g, ""))
                      }
                      required
                      minLength={2}
                      maxLength={80}
                      pattern="[\u0600-\u06FFa-zA-Z\s'\-]{2,80}"
                      title="فقط حروف"
                      autoComplete="family-name"
                    />
                  </label>
                </div>

                <label className="field">
                  <span>نام کاربری (حروف کوچک انگلیسی، عدد، نقطه)</span>
                  <input
                    value={form.username}
                    onChange={(e) => setField("username")(e.target.value.toLowerCase())}
                    required
                    minLength={3}
                    maxLength={30}
                    pattern="[a-z0-9._]+"
                    dir="ltr"
                    autoComplete="username"
                  />
                </label>

                <label className="field">
                  <span>کد دانشجویی</span>
                  <input
                    value={form.student_code}
                    onChange={(e) =>
                      setField("student_code")(
                        e.target.value.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d).toString()).replace(/\D/g, "")
                      )
                    }
                    required
                    inputMode="numeric"
                    minLength={3}
                    maxLength={20}
                    dir="ltr"
                  />
                </label>

                <label className="field">
                  <span>گروه تحصیلی</span>
                  <select
                    value={form.group_id}
                    onChange={(e) => setField("group_id")(e.target.value)}
                    required
                    disabled={noGroups}
                  >
                    <option value="" disabled>
                      انتخاب گروه
                    </option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </label>
                {noGroups && (
                  <p className="form-error">
                    هنوز گروهی تعریف نشده است. ادمین باید از پنل مدیریت گروه بسازد.
                  </p>
                )}

                <div className="field-row">
                  <label className="field">
                    <span>رمز عبور</span>
                    <input
                      value={form.password}
                      onChange={(e) => setField("password")(e.target.value)}
                      type={showPass ? "text" : "password"}
                      required
                      minLength={8}
                      maxLength={128}
                      autoComplete="new-password"
                    />
                  </label>
                  <label className="field">
                    <span>تکرار رمز</span>
                    <input
                      value={form.password_confirm}
                      onChange={(e) => setField("password_confirm")(e.target.value)}
                      type={showPass ? "text" : "password"}
                      required
                      minLength={8}
                      maxLength={128}
                      autoComplete="new-password"
                    />
                  </label>
                </div>
                <p className="json-hint" style={{ margin: "-4px 0 10px" }}>
                  رمز باید حداقل ۸ کاراکتر و شامل حرف و عدد باشد.
                </p>
              </>
            ) : (
              <>
                <label className="field">
                  <span>نام کاربری یا کد دانشجویی</span>
                  <input
                    value={form.identifier}
                    onChange={(e) => setField("identifier")(e.target.value)}
                    required
                    dir="ltr"
                    autoComplete="username"
                  />
                </label>
                <label className="field">
                  <span>رمز عبور</span>
                  <span className="pass-wrap">
                    <input
                      value={form.password}
                      onChange={(e) => setField("password")(e.target.value)}
                      type={showPass ? "text" : "password"}
                      required
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      className="pass-toggle"
                      onClick={() => setShowPass((v) => !v)}
                      aria-label={showPass ? "پنهان کردن رمز" : "نمایش رمز"}
                    >
                      {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </span>
                </label>
              </>
            )}

        <button
          className="btn teal"
          style={{ width: "100%", marginTop: 4 }}
          disabled={loading || (mode === "register" && noGroups)}
        >
          {loading ? "لطفاً صبر کنید..." : mode === "login" ? "ورود" : "ساخت حساب"}
        </button>
      </motion.form>
    </div>
  );
}
