"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { loginDeveloper } from "@/lib/api";

export default function DeveloperLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await loginDeveloper(username, password);
      const must = Boolean(data.user?.must_change_credentials);
      router.push(must ? "/dashboard/credentials" : "/dashboard/ops");
    } catch (err: any) {
      setError(err.message || "ورود ناموفق");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell" dir="rtl">
      <form className="auth-card glass" onSubmit={onSubmit}>
        <div className="brand-row">
          <div className="brand-mark">
            <span /><span /><span /><span />
          </div>
          <strong>دایان — پنل دولوپر</strong>
        </div>
        <h1>ورود دولوپر</h1>
        <p>لاگ، ری‌استارت و مدیریت سامانه</p>
        <label className="field">
          <span>نام کاربری</span>
          <input value={username} onChange={(e) => setUsername(e.target.value)} required dir="ltr" autoComplete="username" />
        </label>
        <label className="field">
          <span>رمز عبور</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required autoComplete="current-password" />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="btn teal" style={{ width: "100%" }} disabled={loading}>
          {loading ? "..." : "ورود"}
        </button>
      </form>
    </div>
  );
}
