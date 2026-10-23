"use client";

import { FormEvent, useEffect, useState } from "react";
import { createDevUser, listDevUsers } from "@/lib/api";

export default function DevUsersPage() {
  const [token, setToken] = useState("");
  const [users, setUsers] = useState<any[]>([]);
  const [form, setForm] = useState({
    username: "",
    display_name: "",
    password: "",
    password_confirm: "",
  });
  const [msg, setMsg] = useState("");

  async function reload(t: string) {
    const rows = await listDevUsers(t);
    setUsers(Array.isArray(rows) ? rows : []);
  }

  useEffect(() => {
    const t = localStorage.getItem("admin_token") || "";
    setToken(t);
    if (t) reload(t).catch((e) => setMsg(e.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      await createDevUser(token, form);
      setForm({ username: "", display_name: "", password: "", password_confirm: "" });
      await reload(token);
      setMsg("کاربر ساخته شد.");
    } catch (err: any) {
      setMsg(err.message || "ناموفق");
    }
  }

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>کاربران دولوپر</h1>
          <p>اضافه کردن حساب برای دسترسی به همین پنل</p>
        </div>
      </header>

      <form className="admin-card" onSubmit={onSubmit}>
        <label className="field">
          <span>نام کاربری</span>
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
            dir="ltr"
            minLength={3}
          />
        </label>
        <label className="field">
          <span>نام نمایشی</span>
          <input
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
        </label>
        <label className="field">
          <span>رمز</span>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            minLength={8}
          />
        </label>
        <label className="field">
          <span>تکرار رمز</span>
          <input
            type="password"
            value={form.password_confirm}
            onChange={(e) => setForm({ ...form, password_confirm: e.target.value })}
            required
            minLength={8}
          />
        </label>
        <button className="btn teal">افزودن کاربر</button>
        {msg ? <p className="json-hint">{msg}</p> : null}
      </form>

      <section className="admin-card">
        <h3>لیست</h3>
        {users.map((u) => (
          <div key={u.id} className="repeat-item">
            <strong>{u.username}</strong>
            <p className="json-hint">
              {u.display_name} · {u.must_change_credentials ? "باید اعتبار را عوض کند" : "فعال"}
            </p>
          </div>
        ))}
      </section>
    </div>
  );
}
