"use client";

import { useState } from "react";
import { Field, GroupPicker, Repeater, newId } from "@/components/Repeater";
import { DropUpload } from "@/components/DropUpload";
import { mediaUrl } from "@/lib/api";
import { useAdminSite } from "@/lib/AdminSiteContext";

const SECTIONS = [
  ["brand", "برند و لوگو"],
  ["banners", "بنرها"],
  ["quick", "دسترسی سریع"],
  ["nav", "منوی پایین"],
  ["telegram", "تلگرام و لینک"],
  ["comments", "نظرات"],
] as const;

export function AppearanceEditors() {
  const { site, patchLocal, groupList, uploadFile, setSite, setMsg } = useAdminSite();
  const [section, setSection] = useState<(typeof SECTIONS)[number][0]>("brand");
  const set = patchLocal;

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>صفحه اصلی</h1>
          <p>لوگو، بنر، دکمه‌ها و منوی پایین سایت دانشجو از اینجا می‌آید.</p>
        </div>
      </header>

      <div className="admin-pills">
        {SECTIONS.map(([id, label]) => (
          <button key={id} type="button" className={section === id ? "on" : ""} onClick={() => setSection(id)}>
            {label}
          </button>
        ))}
      </div>

      {section === "brand" && (
        <section className="admin-card">
          <h3>برند و لوگوی سامانه</h3>
          <p className="json-hint">هر چه خالی بماند در صفحه اصلی نمایش داده نمی‌شود.</p>
          <div className="brand-upload-row">
            <DropUpload
              label="بارگذاری لوگو"
              hint="PNG یا SVG مربعی بهتر است"
              accept="image/*"
              previewUrl={mediaUrl(site.brand?.logo_url)}
              onFile={async (file) => {
                const info = await uploadFile(file, "logo");
                setSite({ ...site, brand: { ...site.brand, logo_url: info.url } });
              }}
            />
            {site.brand?.logo_url ? (
              <button
                className="btn ghost"
                type="button"
                onClick={() => setSite({ ...site, brand: { ...site.brand, logo_url: "" } })}
              >
                حذف لوگو
              </button>
            ) : null}
          </div>
          <Field label="نام برند" value={site.brand?.name} onChange={(v) => setSite({ ...site, brand: { ...site.brand, name: v } })} />
          <Field
            label="عنوان محصول"
            value={site.brand?.product_title}
            onChange={(v) => setSite({ ...site, brand: { ...site.brand, product_title: v } })}
          />
          <Field
            label="شعار"
            value={site.brand?.tagline}
            onChange={(v) => setSite({ ...site, brand: { ...site.brand, tagline: v } })}
          />
          <Field
            label="لینک سایت دانشگاه (صفحه اصلی)"
            type="url"
            value={(site.brand as any)?.website_url || ""}
            onChange={(v) => setSite({ ...site, brand: { ...site.brand, website_url: v } as any })}
            placeholder="https://university.ac.ir"
          />
          <Field
            label="متن دکمه سایت دانشگاه"
            value={(site.brand as any)?.website_label || "سایت دانشگاه"}
            onChange={(v) => setSite({ ...site, brand: { ...site.brand, website_label: v } as any })}
          />
          <p className="json-hint">این لینک فقط روی صفحه اصلی دانشجو دیده می‌شود و با آدرس کرول مدل یکی نیست.</p>
          <div className="field-row">
            <Field label="رنگ اصلی" value={site.theme?.primary} onChange={(v) => set({ theme: { ...site.theme, primary: v } })} />
            <Field label="رنگ تاکیدی" value={site.theme?.accent} onChange={(v) => set({ theme: { ...site.theme, accent: v } })} />
          </div>
        </section>
      )}

      {section === "banners" && (
        <Repeater
          title="بنرهای متحرک"
          items={site.banners || []}
          onChange={(banners) => set({ banners })}
          makeNew={() =>
            ({
              id: newId("b"),
              title: "",
              subtitle: "",
              image_url: "",
              link_url: "",
              enabled: true,
              sort_order: (site.banners || []).length,
              group_ids: [],
            }) as any
          }
          itemLabel={(b: any, i) => b.title || `بنر ${i + 1}`}
          renderItem={(b: any, update) => (
            <>
              <DropUpload
                label="تصویر بنر را اینجا بگذارید"
                hint="افقی، حدود ۱۶:۹ — JPG یا PNG"
                accept="image/*"
                previewUrl={mediaUrl(b.image_url)}
                onFile={async (file) => {
                  try {
                    const info = await uploadFile(file, "banner");
                    update({ image_url: info.url });
                  } catch (e: any) {
                    setMsg?.(e.message || "آپلود بنر ناموفق");
                  }
                }}
              />
              <Field label="عنوان روی بنر" value={b.title} onChange={(v) => update({ title: v })} />
              <Field label="زیرعنوان" type="textarea" value={b.subtitle} onChange={(v) => update({ subtitle: v })} />
              <Field label="لینک (اختیاری)" type="url" value={b.link_url} onChange={(v) => update({ link_url: v })} />
              <Field label="فعال" type="checkbox" value={b.enabled} onChange={(v) => update({ enabled: v })} />
              <GroupPicker groups={groupList} value={b.group_ids} onChange={(group_ids) => update({ group_ids })} />
            </>
          )}
        />
      )}

      {section === "quick" && (
        <Repeater
          title="دکمه‌های دسترسی سریع"
          items={site.quick_actions || []}
          onChange={(quick_actions) => set({ quick_actions, modules: quick_actions })}
          makeNew={() =>
            ({
              id: newId("qa"),
              title: "",
              button_label: "ورود",
              href: "/",
              color: "teal",
              icon: "file",
              badge: "",
              enabled: true,
              sort_order: (site.quick_actions || []).length,
              group_ids: [],
            }) as any
          }
          itemLabel={(m: any, i) => m.title || `دکمه ${i + 1}`}
          renderItem={(m: any, update) => (
            <>
              <Field label="عنوان" value={m.title} onChange={(v) => update({ title: v })} />
              <div className="field-row">
                <Field label="متن دکمه" value={m.button_label} onChange={(v) => update({ button_label: v })} />
                <Field label="مسیر" value={m.href} onChange={(v) => update({ href: v })} />
              </div>
              <div className="field-row">
                <label className="field">
                  <span>رنگ</span>
                  <select value={m.color || "teal"} onChange={(e) => update({ color: e.target.value })}>
                    <option value="teal">فیروزه‌ای</option>
                    <option value="blue">آبی</option>
                    <option value="cyan">آبی روشن</option>
                    <option value="green">سبز</option>
                    <option value="orange">نارنجی</option>
                  </select>
                </label>
                <label className="field">
                  <span>آیکون</span>
                  <select value={m.icon || "file"} onChange={(e) => update({ icon: e.target.value })}>
                    <option value="bell">اطلاع‌رسانی</option>
                    <option value="calendar">تقویم</option>
                    <option value="file">فرم</option>
                    <option value="document">بخشنامه</option>
                    <option value="graduation">آموزش</option>
                    <option value="user">کاربر</option>
                  </select>
                </label>
              </div>
              <Field label="برچسب" value={m.badge} onChange={(v) => update({ badge: v })} />
              <Field label="فعال" type="checkbox" value={m.enabled} onChange={(v) => update({ enabled: v })} />
              <GroupPicker groups={groupList} value={m.group_ids} onChange={(group_ids) => update({ group_ids })} />
            </>
          )}
        />
      )}

      {section === "nav" && (
        <Repeater
          title="آیتم‌های داک پایین"
          items={site.nav || []}
          onChange={(nav) => set({ nav })}
          makeNew={() => ({ id: newId("nav"), label: "", href: "/", icon: "home" }) as any}
          itemLabel={(n: any, i) => n.label || `آیتم ${i + 1}`}
          renderItem={(n: any, update) => (
            <>
              <div className="field-row">
                <Field label="برچسب" value={n.label} onChange={(v) => update({ label: v })} />
                <Field label="مسیر" value={n.href} onChange={(v) => update({ href: v })} />
              </div>
              <label className="field">
                <span>آیکون</span>
                <select value={n.icon || "home"} onChange={(e) => update({ icon: e.target.value })}>
                  <option value="home">خانه</option>
                  <option value="bell">اطلاع‌رسانی</option>
                  <option value="calendar">تقویم</option>
                  <option value="file">فرم</option>
                  <option value="document">بخشنامه</option>
                  <option value="ticket">تیکت</option>
                  <option value="users">اساتید</option>
                  <option value="user">پروفایل</option>
                </select>
              </label>
            </>
          )}
        />
      )}

      {section === "telegram" && (
        <>
          <section className="admin-card">
            <h3>کانال تلگرام</h3>
            <Field label="فعال" type="checkbox" value={site.telegram?.enabled} onChange={(v) => set({ telegram: { ...site.telegram, enabled: v } })} />
            <Field label="عنوان" value={site.telegram?.title} onChange={(v) => set({ telegram: { ...site.telegram, title: v } })} />
            <Field label="توضیح" type="textarea" value={site.telegram?.description} onChange={(v) => set({ telegram: { ...site.telegram, description: v } })} />
            <div className="field-row">
              <Field label="متن دکمه" value={site.telegram?.button_label} onChange={(v) => set({ telegram: { ...site.telegram, button_label: v } })} />
              <Field label="لینک" type="url" value={site.telegram?.url} onChange={(v) => set({ telegram: { ...site.telegram, url: v } })} />
            </div>
          </section>
          <Repeater
            title="لینک‌های دیگر"
            items={site.links || []}
            onChange={(links) => set({ links })}
            makeNew={() => ({ id: newId("l"), title: "", url: "", enabled: true, group_ids: [] }) as any}
            itemLabel={(l: any, i) => l.title || `لینک ${i + 1}`}
            renderItem={(l: any, update) => (
              <>
                <Field label="عنوان" value={l.title} onChange={(v) => update({ title: v })} />
                <Field label="آدرس" type="url" value={l.url} onChange={(v) => update({ url: v })} />
                <GroupPicker groups={groupList} value={l.group_ids} onChange={(group_ids) => update({ group_ids })} />
              </>
            )}
          />
        </>
      )}

      {section === "comments" && (
        <Repeater
          title="نظرات تاییدشده"
          items={site.comments || []}
          onChange={(comments) => set({ comments })}
          makeNew={() => ({ id: newId("cm"), author: "", text: "", enabled: true, group_ids: [] }) as any}
          itemLabel={(c: any, i) => c.author || `نظر ${i + 1}`}
          renderItem={(c: any, update) => (
            <>
              <Field label="نام کاربر" value={c.author} onChange={(v) => update({ author: v })} />
              <Field label="متن نظر" type="textarea" value={c.text} onChange={(v) => update({ text: v })} />
              <Field label="تایید شده" type="checkbox" value={c.enabled} onChange={(v) => update({ enabled: v })} />
            </>
          )}
        />
      )}
    </div>
  );
}
