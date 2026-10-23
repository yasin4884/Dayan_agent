"use client";

import { useEffect, useState } from "react";
import { API_URL, fetchSite } from "@/lib/api";

export function mediaUrl(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

type Props = {
  /** اگر بدهی جای نام برند می‌نشیند (مثلاً عنوان صفحه). */
  title?: string;
  showTagline?: boolean;
};

/** لوگو/برند CMS — برای همه صفحات، نه فقط خانه. */
export function BrandMark({ title, showTagline = false }: Props) {
  const [logo, setLogo] = useState("");
  const [brand, setBrand] = useState("دایان");
  const [tagline, setTagline] = useState("");

  useEffect(() => {
    fetchSite()
      .then((s) => {
        setLogo(mediaUrl(s.brand?.logo_url));
        setBrand(s.brand?.name || s.brand?.product_title || "دایان");
        setTagline(s.brand?.tagline || "");
        const fav = mediaUrl(s.brand?.favicon_url || s.brand?.logo_url);
        if (fav && typeof document !== "undefined") {
          let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
          if (!link) {
            link = document.createElement("link");
            link.rel = "icon";
            document.head.appendChild(link);
          }
          link.href = fav;
        }
      })
      .catch(() => null);
  }, []);

  return (
    <div className="brand-row">
      {logo ? (
        <img className="brand-logo" src={logo} alt={brand} />
      ) : (
        <div className="brand-mark">
          <span />
          <span />
          <span />
          <span />
        </div>
      )}
      <div style={{ minWidth: 0 }}>
        <strong>{title || brand}</strong>
        {showTagline && tagline ? (
          <div style={{ color: "var(--muted)", fontSize: ".76rem" }}>{tagline}</div>
        ) : null}
      </div>
    </div>
  );
}
