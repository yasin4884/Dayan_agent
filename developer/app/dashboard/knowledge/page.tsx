"use client";

import { FormEvent, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import {
  KnowledgeSnapshot,
  crawlUniversity,
  deleteKnowledge,
  fetchKnowledge,
  mediaUrl,
  saveKnowledgeRules,
  saveKnowledgeSettings,
  uploadKnowledge,
} from "@/lib/api";
import { Field, Repeater, newId } from "@/components/Repeater";
import { DropUpload } from "@/components/DropUpload";
import { useAdminSite } from "@/lib/AdminSiteContext";

const KIND_FA: Record<string, string> = {
  rule: "قانون",
  knowledge: "دانش ربات",
  form: "فرم",
  web: "صفحه سایت",
};

export default function KnowledgePage() {
  const { token, setMsg, site, patchLocal, persist } = useAdminSite();
  const [data, setData] = useState<KnowledgeSnapshot | null>(null);
  const [url, setUrl] = useState("");
  const [crawlUrl, setCrawlUrl] = useState("");
  const [crawlOn, setCrawlOn] = useState(false);
  const [rules, setRules] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"knowledge" | "rule">("knowledge");
  const [busy, setBusy] = useState("");

  async function load() {
    const snap = await fetchKnowledge(token);
    setData(snap);
    setUrl(snap.web_base_url || "");
    setCrawlUrl((snap as any).crawl_url || snap.web_base_url || "");
    setCrawlOn(Boolean(snap.crawl_enabled));
    setRules((snap.rules || []).join("\n"));
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, [token]);

  async function saveSiteSettings(e: FormEvent) {
    e.preventDefault();
    setBusy("settings");
    try {
      const snap = await saveKnowledgeSettings(token, {
        web_base_url: url.trim(),
        crawl_url: crawlUrl.trim() || url.trim(),
        crawl_enabled: crawlOn,
      });
      setData(snap);
      setCrawlUrl((snap as any).crawl_url || crawlUrl);
      setMsg("آدرس‌ها ذخیره شد. لینک صفحه اصلی جداست؛ کرول فقط از آدرس مدل.");
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  async function saveRules(e: FormEvent) {
    e.preventDefault();
    setBusy("rules");
    try {
      const list = rules.split("\n").map((x) => x.trim()).filter(Boolean);
      const snap = await saveKnowledgeRules(token, list);
      setData(snap);
      setMsg("قوانین ذخیره و ایندکس شد.");
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  async function onFile(file: File) {
    setBusy("upload");
    try {
      await uploadKnowledge(token, file, title || file.name, kind);
      setTitle("");
      await load();
      setMsg("فایل چانک و امبد شد.");
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  async function crawl() {
    setBusy("crawl");
    try {
      const snap = await crawlUniversity(token, crawlUrl.trim() || url.trim() || undefined);
      setData(snap);
      setUrl(snap.web_base_url || url);
      setCrawlUrl((snap as any).crawl_url || crawlUrl || url);
      setCrawlOn(true);
      setMsg(`${snap.indexed_pages || 0} صفحه از سایت ایندکس شد.`);
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  async function remove(id: string) {
    setBusy(id);
    try {
      const snap = await deleteKnowledge(token, id);
      setData(snap);
      setMsg("سند از دانش ربات حذف شد.");
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  async function saveFaqs() {
    setBusy("faqs");
    try {
      await persist(["faqs"]);
      setMsg("سوالات متداول ذخیره شد. همیشه در چت پیشنهاد و جواب داده می‌شوند.");
    } catch (err: any) {
      setMsg(err.message || "ذخیره FAQ ناموفق");
    } finally {
      setBusy("");
    }
  }

  const docs = data?.documents || [];
  const faqs = site?.faqs || [];

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>دانش ربات</h1>
          <p>
            سوالات متداول همیشه اولویت اول چت هستند؛ بعدش اسناد و سایت دانشگاه برای جواب‌های عمیق‌تر.
          </p>
        </div>
      </header>

      <section className="admin-card">
        <div className="admin-toolbar">
          <h3 style={{ margin: 0, flex: 1 }}>سوالات متداول (FAQ)</h3>
          <button className="btn teal" type="button" onClick={saveFaqs} disabled={busy === "faqs"}>
            ذخیره FAQ
          </button>
        </div>
        <p className="json-hint">
          این سوال‌ها همیشه در چت پیشنهاد و جواب داده می‌شوند — چه مدل روشن باشد چه قطع. کلمات کلیدی کمک
          می‌کنند بهتر پیدا شوند.
        </p>
        <Repeater
          title=""
          items={faqs}
          onChange={(next) => patchLocal({ faqs: next })}
          makeNew={() => ({
            id: newId("faq"),
            question: "",
            answer: "",
            keywords: "",
            enabled: true,
          })}
          itemLabel={(f, i) => f.question || `سوال ${i + 1}`}
          renderItem={(f, update) => (
            <>
              <Field label="سوال" value={f.question} onChange={(v) => update({ question: v })} />
              <Field label="جواب" type="textarea" rows={4} value={f.answer} onChange={(v) => update({ answer: v })} />
              <Field
                label="کلمات کلیدی (با فاصله)"
                value={f.keywords || ""}
                onChange={(v) => update({ keywords: v })}
                placeholder="شهریه حذف واحد کتابخانه"
              />
              <Field
                label="فعال"
                type="checkbox"
                value={f.enabled !== false}
                onChange={(v) => update({ enabled: v })}
              />
            </>
          )}
        />
      </section>

      <form className="admin-card" onSubmit={saveSiteSettings}>
        <h3>سایت برای مدل (کرول)</h3>
        <p className="json-hint">
          این آدرس‌ها فقط برای دانش ربات است. لینک نمایشی صفحه اصلی را از «ظاهر → برند» بگذار.
        </p>
        <Field
          label="آدرس پایه سایت دانشگاه (مرجع)"
          type="url"
          value={url}
          onChange={setUrl}
          placeholder="https://example.ac.ir"
        />
        <Field
          label="آدرس شروع کرول مدل (می‌تواند صفحه خاصی باشد)"
          type="url"
          value={crawlUrl}
          onChange={setCrawlUrl}
          placeholder="https://example.ac.ir/students"
        />
        <Field
          label="اگر در دیتابیس نبود، سایت را بگرد"
          type="checkbox"
          value={crawlOn}
          onChange={setCrawlOn}
        />
        <div className="admin-toolbar">
          <button className="btn teal" disabled={busy === "settings"}>
            ذخیره آدرس کرول
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={crawl}
            disabled={busy === "crawl" || !(crawlUrl.trim() || url.trim())}
          >
            {busy === "crawl" ? "در حال ایندکس سایت..." : "الان سایت را ایندکس کن"}
          </button>
        </div>
      </form>

      <form className="admin-card" onSubmit={saveRules}>
        <h3>قوانین متنی</h3>
        <p className="json-hint">هر خط یک قانون. علاوه بر این می‌توانید فایل قانون هم آپلود کنید.</p>
        <textarea rows={8} value={rules} onChange={(e) => setRules(e.target.value)} />
        <button className="btn teal" disabled={busy === "rules"}>
          ذخیره و ایندکس قوانین
        </button>
      </form>

      <section className="admin-card">
        <h3>آپلود سند برای ربات</h3>
        <p className="json-hint">PDF، Word (.docx) و Excel (.xlsx). متن استخراج، چانک و امبد می‌شود.</p>
        <Field label="عنوان سند (اختیاری)" value={title} onChange={setTitle} />
        <label className="field">
          <span>نوع</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as "knowledge" | "rule")}>
            <option value="knowledge">دانش ربات</option>
            <option value="rule">قانون</option>
          </select>
        </label>
        <DropUpload
          label={busy === "upload" ? "در حال چانک و امبد..." : "فایل را انتخاب کنید"}
          hint="pdf / docx / xlsx"
          accept=".pdf,.doc,.docx,.xlsx,.xls,.txt,.md,.csv"
          onFile={onFile}
        />
      </section>

      <section className="admin-card">
        <h3>اسناد ایندکس‌شده</h3>
        {!docs.length ? <p className="json-hint">هنوز سندی ایندکس نشده است.</p> : null}
        <div className="knowledge-list">
          {docs.map((d) => (
            <article key={d.id} className="knowledge-row">
              <div>
                <strong>{d.title}</strong>
                <p>
                  {KIND_FA[d.kind] || d.kind}
                  {d.chunk_count ? ` · ${d.chunk_count} قطعه` : ""}
                  {d.created_at ? ` · ${d.created_at}` : ""}
                </p>
                {d.file_url ? (
                  <a href={mediaUrl(d.file_url)} target="_blank" rel="noreferrer">
                    فایل
                  </a>
                ) : null}
                {d.source_url ? (
                  <a href={d.source_url} target="_blank" rel="noreferrer">
                    {d.source_url}
                  </a>
                ) : null}
              </div>
              <button className="btn ghost" type="button" onClick={() => remove(d.id)} disabled={busy === d.id}>
                <Trash2 size={15} />
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
