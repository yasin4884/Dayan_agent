"use client";

import { FormEvent, useState } from "react";
import { Field } from "@/components/Repeater";
import { changeAdminPassword, registerAdmin } from "@/lib/api";
import { useAdminSite } from "@/lib/AdminSiteContext";

export default function SettingsPage() {
  const { token, site, setSite, persist, setMsg } = useAdminSite();
  const [adminForm, setAdminForm] = useState({
    full_name: "",
    personnel_code: "",
    password: "",
    password_confirm: "",
  });
  const [passForm, setPassForm] = useState({
    current_password: "",
    new_password: "",
    new_password_confirm: "",
  });

  async function onRegisterAdmin(e: FormEvent) {
    e.preventDefault();
    try {
      const data = await registerAdmin(token, adminForm);
      setMsg(`ادمین جدید ساخته شد: ${data.user?.personnel_code}`);
      setAdminForm({ full_name: "", personnel_code: "", password: "", password_confirm: "" });
    } catch (err: any) {
      setMsg(err.message || "خطا");
    }
  }

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    try {
      await changeAdminPassword(token, passForm);
      setMsg("رمز عبور شما عوض شد.");
      setPassForm({ current_password: "", new_password: "", new_password_confirm: "" });
    } catch (err: any) {
      setMsg(err.message || "عوض کردن رمز ناموفق");
    }
  }

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>تنظیمات</h1>
          <p>متن صفحه ورود، عوض کردن رمز، و ساخت ادمین جدید.</p>
        </div>
      </header>

      <section className="admin-card">
        <h3>متن صفحه ورود دانشجو</h3>
        <Field
          label="عنوان"
          value={site.login?.user?.title}
          onChange={(v) => setSite({ ...site, login: { ...site.login, user: { ...site.login.user, title: v } } })}
        />
        <Field
          label="زیرعنوان"
          type="textarea"
          value={site.login?.user?.subtitle}
          onChange={(v) => setSite({ ...site, login: { ...site.login, user: { ...site.login.user, subtitle: v } } })}
        />
        <h3 style={{ marginTop: 8 }}>متن صفحه ورود ادمین</h3>
        <Field
          label="عنوان"
          value={site.login?.admin?.title}
          onChange={(v) => setSite({ ...site, login: { ...site.login, admin: { ...site.login.admin, title: v } } })}
        />
        <Field
          label="زیرعنوان"
          type="textarea"
          value={site.login?.admin?.subtitle}
          onChange={(v) => setSite({ ...site, login: { ...site.login, admin: { ...site.login.admin, subtitle: v } } })}
        />
        <button className="btn teal" type="button" onClick={() => persist(["login"])}>
          ذخیره متن ورود
        </button>
      </section>

      <form onSubmit={onChangePassword} className="admin-card">
        <h3>عوض کردن رمز من</h3>
        <p className="json-hint">رمز فعلی را وارد کن و رمز جدید بگذار (حداقل ۸ کاراکتر، حرف + عدد).</p>
        <label className="field">
          <span>رمز فعلی</span>
          <input
            type="password"
            minLength={1}
            value={passForm.current_password}
            onChange={(e) => setPassForm({ ...passForm, current_password: e.target.value })}
            required
            autoComplete="current-password"
          />
        </label>
        <div className="field-row">
          <label className="field">
            <span>رمز جدید</span>
            <input
              type="password"
              minLength={8}
              value={passForm.new_password}
              onChange={(e) => setPassForm({ ...passForm, new_password: e.target.value })}
              required
              autoComplete="new-password"
            />
          </label>
          <label className="field">
            <span>تکرار رمز جدید</span>
            <input
              type="password"
              minLength={8}
              value={passForm.new_password_confirm}
              onChange={(e) => setPassForm({ ...passForm, new_password_confirm: e.target.value })}
              required
              autoComplete="new-password"
            />
          </label>
        </div>
        <button className="btn teal">ذخیره رمز جدید</button>
      </form>

      <form onSubmit={onRegisterAdmin} className="admin-card">
        <h3>ثبت ادمین جدید</h3>
        <p className="json-hint">ورود ادمین فقط با شماره پرسنلی است.</p>
        <Field label="نام و نام خانوادگی" value={adminForm.full_name} onChange={(v) => setAdminForm({ ...adminForm, full_name: v })} />
        <Field label="شماره پرسنلی" value={adminForm.personnel_code} onChange={(v) => setAdminForm({ ...adminForm, personnel_code: v })} />
        <div className="field-row">
          <label className="field">
            <span>رمز عبور</span>
            <input
              type="password"
              minLength={8}
              value={adminForm.password}
              onChange={(e) => setAdminForm({ ...adminForm, password: e.target.value })}
              required
            />
          </label>
          <label className="field">
            <span>تکرار رمز</span>
            <input
              type="password"
              minLength={8}
              value={adminForm.password_confirm}
              onChange={(e) => setAdminForm({ ...adminForm, password_confirm: e.target.value })}
              required
            />
          </label>
        </div>
        <button className="btn teal">ثبت ادمین</button>
      </form>
    </div>
  );
}
