"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { API_URL } from "@/lib/api";

export type Banner = {
  id: string;
  title?: string;
  subtitle?: string;
  image_url?: string;
  link_url?: string;
};

function absolute(url?: string) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export function BannerSlider({ banners }: { banners: Banner[] }) {
  const [index, setIndex] = useState(0);
  const count = banners.length;

  useEffect(() => {
    if (count < 2) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % count), 5000);
    return () => clearInterval(timer);
  }, [count]);

  if (!count) {
    return (
      <div className="empty-state glass" style={{ marginBottom: 16 }}>
        هنوز بنری از پنل ادمین اضافه نشده است.
      </div>
    );
  }

  const current = banners[index % count];
  const image = absolute(current.image_url);
  const Wrapper: any = current.link_url ? "a" : "div";
  const wrapperProps = current.link_url
    ? { href: current.link_url, target: "_blank", rel: "noreferrer" }
    : {};

  return (
    <div className="banner-slider glass">
      <AnimatePresence mode="wait">
        <motion.div
          key={current.id || index}
          className="banner-slide"
          style={image ? { backgroundImage: `url(${image})` } : undefined}
          initial={{ opacity: 0, scale: 1.04 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.99 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          <Wrapper {...wrapperProps}>
            {current.title ? <h2>{current.title}</h2> : null}
            {current.subtitle ? <p>{current.subtitle}</p> : null}
          </Wrapper>
        </motion.div>
      </AnimatePresence>

      {count > 1 && (
        <div className="banner-dots">
          {banners.map((b, i) => (
            <button
              key={b.id || i}
              type="button"
              className={i === index ? "active" : ""}
              onClick={() => setIndex(i)}
              aria-label={`بنر ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
