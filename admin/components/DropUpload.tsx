"use client";

import { Upload } from "lucide-react";

export function DropUpload({
  label,
  hint,
  accept,
  previewUrl,
  onFile,
}: {
  label: string;
  hint?: string;
  accept?: string;
  previewUrl?: string;
  onFile: (file: File) => void | Promise<void>;
}) {
  return (
    <label className="drop-upload">
      <input
        type="file"
        accept={accept}
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          try {
            await onFile(f);
          } catch {
            /* خطا در والد نمایش داده می‌شود */
          }
        }}
      />
      {previewUrl ? (
        <img src={previewUrl} alt="" className="drop-upload-preview" />
      ) : (
        <div className="drop-upload-empty">
          <Upload size={22} />
          <strong>{label}</strong>
          {hint ? <span>{hint}</span> : null}
        </div>
      )}
    </label>
  );
}
