"use client";

import { FormEvent, useState } from "react";
import { Upload } from "lucide-react";
import { Field, GroupPicker, Repeater, newId, todayISO } from "@/components/Repeater";
import { mediaUrl, uploadForm, reindexForms } from "@/lib/api";
import { displayJalali } from "@/lib/jalali";
import { useAdminSite } from "@/lib/AdminSiteContext";

const SECTIONS = [
  ["calendar", "تقویم"],
  ["notifications", "اطلاع‌رسانی"],
  ["circulars", "بخشنامه"],
  ["forms", "فرم‌ها"],
  ["professors", "اساتید"],
] as const;

export function ContentEditors() {
  const { site, patchLocal, groupList, token, uploadFile, reload, setMsg } = useAdminSite();
  const [section, setSection] = useState<(typeof SECTIONS)[number][0]>("calendar");
  const [formMeta, setFormMeta] = useState({ title: "", slug: "", description: "" });
  const [formGroups, setFormGroups] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const set = patchLocal;

  async function onUploadForm(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    try {
      const res = await uploadForm(token, { ...formMeta, group: formGroups.join(","), file });
      await reload();
      setFile(null);
      setFormMeta({ title: "", slug: "", description: "" });
      setFormGroups([]);
      if (res?.indexed) {
        setMsg(res.index_note || "فرم آپلود و برای ربات ایندکس شد.");
      } else {
        setMsg(
          `فرم آپلود شد ولی ایندکس نشد${res?.index_error ? `: ${res.index_error}` : ". دوباره آپلود کن یا دانش را چک کن."}`
        );
      }
    } catch (err: any) {
      setMsg(err.message || "خطای آپلود");
    }
  }

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>محتوای سامانه</h1>
          <p>تقویم، اطلاعیه، بخشنامه، فرم و اساتید — همه فیلتر گروه دارند.</p>
        </div>
      </header>

      <div className="admin-pills">
        {SECTIONS.map(([id, label]) => (
          <button key={id} type="button" className={section === id ? "on" : ""} onClick={() => setSection(id)}>
            {label}
          </button>
        ))}
      </div>

      {section === "calendar" && (
        <>
          <section className="admin-card">
            <Field
              label="عنوان بخش تقویم"
              value={site.calendar?.title}
              onChange={(v) => set({ calendar: { ...site.calendar, title: v } })}
            />
          </section>
          <Repeater
            title="رویدادها"
            items={site.calendar?.events || []}
            onChange={(events) => set({ calendar: { ...site.calendar, events } })}
            makeNew={() =>
              ({
                id: newId("ev"),
                label: "",
                date: todayISO(),
                time: "",
                description: "",
                remind_days: 10,
                sort_order: (site.calendar?.events || []).length,
                group_ids: [],
              }) as any
            }
            itemLabel={(e: any, i) => e.label || `رویداد ${i + 1}`}
            renderItem={(ev: any, update) => (
              <>
                <Field label="عنوان رویداد" value={ev.label} onChange={(v) => update({ label: v })} />
                <div className="field-row">
                  <Field label="تاریخ (میلادی ذخیره می‌شود)" type="date" value={ev.date} onChange={(v) => update({ date: v })} />
                  <Field label="ساعت" type="time" value={ev.time} onChange={(v) => update({ time: v })} />
                </div>
                <p className="json-hint">نمایش شمسی برای دانشجو: {ev.date ? displayJalali(ev.date) : "—"}</p>
                <Field label="توضیح" type="textarea" value={ev.description} onChange={(v) => update({ description: v })} />
                <Field label="چند روز قبل یادآوری" type="number" value={ev.remind_days} onChange={(v) => update({ remind_days: v })} />
                <GroupPicker groups={groupList} value={ev.group_ids} onChange={(group_ids) => update({ group_ids })} />
              </>
            )}
          />
        </>
      )}

      {section === "notifications" && (
        <Repeater
          title="اطلاع‌رسانی‌ها"
          items={site.notifications || []}
          onChange={(notifications) => set({ notifications })}
          makeNew={() =>
            ({
              id: newId("n"),
              title: "",
              body: "",
              pinned: false,
              push: false,
              created_at: new Date().toISOString().slice(0, 16).replace("T", " "),
              enabled: true,
              group_ids: [],
            }) as any
          }
          itemLabel={(n: any, i) => n.title || `اطلاعیه ${i + 1}`}
          renderItem={(n: any, update) => (
            <>
              <Field label="عنوان" value={n.title} onChange={(v) => update({ title: v })} />
              <Field label="متن" type="textarea" rows={4} value={n.body} onChange={(v) => update({ body: v })} />
              <Field label="تاریخ" value={n.created_at} onChange={(v) => update({ created_at: v })} />
              <div className="field-row">
                <Field label="مهم (پین)" type="checkbox" value={n.pinned} onChange={(v) => update({ pinned: v })} />
                <Field label="ارسال اعلان PWA" type="checkbox" value={n.push} onChange={(v) => update({ push: v })} />
              </div>
              <GroupPicker groups={groupList} value={n.group_ids} onChange={(group_ids) => update({ group_ids })} />
            </>
          )}
        />
      )}

      {section === "circulars" && (
        <Repeater
          title="بخشنامه‌ها"
          items={site.circulars || []}
          onChange={(circulars) => set({ circulars })}
          makeNew={() =>
            ({
              id: newId("c"),
              title: "",
              body: "",
              file_url: "",
              created_at: todayISO(),
              enabled: true,
              group_ids: [],
            }) as any
          }
          itemLabel={(c: any, i) => c.title || `بخشنامه ${i + 1}`}
          renderItem={(c: any, update) => (
            <>
              <Field label="عنوان" value={c.title} onChange={(v) => update({ title: v })} />
              <Field label="متن" type="textarea" rows={4} value={c.body} onChange={(v) => update({ body: v })} />
              <label className="field">
                <span>فایل بخشنامه</span>
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,.xlsx,.xls,.txt"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const info = await uploadFile(f, "circular");
                    update({ file_url: info.url, file_name: info.filename });
                  }}
                />
              </label>
              {c.file_url ? (
                <a className="file-chip" href={mediaUrl(c.file_url)} target="_blank" rel="noreferrer">
                  مشاهده فایل
                </a>
              ) : null}
              <Field label="تاریخ" value={c.created_at} onChange={(v) => update({ created_at: v })} />
              <GroupPicker groups={groupList} value={c.group_ids} onChange={(group_ids) => update({ group_ids })} />
            </>
          )}
        />
      )}

      {section === "forms" && (
        <section className="admin-card">
          <h3>فرم‌ها</h3>
          <p className="json-hint">متن فرم استخراج و برای پاسخ ربات ایندکس می‌شود.</p>
          <form onSubmit={onUploadForm} className="repeat-item">
            <Field label="عنوان فرم" value={formMeta.title} onChange={(v) => setFormMeta({ ...formMeta, title: v })} />
            <Field
              label="شناسه یکتا (انگلیسی)"
              value={formMeta.slug}
              onChange={(v) => setFormMeta({ ...formMeta, slug: v })}
              placeholder="internship-form"
            />
            <Field label="توضیح" type="textarea" value={formMeta.description} onChange={(v) => setFormMeta({ ...formMeta, description: v })} />
            <GroupPicker groups={groupList} value={formGroups} onChange={setFormGroups} />
            <label className="field">
              <span>فایل فرم (PDF / Word / Excel)</span>
              <input
                type="file"
                accept=".pdf,.doc,.docx,.xlsx,.xls,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
            </label>
            <button className="btn teal" disabled={!file || !formMeta.title || !formMeta.slug}>
              <Upload size={15} /> آپلود و ایندکس فرم
            </button>
          </form>
          <button
            type="button"
            className="btn ghost"
            style={{ marginTop: 8 }}
            onClick={async () => {
              try {
                const r = await reindexForms(token);
                await reload();
                setMsg(`ایندکس فرم‌ها: موفق ${r.ok} · ناموفق ${r.failed}`);
              } catch (err: any) {
                setMsg(err.message || "خطای ایندکس");
              }
            }}
          >
            ایندکس دوباره همه فرم‌ها
          </button>

          <Repeater
            title="فرم‌های موجود"
            items={site.forms || []}
            onChange={(forms) => set({ forms })}
            makeNew={() =>
              ({ id: newId("f"), slug: newId("form"), title: "", description: "", enabled: true, group_ids: [] }) as any
            }
            itemLabel={(f: any, i) => f.title || `فرم ${i + 1}`}
            renderItem={(f: any, update) => (
              <>
                <Field label="عنوان" value={f.title} onChange={(v) => update({ title: v })} />
                <Field label="توضیح" type="textarea" value={f.description} onChange={(v) => update({ description: v })} />
                {f.file_url ? (
                  <a className="file-chip" href={mediaUrl(f.file_url)} target="_blank" rel="noreferrer">
                    {f.filename || "دریافت فایل"}
                  </a>
                ) : null}
                <p className="json-hint">
                  {f.indexed === true
                    ? "ایندکس‌شده برای ربات"
                    : f.indexed === false
                      ? `ایندکس نشده${f.index_error ? `: ${f.index_error}` : ""}`
                      : "وضعیت ایندکس نامشخص (دوباره آپلود کن)"}
                </p>
                <Field label="فعال" type="checkbox" value={f.enabled} onChange={(v) => update({ enabled: v })} />
                <GroupPicker groups={groupList} value={f.group_ids} onChange={(group_ids) => update({ group_ids })} />
              </>
            )}
          />
        </section>
      )}

      {section === "professors" && (
        <Repeater
          title="اساتید و امتیازها"
          items={site.professors || []}
          onChange={(professors) => set({ professors })}
          makeNew={() =>
            ({
              id: newId("p"),
              full_name: "",
              course: "",
              score: 0,
              rank: 0,
              note: "",
              enabled: true,
              group_ids: [],
            }) as any
          }
          itemLabel={(p: any, i) => p.full_name || `استاد ${i + 1}`}
          renderItem={(p: any, update) => (
            <>
              <Field label="نام استاد" value={p.full_name} onChange={(v) => update({ full_name: v })} />
              <div className="field-row">
                <Field label="درس" value={p.course} onChange={(v) => update({ course: v })} />
                <Field label="امتیاز" type="number" value={p.score} onChange={(v) => update({ score: v })} />
              </div>
              <Field label="توضیح" value={p.note} onChange={(v) => update({ note: v })} />
              <GroupPicker groups={groupList} value={p.group_ids} onChange={(group_ids) => update({ group_ids })} />
            </>
          )}
        />
      )}
    </div>
  );
}
