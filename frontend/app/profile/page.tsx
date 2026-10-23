"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { changePassword } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";
import { SiteDock } from "@/components/SiteDock";

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [current, setCurrent] = useState("");
  const [nextPass, setNextPass] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("user");
      if (raw) setUser(JSON.parse(raw));
    } catch {}
  }, []);

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    router.push("/login");
  }

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      await changePassword(current, nextPass, confirm);
      setCurrent("");
      setNextPass("");
      setConfirm("");
      setMsg("رمز با موفقیت عوض شد.");
    } catch (err: any) {
      setMsg(err.message || "عوض کردن رمز ناموفق");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell" dir="rtl">
      <header className="topbar glass">
        <BrandMark title="پروفایل" />
      </header>

      {!user ? (
        <div className="empty-state glass">وارد حساب نشده‌اید.</div>
      ) : (
        <>
          <section className="list-item glass">
            <h4>{user.full_name || `${user.first_name || ""} ${user.last_name || ""}`}</h4>
            <p>نام کاربری: {user.username}</p>
            <p>کد دانشجویی: {user.student_code}</p>
            {user.group_name ? <p>گروه: {user.group_name}</p> : null}
            <p style={{ color: "var(--muted)", fontSize: ".85rem" }}>حساب دانشجویی</p>
            <button className="btn ghost" type="button" onClick={logout} style={{ marginTop: 10 }}>
              خروج
            </button>
          </section>

          <section className="list-item glass" style={{ marginTop: 14 }}>
            <h4>عوض کردن رمز</h4>
            <form onSubmit={onChangePassword} className="auth-card" style={{ boxShadow: "none", background: "transparent", padding: 0 }}>
              <label className="field">
                <span>رمز فعلی</span>
                <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
              </label>
              <label className="field">
                <span>رمز جدید</span>
                <input type="password" value={nextPass} onChange={(e) => setNextPass(e.target.value)} required minLength={8} />
              </label>
              <label className="field">
                <span>تکرار رمز جدید</span>
                <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
              </label>
              {msg ? <p className="form-error" style={{ color: msg.includes("موفق") ? "var(--accent)" : undefined }}>{msg}</p> : null}
              <button className="btn teal" disabled={loading} type="submit">
                {loading ? "..." : "ذخیره رمز جدید"}
              </button>
            </form>
          </section>
        </>
      )}
      <SiteDock />
    </div>
  );
}
