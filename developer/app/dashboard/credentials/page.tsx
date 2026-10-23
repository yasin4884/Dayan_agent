"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { changeDevCredentials } from "@/lib/api";

export default function CredentialsPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [current, setCurrent] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem("admin_token") || "");
    try {
      const u = JSON.parse(localStorage.getItem("admin_user") || "{}");
      if (u.username) setUsername(u.username);
    } catch {}
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      await changeDevCredentials(token, {
        current_password: current,
        new_username: username || undefined,
        new_password: password,
        new_password_confirm: confirm,
      });
      setMsg("اعتبار به‌روز شد.");
      setTimeout(() => router.push("/dashboard/ops"), 700);
    } catch (err: any) {
      setMsg(err.message || "ناموفق");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>عوض کردن نام کاربری و رمز</h1>
          <p>بعد از اولین ورود اجباری است؛ بعداً هم از اینجا عوض کن.</p>
        </div>
      </header>
      <form className="admin-card" onSubmit={onSubmit}>
        <label className="field">
          <span>رمز فعلی</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        </label>
        <label className="field">
          <span>نام کاربری جدید</span>
          <input value={username} onChange={(e) => setUsername(e.target.value)} required dir="ltr" minLength={3} />
        </label>
        <label className="field">
          <span>رمز جدید</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </label>
        <label className="field">
          <span>تکرار رمز جدید</span>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
        </label>
        {msg ? <p className="json-hint">{msg}</p> : null}
        <button className="btn teal" disabled={loading}>
          {loading ? "..." : "ذخیره"}
        </button>
      </form>
    </div>
  );
}
