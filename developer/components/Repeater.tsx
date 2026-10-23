"use client";

import { Plus, Trash2 } from "lucide-react";

export type Group = { id: string; name: string };

/** ورودی متنی/عددی/چک‌باکس با برچسب فارسی. */
export function Field({
  label,
  value,
  onChange,
  type = "text",
  rows,
  placeholder,
}: {
  label: string;
  value: any;
  onChange: (v: any) => void;
  type?: "text" | "number" | "checkbox" | "textarea" | "date" | "time" | "url";
  rows?: number;
  placeholder?: string;
}) {
  if (type === "checkbox") {
    return (
      <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: ".88rem" }}>
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        <span>{label}</span>
      </label>
    );
  }
  return (
    <label className="field">
      <span>{label}</span>
      {type === "textarea" ? (
        <textarea
          rows={rows || 3}
          value={value ?? ""}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          type={type}
          value={value ?? ""}
          placeholder={placeholder}
          onChange={(e) => onChange(type === "number" ? Number(e.target.value) : e.target.value)}
        />
      )}
    </label>
  );
}

/** انتخاب گروه‌های هدف — خالی یعنی همه کاربران. */
export function GroupPicker({
  groups,
  value,
  onChange,
}: {
  groups: Group[];
  value?: string[];
  onChange: (v: string[]) => void;
}) {
  const selected = value || [];
  if (!groups.length) {
    return <p className="json-hint">اول از بخش «گروه‌ها» گروه بسازید.</p>;
  }
  return (
    <div>
      <span style={{ fontSize: ".84rem", color: "var(--muted)" }}>
        گروه‌های هدف (هیچ‌کدام = همه)
      </span>
      <div className="chip-toggle" style={{ marginTop: 6 }}>
        {groups.map((g) => {
          const on = selected.includes(g.id);
          return (
            <button
              key={g.id}
              type="button"
              className={on ? "on" : ""}
              onClick={() =>
                onChange(on ? selected.filter((x) => x !== g.id) : [...selected, g.id])
              }
            >
              {g.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** لیست تکرارشونده با افزودن/حذف/مرتب‌سازی. */
export function Repeater<T extends { id?: string }>({
  title,
  items,
  onChange,
  makeNew,
  renderItem,
  itemLabel,
}: {
  title: string;
  items: T[];
  onChange: (items: T[]) => void;
  makeNew: () => T;
  renderItem: (item: T, update: (patch: Partial<T>) => void, index: number) => React.ReactNode;
  itemLabel?: (item: T, index: number) => string;
}) {
  const list = items || [];

  return (
    <section className="admin-section">
      <div className="admin-toolbar">
        <h3 style={{ margin: 0, flex: 1 }}>{title}</h3>
        <button className="btn teal" type="button" onClick={() => onChange([...list, makeNew()])}>
          <Plus size={15} /> افزودن
        </button>
      </div>

      {!list.length && <p className="json-hint">موردی ثبت نشده است.</p>}

      {list.map((item, index) => (
        <div className="repeat-item" key={item.id || index}>
          <div className="repeat-head">
            <strong style={{ fontSize: ".9rem" }}>
              {itemLabel ? itemLabel(item, index) : `مورد ${index + 1}`}
            </strong>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className="btn ghost"
                type="button"
                title="بالا"
                disabled={index === 0}
                onClick={() => {
                  const next = [...list];
                  [next[index - 1], next[index]] = [next[index], next[index - 1]];
                  onChange(next);
                }}
              >
                ↑
              </button>
              <button
                className="btn ghost"
                type="button"
                title="پایین"
                disabled={index === list.length - 1}
                onClick={() => {
                  const next = [...list];
                  [next[index + 1], next[index]] = [next[index], next[index + 1]];
                  onChange(next);
                }}
              >
                ↓
              </button>
              <button
                className="btn ghost"
                type="button"
                title="حذف"
                onClick={() => onChange(list.filter((_, i) => i !== index))}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>
          {renderItem(
            item,
            (patch) => {
              const next = [...list];
              next[index] = { ...item, ...patch };
              onChange(next);
            },
            index
          )}
        </div>
      ))}
    </section>
  );
}

export const newId = (prefix: string) =>
  `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

export const todayISO = () => new Date().toISOString().slice(0, 10);
