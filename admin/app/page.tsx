"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, signupAdmin, fetchSite, createGroup, SiteConfig } from "@/lib/api";

type Mode = "login" | "register";

export default function AdminLoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [site, setSite] = useState<SiteConfig | null>(null);
  const [fullName, setFullName] = useState("");
  const [personnelCode, setPersonnelCode] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSite().then(setSite).catch(() => null);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        if (password !== passwordConfirm) {
          setError("رمز و تکرار آن یکسان نیستند.");
          return;
        }
        const data = await signupAdmin(fullName, personnelCode, password, passwordConfirm);
        try {
          await createGroup(data.access_token, "گروه عمومی", "گروه پیش‌فرض");
        } catch {}
      } else {
        await login(personnelCode, password);
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || (mode === "register" ? "ثبت‌نام ناموفق بود." : "ورود ناموفق بود."));
    } finally {
      setLoading(false);
    }
  }

  const copy = site?.login?.admin;
  const brand = site?.brand?.name || "دایان — پنل ادمین";
  const isRegister = mode === "register";

  return (
    <div className="auth-shell" dir="rtl">
      <form className="auth-card glass" onSubmit={onSubmit}>
        <div className="brand-row">
          <div className="brand-mark">
            <span /><span /><span /><span />
          </div>
          <strong>{brand}</strong>
        </div>
        <h1>{isRegister ? "ثبت‌نام ادمین" : copy?.title || "ورود ادمین"}</h1>
        <p>{isRegister ? "نام، شماره پرسنلی و رمز را بزن." : copy?.subtitle || "با شماره پرسنلی و رمز وارد شو."}</p>

        <div className="role-tabs" role="tablist">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>
            ورود
          </button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>
            ثبت‌نام
          </button>
        </div>

        {isRegister && (
          <label className="field">
            <span>نام و نام خانوادگی</span>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
        )}
        <label className="field">
          <span>شماره پرسنلی</span>
          <input value={personnelCode} onChange={(e) => setPersonnelCode(e.target.value)} required dir="ltr" />
        </label>
        <label className="field">
          <span>رمز عبور</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            minLength={isRegister ? 8 : 1}
          />
        </label>
        {isRegister && (
          <label className="field">
            <span>تکرار رمز</span>
            <input
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              type="password"
              required
              minLength={8}
            />
          </label>
        )}
        {error && <p className="form-error">{error}</p>}
        <button className="btn teal" style={{ width: "100%" }} disabled={loading}>
          {loading ? "لطفا صبر کنید..." : isRegister ? "ثبت‌نام و ورود" : "ورود"}
        </button>
      </form>
    </div>
  );
}
