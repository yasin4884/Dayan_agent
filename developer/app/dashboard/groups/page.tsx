"use client";

import { useState } from "react";
import { createGroup, updateGroup } from "@/lib/api";
import { useAdminSite } from "@/lib/AdminSiteContext";

export default function GroupsPage() {
  const { token, groups, reloadGroups, setMsg } = useAdminSite();
  const [name, setName] = useState("");

  return (
    <div className="admin-stack">
      <header className="admin-page-head">
        <div>
          <h1>گروه‌های دانشجویی</h1>
          <p>همین لیست در ثبت‌نام می‌آید و مبنای فیلتر بنر، اطلاعیه و تقویم است.</p>
        </div>
      </header>
      <section className="admin-card">
        <div className="admin-toolbar">
          <input
            style={{ flex: 1, minWidth: 200 }}
            placeholder="نام گروه جدید"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            className="btn teal"
            type="button"
            onClick={async () => {
              if (!name.trim()) return;
              try {
                await createGroup(token, name.trim());
                await reloadGroups();
                setName("");
                setMsg("گروه اضافه شد.");
              } catch (e: any) {
                setMsg(e.message);
              }
            }}
          >
            افزودن گروه
          </button>
        </div>
        <div className="table-wrap">
          <table className="simple">
            <thead>
              <tr>
                <th>نام گروه</th>
                <th>وضعیت</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {!groups.length && (
                <tr>
                  <td colSpan={3} style={{ color: "var(--muted)" }}>
                    گروهی ثبت نشده است.
                  </td>
                </tr>
              )}
              {groups.map((g) => (
                <tr key={g.id}>
                  <td>{g.name}</td>
                  <td>{g.is_active === false ? "غیرفعال" : "فعال"}</td>
                  <td>
                    <button
                      className="btn ghost"
                      type="button"
                      onClick={async () => {
                        try {
                          await updateGroup(token, g.id, { is_active: g.is_active === false });
                          await reloadGroups();
                        } catch (e: any) {
                          setMsg(e.message);
                        }
                      }}
                    >
                      {g.is_active === false ? "فعال کن" : "غیرفعال کن"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
